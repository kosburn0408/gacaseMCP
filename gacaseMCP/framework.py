"""In-memory index of one CASE framework package: tree, codes, search."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_WORD_RE = re.compile(r"[a-z0-9]+")
STATEMENT_PREVIEW = 300

# Georgia uses KG/01..12; accept common spellings.
_LEVEL_ALIASES = {
    "K": "KG", "KG": "KG", "KINDERGARTEN": "KG", "PK": "PK", "PREK": "PK", "PRE-K": "PK",
}


def normalize_level(level: str | None) -> str | None:
    if level is None:
        return None
    s = str(level).strip().upper().replace("TH", "").replace("ST", "").replace("ND", "").replace("RD", "")
    s = s.replace("GRADE", "").strip()
    if s in _LEVEL_ALIASES:
        return _LEVEL_ALIASES[s]
    if s.isdigit():
        return f"{int(s):02d}"
    return s


def words(text: str) -> list[str]:
    """Lowercase word tokens; hyphens and punctuation split words ("silent-e" → silent, e)."""
    return _WORD_RE.findall((text or "").lower())


def _node_id(node: Any) -> str | None:
    if isinstance(node, dict):
        return node.get("identifier")
    if isinstance(node, str):
        return node.rstrip("/").rsplit("/", 1)[-1]
    return None


def _node_title(node: Any) -> str | None:
    return node.get("title") if isinstance(node, dict) else None


def _node_uri(node: Any) -> str | None:
    if isinstance(node, dict):
        return node.get("uri")
    return node if isinstance(node, str) else None


def item_summary(item: dict[str, Any], full: bool = False) -> dict[str, Any]:
    stmt = item.get("fullStatement") or ""
    if not full and len(stmt) > STATEMENT_PREVIEW:
        stmt = stmt[:STATEMENT_PREVIEW].rstrip() + "…"
    out = {
        "identifier": item.get("identifier"),
        "code": (item.get("humanCodingScheme") or "").strip(),
        "statement": stmt,
        "item_type": (item.get("CFItemType") or "").strip(),
        "education_level": item.get("educationLevel") or [],
        "uri": item.get("uri"),
    }
    if full:
        for k in ("abbreviatedStatement", "notes", "statusStartDate", "statusEndDate", "lastChangeDateTime", "extensions"):
            if item.get(k) not in (None, "", [], {}):
                out[k] = item[k]
    return out


@dataclass
class FrameworkIndex:
    document: dict[str, Any]
    items: dict[str, dict[str, Any]]
    by_code: dict[str, list[str]]
    parent: dict[str, str]
    children: dict[str, list[tuple[float, str]]]
    associations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def doc_id(self) -> str:
        return self.document.get("identifier", "")

    @classmethod
    def build(cls, pkg: dict[str, Any]) -> "FrameworkIndex":
        doc = pkg.get("CFDocument", {}) or {}
        items = {i["identifier"]: i for i in pkg.get("CFItems", []) or [] if i.get("identifier")}
        by_code: dict[str, list[str]] = {}
        for iid, it in items.items():
            code = (it.get("humanCodingScheme") or "").strip()
            if code:
                by_code.setdefault(code.lower(), []).append(iid)
        parent: dict[str, str] = {}
        children: dict[str, list[tuple[float, str]]] = {}
        assocs = pkg.get("CFAssociations", []) or []
        for a in assocs:
            if (a.get("associationType") or "") != "isChildOf":
                continue
            child, par = _node_id(a.get("originNodeURI")), _node_id(a.get("destinationNodeURI"))
            if not child or not par:
                continue
            parent.setdefault(child, par)
            seq = a.get("sequenceNumber")
            children.setdefault(par, []).append((float(seq) if isinstance(seq, (int, float)) else 1e9, child))
        for lst in children.values():
            lst.sort(key=lambda t: (t[0], (items.get(t[1], {}).get("humanCodingScheme") or "")))
        return cls(doc, items, by_code, parent, children, assocs)

    # ── Lookup ────────────────────────────────────────────────────────────
    def resolve(self, ref: str) -> list[str]:
        """Item identifiers matching an identifier or a human code (codes can repeat)."""
        ref = (ref or "").strip()
        if ref in self.items:
            return [ref]
        tail = ref.rstrip("/").rsplit("/", 1)[-1]
        if tail in self.items:
            return [tail]
        return list(self.by_code.get(ref.lower(), []))

    def child_ids(self, parent_id: str | None) -> list[str]:
        pid = parent_id or self.doc_id
        ids = [c for _, c in self.children.get(pid, []) if c in self.items]
        if not ids and parent_id is None:
            # Some packages omit document-level isChildOf links: use items without a parent.
            ids = [i for i in self.items if i not in self.parent]
        return ids

    def ancestors(self, item_id: str) -> list[str]:
        chain: list[str] = []
        seen = {item_id}
        cur = self.parent.get(item_id)
        while cur and cur in self.items and cur not in seen:
            chain.append(cur)
            seen.add(cur)
            cur = self.parent.get(cur)
        return list(reversed(chain))

    def related(self, item_id: str, association_type: str | None = None) -> list[dict[str, Any]]:
        out = []
        for a in self.associations:
            atype = a.get("associationType") or ""
            if association_type and atype.lower() != association_type.lower():
                continue
            o, d = a.get("originNodeURI"), a.get("destinationNodeURI")
            oid, did = _node_id(o), _node_id(d)
            if item_id not in (oid, did):
                continue
            other_node, direction = (d, "outgoing") if oid == item_id else (o, "incoming")
            other_id = _node_id(other_node)
            other = self.items.get(other_id or "")
            out.append({
                "association_type": atype,
                "direction": direction,
                "sequence_number": a.get("sequenceNumber"),
                "other": item_summary(other) if other else {
                    "identifier": other_id, "title": _node_title(other_node), "uri": _node_uri(other_node),
                    "in_this_framework": other_id == self.doc_id,
                },
            })
        return out

    # ── Filtering & search ───────────────────────────────────────────────
    def filter(self, item_type: str | None = None, education_level: str | None = None) -> list[str]:
        lvl = normalize_level(education_level)
        out = []
        for iid, it in self.items.items():
            if item_type and (it.get("CFItemType") or "").strip().lower() != item_type.strip().lower():
                continue
            if lvl and lvl not in [normalize_level(x) for x in (it.get("educationLevel") or [])]:
                continue
            out.append(iid)
        out.sort(key=lambda i: (self.items[i].get("humanCodingScheme") or "~"))
        return out

    def search(self, query: str, item_type: str | None = None, education_level: str | None = None) -> list[tuple[float, str]]:
        q_words = words(query)
        if not q_words:
            return []
        q_phrase = " ".join(q_words)
        q_code = query.strip().lower()
        results = []
        for iid in self.filter(item_type, education_level):
            it = self.items[iid]
            code = (it.get("humanCodingScheme") or "").strip().lower()
            stmt_words = words(it.get("fullStatement") or "")
            stmt_text = " ".join(stmt_words)
            score = 0.0
            if code and code == q_code:
                score += 100
            elif code and code.startswith(q_code) and len(q_code) >= 2:
                score += 40
            present = [w for w in q_words if w in stmt_words or any(sw.startswith(w) for sw in stmt_words if len(w) >= 4)]
            if not present and score == 0:
                continue
            score += 10 * len(present) / len(q_words)
            if len(present) == len(q_words):
                score += 10
            if len(q_words) > 1 and q_phrase in stmt_text:
                score += 15
            # Prefer broader items (standards over sub-skills) on ties.
            score -= 0.1 * code.count(".")
            results.append((score, iid))
        results.sort(key=lambda t: (-t[0], self.items[t[1]].get("humanCodingScheme") or ""))
        return results


_index_cache: dict[str, tuple[int, FrameworkIndex]] = {}


def index_for(pkg: dict[str, Any], server: str = "") -> FrameworkIndex:
    """Build (or reuse) the index for a package object (keyed by server + framework)."""
    key = f"{server}:{pkg.get('CFDocument', {}).get('identifier', '')}"
    hit = _index_cache.get(key)
    if hit and hit[0] == id(pkg):
        return hit[1]
    idx = FrameworkIndex.build(pkg)
    _index_cache[key] = (id(pkg), idx)
    return idx
