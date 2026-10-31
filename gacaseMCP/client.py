"""Cached client for a CASE 1.1 REST API (default: Georgia's SuitCASE).

Framework packages can be several megabytes, so each one is downloaded once
and kept in memory for ``GACASE_CACHE_TTL`` seconds (default 24 hours).

Configuration (environment variables):
- ``GACASE_BASE_URL``   default ``https://case.georgiastandards.org/ims/case/v1p1``
- ``GACASE_CACHE_TTL``  seconds to keep downloaded data (default 86400; 0 disables)
- ``GACASE_TIMEOUT``    request timeout in seconds (default 60)
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://case.georgiastandards.org/ims/case/v1p1"
USER_AGENT = "gacaseMCP/1.1 (+https://github.com/kosburn0408/gacaseMCP)"
# Ask for every framework in one page; Georgia has ~60. Raise if a server pages smaller.
DOCUMENTS_LIMIT = 1000


class CaseAPIError(Exception):
    """A CASE API request failed; the message is safe to show to a user."""


def base_url() -> str:
    return os.environ.get("GACASE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _ttl() -> float:
    return float(os.environ.get("GACASE_CACHE_TTL", "86400"))


def _timeout() -> float:
    return float(os.environ.get("GACASE_TIMEOUT", "60"))


_cache: dict[str, tuple[float, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}


def clear_cache() -> None:
    _cache.clear()


async def _get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    key = f"{base_url()}{path}?{sorted((params or {}).items())}"
    ttl = _ttl()
    hit = _cache.get(key)
    if hit and ttl > 0 and time.time() - hit[0] < ttl:
        return hit[1]

    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        hit = _cache.get(key)
        if hit and ttl > 0 and time.time() - hit[0] < ttl:
            return hit[1]
        url = f"{base_url()}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=_timeout(),
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url, params=params)
        except httpx.RequestError as exc:
            raise CaseAPIError(f"Could not reach the CASE API at {url}: {exc.__class__.__name__}") from exc
        if resp.status_code == 404:
            raise CaseAPIError(f"Not found: {url}")
        if resp.status_code >= 400:
            raise CaseAPIError(f"CASE API returned HTTP {resp.status_code} for {url}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise CaseAPIError(f"CASE API returned non-JSON content for {url}") from exc
        _cache[key] = (time.time(), data)
        return data


async def get_documents() -> list[dict[str, Any]]:
    data = await _get_json("/CFDocuments", {"limit": DOCUMENTS_LIMIT})
    if isinstance(data, dict):
        return list(data.get("CFDocuments", []))
    if isinstance(data, list):
        return data
    raise CaseAPIError("Unexpected CFDocuments response shape")


async def get_package(framework_uuid: str) -> dict[str, Any]:
    uuid = (framework_uuid or "").strip()
    if not uuid:
        raise CaseAPIError("framework_uuid is required.")
    data = await _get_json(f"/CFPackages/{uuid}")
    if not isinstance(data, dict) or "CFDocument" not in data:
        raise CaseAPIError(f"Unexpected CFPackage response for {uuid}")
    return data
