"""gacaseMCP — MCP server for Georgia's SuitCASE (1EdTech CASE 1.1) standards API.

Tools are designed for AI assistants: they return summaries and pages, not
whole frameworks, and let the assistant walk the standards tree (children,
ancestors, associations) instead of reading everything at once.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gacaseMCP.client import (
    CaseAPIError,
    get_by_uri,
    get_documents,
    get_item_associations as fetch_item_associations,
    get_package,
    get_server,
    servers,
)
from gacaseMCP.framework import FrameworkIndex, index_for, item_summary, normalize_level

mcp = FastMCP("gacaseMCP")

COURSE_CODE_REGEX = re.compile(r"^\d{2}\.\d{5}$")
MAX_LIMIT = 200


def _err(exc: Exception) -> dict[str, Any]:
    return {"error": str(exc)}


def _page(ids: list[str], limit: int, offset: int) -> tuple[list[str], dict[str, Any]]:
    limit = max(1, min(int(limit or 50), MAX_LIMIT))
    offset = max(0, int(offset or 0))
    page = ids[offset:offset + limit]
    nxt = offset + limit if offset + limit < len(ids) else None
    return page, {"total": len(ids), "offset": offset, "limit": limit, "next_offset": nxt}


def _doc_summary(doc: dict[str, Any]) -> dict[str, Any]:
    pkg_uri = doc.get("CFPackageURI")
    return {
        "identifier": doc.get("identifier"),
        "title": doc.get("title"),
        "adoption_status": doc.get("adoptionStatus"),
        "framework_type": (doc.get("frameworkType") or "").strip() or None,
        "subject": doc.get("subject"),
        "creator": doc.get("creator"),
        "publisher": doc.get("publisher"),
        "version": doc.get("version"),
        "status_start_date": doc.get("statusStartDate"),
        "status_end_date": doc.get("statusEndDate"),
        "last_change_date_time": doc.get("lastChangeDateTime"),
        "case_version": doc.get("caseVersion"),
        "official_source_url": doc.get("officialSourceURL"),
        "uri": doc.get("uri"),
        "package_uri": pkg_uri.get("uri") if isinstance(pkg_uri, dict) else pkg_uri,
    }


async def _index(framework_uuid: str, server: Optional[str] = None) -> FrameworkIndex:
    srv = get_server(server)
    return index_for(await get_package(framework_uuid, srv.name), srv.name)



def _status_warning(idx: FrameworkIndex) -> list[str]:
    status = (idx.document.get("adoptionStatus") or "").strip()
    if status and status.lower() != "adopted":
        return [f"This framework's adoption status is '{status}'. Check for a current (Adopted) framework before aligning to it."]
    return []


# ── Frameworks ──────────────────────────────────────────────────────────────


@mcp.tool()
async def get_framework_packages(
    query: Optional[str] = None,
    framework_type: Optional[str] = None,
    include_deprecated: bool = False,
    server: Optional[str] = None,
) -> dict[str, Any]:
    """List Georgia SuitCASE frameworks (standards, course codes, CTAE clusters, career lists).

    Only Adopted/Draft frameworks are returned unless include_deprecated is true, so retired
    standards aren't used by mistake. Each result includes adoption_status.

    Args:
        query: Optional keyword matched against title, description, notes, subject and type.
        framework_type: Optional type, e.g. 'Standards', 'CourseCodes', 'Credential List'.
        include_deprecated: Also return Deprecated frameworks (default false).
        server: CASE server name from list_case_servers (default: georgia).
    """
    try:
        srv = get_server(server)
        docs = await get_documents(srv.name)
    except CaseAPIError as exc:
        return _err(exc)

    q = (query or "").strip().lower()
    ft = (framework_type or "").strip().lower()
    out, hidden = [], 0
    for d in docs:
        s = _doc_summary(d)
        if not include_deprecated and (s["adoption_status"] or "").strip().lower() == "deprecated":
            hidden += 1
            continue
        if ft and ft not in (s["framework_type"] or "").lower():
            continue
        if q:
            hay = " ".join(str(x or "") for x in (
                s["title"], d.get("description"), d.get("notes"), s["framework_type"],
                " ".join(s["subject"]) if isinstance(s["subject"], list) else s["subject"],
            )).lower()
            if q not in hay:
                continue
        out.append(s)
    out.sort(key=lambda s: (s["title"] or "").lower())
    result: dict[str, Any] = {
        "total_packages": len(out),
        "query": query,
        "framework_type": framework_type,
        "packages": out,
        "server": srv.name,
        "source": srv.base_url,
    }
    if hidden:
        result["deprecated_hidden"] = hidden
    return result


@mcp.tool()
async def get_framework_by_id(framework_uuid: str, server: Optional[str] = None) -> dict[str, Any]:
    """Summarize one framework: metadata, adoption status, item counts by type and grade, and its top level.

    Does not return every item (frameworks can hold thousands). Use get_children to walk the
    tree, get_framework_items to page through items, or search_standards to find items.

    Args:
        framework_uuid: Framework identifier from get_framework_packages.
        server: CASE server name from list_case_servers (default: georgia).
    """
    try:
        idx = await _index(framework_uuid, server)
    except CaseAPIError as exc:
        return _err(exc)

    type_counts: dict[str, int] = {}
    level_counts: dict[str, int] = {}
    for it in idx.items.values():
        t = (it.get("CFItemType") or "(none)").strip()
        type_counts[t] = type_counts.get(t, 0) + 1
        for lvl in it.get("educationLevel") or []:
            level_counts[lvl] = level_counts.get(lvl, 0) + 1
    assoc_counts: dict[str, int] = {}
    for a in idx.associations:
        t = a.get("associationType") or "(none)"
        assoc_counts[t] = assoc_counts.get(t, 0) + 1

    top = idx.child_ids(None)
    return {
        "framework": _doc_summary(idx.document),
        "warnings": _status_warning(idx),
        "total_items": len(idx.items),
        "item_types": dict(sorted(type_counts.items(), key=lambda kv: -kv[1])),
        "education_levels": dict(sorted(level_counts.items())),
        "association_types": dict(sorted(assoc_counts.items(), key=lambda kv: -kv[1])),
        "top_level": {"total": len(top), "items": [item_summary(idx.items[i]) for i in top[:50]]},
        "next_steps": "Use get_children(framework_uuid, item) to drill down, or search_standards to find items.",
    }


@mcp.tool()
async def get_framework_items(
    framework_uuid: str,
    item_type: Optional[str] = None,
    education_level: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    server: Optional[str] = None,
) -> dict[str, Any]:
    """Page through a framework's items, optionally filtered by item type and grade.

    Args:
        framework_uuid: Framework identifier.
        item_type: Exact CFItemType, e.g. 'Standard', 'Course', 'Content Standard' (see get_framework_by_id).
        education_level: Grade such as 'K', '1', '09' (matched against educationLevel).
        limit: Items per page (max 200). offset: Starting position.
        server: CASE server name from list_case_servers (default: georgia).
    """
    try:
        idx = await _index(framework_uuid, server)
    except CaseAPIError as exc:
        return _err(exc)
    ids = idx.filter(item_type, education_level)
    page, paging = _page(ids, limit, offset)
    return {
        "framework_title": idx.document.get("title"),
        "warnings": _status_warning(idx),
        "filters": {"item_type": item_type, "education_level": normalize_level(education_level)},
        **paging,
        "items": [item_summary(idx.items[i]) for i in page],
    }


# ── Navigating the tree ─────────────────────────────────────────────────────


def _resolve_one(idx: FrameworkIndex, item: str) -> tuple[str | None, dict[str, Any] | None]:
    ids = idx.resolve(item)
    if not ids:
        return None, {"error": f"No item with identifier or code '{item}' in this framework."}
    if len(ids) > 1:
        return None, {
            "error": f"Code '{item}' matches {len(ids)} items; pass an identifier instead.",
            "candidates": [item_summary(idx.items[i]) for i in ids],
        }
    return ids[0], None


@mcp.tool()
async def get_item(framework_uuid: str, item: str, server: Optional[str] = None) -> dict[str, Any]:
    """Get one standard by identifier or human code (e.g. '1.F.P.2', 'IT-IDT-1'), with its full statement,
    breadcrumb of parents, direct children, and non-hierarchy associations (crosswalks, prerequisites).

    Args:
        framework_uuid: Framework identifier.
        item: Item identifier (UUID or URI) or humanCodingScheme code.
        server: CASE server name from list_case_servers (default: georgia).
    """
    try:
        idx = await _index(framework_uuid, server)
    except CaseAPIError as exc:
        return _err(exc)
    iid, err = _resolve_one(idx, item)
    if err:
        return err
    kids = idx.child_ids(iid)
    other = [r for r in idx.related(iid) if r["association_type"] != "isChildOf"]
    return {
        "framework_title": idx.document.get("title"),
        "warnings": _status_warning(idx),
        "item": item_summary(idx.items[iid], full=True),
        "breadcrumb": [item_summary(idx.items[a]) for a in idx.ancestors(iid)],
        "children": {"total": len(kids), "items": [item_summary(idx.items[c]) for c in kids[:50]]},
        "associations": other[:50],
    }


@mcp.tool()
async def get_children(
    framework_uuid: str,
    item: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    server: Optional[str] = None,
) -> dict[str, Any]:
    """List the direct children of an item in teaching order (or the framework's top level if item is omitted).

    Args:
        framework_uuid: Framework identifier.
        item: Parent identifier or code. Omit for the top level.
        limit: Items per page (max 200). offset: Starting position.
        server: CASE server name from list_case_servers (default: georgia).
    """
    try:
        idx = await _index(framework_uuid, server)
    except CaseAPIError as exc:
        return _err(exc)
    parent_id = None
    if item:
        parent_id, err = _resolve_one(idx, item)
        if err:
            return err
    kids = idx.child_ids(parent_id)
    page, paging = _page(kids, limit, offset)
    return {
        "framework_title": idx.document.get("title"),
        "parent": item_summary(idx.items[parent_id]) if parent_id else {"title": idx.document.get("title"), "level": "framework"},
        **paging,
        "children": [dict(item_summary(idx.items[c]), has_children=bool(idx.child_ids(c))) for c in page],
    }


@mcp.tool()
async def get_ancestors(framework_uuid: str, item: str, server: Optional[str] = None) -> dict[str, Any]:
    """Return the path from the framework's top level down to an item (domain → strand → standard …).

    Args:
        framework_uuid: Framework identifier.
        item: Item identifier or code.
        server: CASE server name from list_case_servers (default: georgia).
    """
    try:
        idx = await _index(framework_uuid, server)
    except CaseAPIError as exc:
        return _err(exc)
    iid, err = _resolve_one(idx, item)
    if err:
        return err
    return {
        "framework_title": idx.document.get("title"),
        "item": item_summary(idx.items[iid]),
        "ancestors": [item_summary(idx.items[a]) for a in idx.ancestors(iid)],
    }


@mcp.tool()
async def get_associations(
    framework_uuid: str,
    item: str,
    association_type: Optional[str] = None,
    server: Optional[str] = None,
) -> dict[str, Any]:
    """List an item's CASE associations: isChildOf, exactMatchOf, isRelatedTo, precedes, isPartOf, etc.

    Args:
        framework_uuid: Framework identifier.
        item: Item identifier or code.
        association_type: Optional filter, e.g. 'exactMatchOf' or 'isRelatedTo'.
        server: CASE server name from list_case_servers (default: georgia).
    """
    try:
        idx = await _index(framework_uuid, server)
    except CaseAPIError as exc:
        return _err(exc)
    iid, err = _resolve_one(idx, item)
    if err:
        return err
    rel = idx.related(iid, association_type)
    return {
        "framework_title": idx.document.get("title"),
        "item": item_summary(idx.items[iid]),
        "total": len(rel),
        "associations": rel[:200],
    }


# ── Search & courses ────────────────────────────────────────────────────────


@mcp.tool()
async def search_standards(
    framework_uuid: str,
    query: str,
    education_level: Optional[str] = None,
    item_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    server: Optional[str] = None,
) -> dict[str, Any]:
    """Search a framework's items by code or keywords, ranked by relevance.

    Matches words rather than exact strings ("silent e" finds "silent-e"), ranks exact code
    matches and full-phrase matches first, and can filter by grade and item type.

    Args:
        framework_uuid: Framework identifier.
        query: Code (e.g. '1.F.P') or keywords (e.g. 'decode silent e', 'cybersecurity').
        education_level: Optional grade, e.g. 'K', '3', '09'.
        item_type: Optional CFItemType, e.g. 'Standard', 'Course'.
        limit: Results per page (max 200). offset: Starting position.
        server: CASE server name from list_case_servers (default: georgia).
    """
    if not query or not query.strip():
        return {"error": "query is required."}
    try:
        idx = await _index(framework_uuid, server)
    except CaseAPIError as exc:
        return _err(exc)
    ranked = idx.search(query, item_type, education_level)
    ids = [i for _, i in ranked]
    scores = {i: s for s, i in ranked}
    page, paging = _page(ids, limit, offset)
    return {
        "framework_title": idx.document.get("title"),
        "warnings": _status_warning(idx),
        "query": query.strip(),
        "filters": {"education_level": normalize_level(education_level), "item_type": item_type},
        **paging,
        "matches": [dict(item_summary(idx.items[i]), score=round(scores[i], 1)) for i in page],
    }


@mcp.tool()
async def get_courses_and_pathways(
    framework_uuid: str,
    filter_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    server: Optional[str] = None,
) -> dict[str, Any]:
    """List courses, pathways and clusters in a framework, using each item's CFItemType.

    Courses are items typed 'Course' or coded like Georgia course numbers (NN.NNNNN).
    Pathways and clusters come from item types containing 'pathway' or 'cluster'.

    Args:
        framework_uuid: Framework identifier.
        filter_type: Optional 'Course', 'Pathway' or 'Cluster'.
        limit: Results per page (max 200). offset: Starting position.
        server: CASE server name from list_case_servers (default: georgia).
    """
    try:
        idx = await _index(framework_uuid, server)
    except CaseAPIError as exc:
        return _err(exc)
    want = (filter_type or "").strip().lower().rstrip("s")
    found: list[tuple[str, str]] = []
    for iid, it in idx.items.items():
        itype = (it.get("CFItemType") or "").strip().lower()
        code = (it.get("humanCodingScheme") or "").strip()
        if itype == "course" or COURSE_CODE_REGEX.match(code):
            cat = "Course"
        elif "pathway" in itype:
            cat = "Pathway"
        elif "cluster" in itype:
            cat = "Cluster"
        else:
            continue
        if want and cat.lower() != want:
            continue
        found.append((cat, iid))
    found.sort(key=lambda t: (t[0], idx.items[t[1]].get("humanCodingScheme") or ""))
    page, paging = _page([i for _, i in found], limit, offset)
    cats = dict((i, c) for c, i in found)
    counts: dict[str, int] = {}
    for c, _ in found:
        counts[c] = counts.get(c, 0) + 1
    return {
        "framework_title": idx.document.get("title"),
        "warnings": _status_warning(idx),
        "filter_applied": filter_type,
        "counts": counts,
        **paging,
        "courses_and_pathways": [
            dict(item_summary(idx.items[i]), category=cats[i],
                 standards_count=len(idx.child_ids(i)) if cats[i] == "Course" else None)
            for i in page
        ],
    }


# ── Servers & cross-server links ────────────────────────────────────────────


@mcp.tool()
async def list_case_servers() -> dict[str, Any]:
    """List the CASE servers this tool can query (built-in Georgia servers plus any configured in GACASE_SERVERS).

    Use a server's name as the `server` argument of the other tools.
    """
    try:
        all_servers = servers()
        default = get_server(None).name
    except CaseAPIError as exc:
        return _err(exc)
    return {"default": default, "servers": [s.public() for s in all_servers.values()]}


@mcp.tool()
async def get_item_associations(item: str, server: Optional[str] = None) -> dict[str, Any]:
    """Every association touching one item across all frameworks on a server (CASE getCFItemAssociations).

    Useful on the Georgia CASE Council server ('georgiacase'), where cross-agency articulations
    and crosswalks live in frameworks separate from the standards themselves.

    Args:
        item: Item identifier (UUID) or CASE item URI.
        server: CASE server name from list_case_servers (default: georgia).
    """
    try:
        srv = get_server(server)
        data = await fetch_item_associations(item, srv.name)
    except CaseAPIError as exc:
        return _err(exc)
    assocs = data.get("CFAssociations", []) or []
    out = []
    iid = (item or "").strip().rstrip("/").rsplit("/", 1)[-1]
    for a in assocs:
        o, d = a.get("originNodeURI") or {}, a.get("destinationNodeURI") or {}
        oid = o.get("identifier") if isinstance(o, dict) else str(o).rsplit("/", 1)[-1]
        other = d if oid == iid else o
        out.append({
            "association_type": a.get("associationType"),
            "direction": "outgoing" if oid == iid else "incoming",
            "other_title": other.get("title") if isinstance(other, dict) else None,
            "other_identifier": other.get("identifier") if isinstance(other, dict) else None,
            "other_uri": other.get("uri") if isinstance(other, dict) else other,
            "framework_uri": (a.get("CFDocumentURI") or {}).get("uri") if isinstance(a.get("CFDocumentURI"), dict) else a.get("CFDocumentURI"),
            "sequence_number": a.get("sequenceNumber"),
        })
    item_info = data.get("CFItem") or {}
    return {
        "server": srv.name,
        "item": item_summary(item_info) if item_info else {"identifier": iid},
        "total": len(out),
        "associations": out[:200],
        "next_steps": "Follow other_uri with resolve_case_uri to read the linked item, even on another configured server.",
    }


@mcp.tool()
async def resolve_case_uri(uri: str) -> dict[str, Any]:
    """Read any CASE URI (item, framework document or association) on a configured server.

    Use this to follow a crosswalk or association link to another framework or another
    state's server. Only hosts listed by list_case_servers are fetched.

    Args:
        uri: A CASE API URI, e.g. https://case.georgiastandards.org/ims/case/v1p1/CFItems/<id>.
    """
    try:
        srv, data = await get_by_uri(uri)
    except CaseAPIError as exc:
        return _err(exc)
    if isinstance(data, dict) and data.get("CFDocument"):
        data = data["CFDocument"]
    kind = "unknown"
    if isinstance(data, dict):
        if "fullStatement" in data:
            kind = "CFItem"
            body: Any = item_summary(data, full=True)
        elif "adoptionStatus" in data or "CFPackageURI" in data:
            kind = "CFDocument"
            body = _doc_summary(data)
        elif "associationType" in data:
            kind = "CFAssociation"
            body = data
        else:
            body = data
    else:
        body = data
    return {"server": srv.name, "uri": uri, "type": kind, "result": body}


if __name__ == "__main__":
    mcp.run()
