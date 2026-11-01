"""Cached client for one or more CASE 1.1 REST APIs.

Built-in servers:
- ``georgia``     Georgia's SuitCASE (GaDOE K-12 standards, CTAE, course codes)
- ``georgiacase`` Georgia CASE Council shared server (cross-agency frameworks,
                  High-Demand Career List, SOC reference data)

Add more (another state, Common Good Learning Tools' Rosetta, a district
Satchel) with ``GACASE_SERVERS``, a JSON object such as::

    {"rosetta": {"base_url": "https://<host>/ims/case/v1p1",
                 "description": "CGLT Rosetta",
                 "token_env": "ROSETTA_TOKEN"}}

``token_env`` names an environment variable holding a bearer token, sent as
``Authorization: Bearer <token>``. Tokens are never read from the JSON itself.

Framework packages can be several megabytes, so each response is kept in
memory for ``GACASE_CACHE_TTL`` seconds (default 24 hours).

Other settings: ``GACASE_BASE_URL`` (overrides the ``georgia`` server's URL),
``GACASE_DEFAULT_SERVER`` (default ``georgia``), ``GACASE_TIMEOUT`` (seconds).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

USER_AGENT = "gacaseMCP/1.2 (+https://github.com/kosburn0408/gacaseMCP)"
DOCUMENTS_LIMIT = 1000

BUILTIN_SERVERS: dict[str, dict[str, str]] = {
    "georgia": {
        "base_url": "https://case.georgiastandards.org/ims/case/v1p1",
        "description": "Georgia SuitCASE (GaDOE): K-12 standards, CTAE clusters, course codes, career lists.",
    },
    "georgiacase": {
        "base_url": "https://georgiacase.org/ims/case/v1p1",
        "description": "Georgia CASE Council shared server: cross-agency frameworks (GaDOE, TCSG, USG institutions), "
                       "High-Demand Career List, SOC reference data.",
    },
}


class CaseAPIError(Exception):
    """A CASE API request failed; the message is safe to show to a user."""


@dataclass(frozen=True)
class Server:
    name: str
    base_url: str
    description: str = ""
    token_env: str | None = None

    @property
    def host(self) -> str:
        return urlparse(self.base_url).netloc.lower()

    def headers(self) -> dict[str, str]:
        h = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if self.token_env:
            token = os.environ.get(self.token_env, "").strip()
            if token:
                h["Authorization"] = f"Bearer {token}"
        return h

    def public(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "description": self.description,
            "authenticated": bool(self.token_env and os.environ.get(self.token_env, "").strip()),
            "token_env": self.token_env,
        }


def servers() -> dict[str, Server]:
    cfg = {k: dict(v) for k, v in BUILTIN_SERVERS.items()}
    if os.environ.get("GACASE_BASE_URL"):
        cfg["georgia"]["base_url"] = os.environ["GACASE_BASE_URL"]
    extra = os.environ.get("GACASE_SERVERS", "").strip()
    if extra:
        try:
            parsed = json.loads(extra)
        except ValueError as exc:
            raise CaseAPIError(f"GACASE_SERVERS is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise CaseAPIError("GACASE_SERVERS must be a JSON object of name → settings.")
        for name, conf in parsed.items():
            if not isinstance(conf, dict) or not conf.get("base_url"):
                raise CaseAPIError(f"GACASE_SERVERS entry '{name}' needs a base_url.")
            cfg[name.strip().lower()] = {**cfg.get(name.strip().lower(), {}), **conf}
    out = {}
    for name, conf in cfg.items():
        url = conf["base_url"].rstrip("/")
        if not url.startswith("https://") and not url.startswith("http://localhost"):
            raise CaseAPIError(f"Server '{name}' must use https.")
        out[name] = Server(name, url, conf.get("description", ""), conf.get("token_env"))
    return out


def default_server() -> str:
    return os.environ.get("GACASE_DEFAULT_SERVER", "georgia").strip().lower()


def get_server(name: str | None) -> Server:
    all_servers = servers()
    key = (name or default_server()).strip().lower()
    if key not in all_servers:
        raise CaseAPIError(f"Unknown CASE server '{name}'. Available: {', '.join(sorted(all_servers))}.")
    return all_servers[key]


def base_url(server: str | None = None) -> str:
    return get_server(server).base_url


def _ttl() -> float:
    return float(os.environ.get("GACASE_CACHE_TTL", "86400"))


def _timeout() -> float:
    return float(os.environ.get("GACASE_TIMEOUT", "60"))


_cache: dict[str, tuple[float, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}


def clear_cache() -> None:
    _cache.clear()


async def _fetch(srv: Server, url: str, params: dict[str, Any] | None = None) -> Any:
    key = f"{url}?{sorted((params or {}).items())}"
    ttl = _ttl()
    hit = _cache.get(key)
    if hit and ttl > 0 and time.time() - hit[0] < ttl:
        return hit[1]
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        hit = _cache.get(key)
        if hit and ttl > 0 and time.time() - hit[0] < ttl:
            return hit[1]
        try:
            async with httpx.AsyncClient(timeout=_timeout(), headers=srv.headers(), follow_redirects=True) as client:
                resp = await client.get(url, params=params)
        except httpx.RequestError as exc:
            raise CaseAPIError(f"Could not reach CASE server '{srv.name}' ({url}): {exc.__class__.__name__}") from exc
        if resp.status_code == 404:
            raise CaseAPIError(f"Not found on '{srv.name}': {url}")
        if resp.status_code in (401, 403):
            hint = f" Set {srv.token_env}." if srv.token_env else " This server may need an access token (token_env)."
            raise CaseAPIError(f"CASE server '{srv.name}' refused access (HTTP {resp.status_code}).{hint}")
        if resp.status_code >= 400:
            raise CaseAPIError(f"CASE server '{srv.name}' returned HTTP {resp.status_code} for {url}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise CaseAPIError(f"CASE server '{srv.name}' returned non-JSON content for {url}") from exc
        _cache[key] = (time.time(), data)
        return data


async def _get_json(path: str, params: dict[str, Any] | None = None, server: str | None = None) -> Any:
    srv = get_server(server)
    return await _fetch(srv, f"{srv.base_url}{path}", params)


async def get_documents(server: str | None = None) -> list[dict[str, Any]]:
    data = await _get_json("/CFDocuments", {"limit": DOCUMENTS_LIMIT}, server)
    if isinstance(data, dict):
        return list(data.get("CFDocuments", []))
    if isinstance(data, list):
        return data
    raise CaseAPIError("Unexpected CFDocuments response shape")


async def get_package(framework_uuid: str, server: str | None = None) -> dict[str, Any]:
    uuid = (framework_uuid or "").strip()
    if not uuid:
        raise CaseAPIError("framework_uuid is required.")
    data = await _get_json(f"/CFPackages/{uuid}", None, server)
    if not isinstance(data, dict) or "CFDocument" not in data:
        raise CaseAPIError(f"Unexpected CFPackage response for {uuid}")
    return data


async def get_item_associations(item_id: str, server: str | None = None) -> dict[str, Any]:
    """CASE getCFItemAssociations: every association touching an item, across the server's frameworks."""
    iid = (item_id or "").strip().rstrip("/").rsplit("/", 1)[-1]
    if not iid:
        raise CaseAPIError("item identifier is required.")
    data = await _get_json(f"/CFItemAssociations/{iid}", None, server)
    if not isinstance(data, dict):
        raise CaseAPIError(f"Unexpected CFItemAssociations response for {iid}")
    return data


def server_for_uri(uri: str) -> Server:
    """Match a CASE URI to a configured server by host. Only configured hosts are fetched."""
    host = urlparse(uri or "").netloc.lower()
    for srv in servers().values():
        if srv.host == host:
            return srv
    raise CaseAPIError(
        f"'{host or uri}' is not a configured CASE server. Add it to GACASE_SERVERS to follow links there."
    )


async def get_by_uri(uri: str) -> tuple[Server, Any]:
    """Dereference a CASE URI (CFItems, CFDocuments, CFAssociations) on a configured server."""
    u = (uri or "").strip()
    parsed = urlparse(u)
    if parsed.scheme not in ("https", "http") or "/ims/case/" not in parsed.path:
        raise CaseAPIError("Expected a CASE API URI such as https://<host>/ims/case/v1p1/CFItems/<id>.")
    srv = server_for_uri(u)
    return srv, await _fetch(srv, u)
