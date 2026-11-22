"""HTTP transport: health check, MCP over streamable HTTP, and configuration."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from gacaseMCP import main as m
from tests.conftest import ELA

_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def http_client():
    """One app per process: FastMCP's session manager can only be started once."""
    m.configure_http()
    with TestClient(m.mcp.streamable_http_app()) as client:
        yield client


def _rpc(client: TestClient, method: str, params: dict | None = None, id_: int = 1):
    body = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    return client.post("/mcp", json=body, headers=_HEADERS)


def test_health_endpoint(http_client) -> None:
    r = http_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_tools_list_over_http(http_client) -> None:
    init = _rpc(http_client, "initialize", {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"},
    })
    assert init.status_code == 200
    r = _rpc(http_client, "tools/list", id_=2)
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert {"get_framework_packages", "get_item", "search_standards"} <= names


def test_tool_call_over_http(http_client) -> None:
    r = _rpc(http_client, "tools/call", {
        "name": "search_standards", "arguments": {"framework_uuid": ELA, "query": "silent e"},
    }, id_=3)
    assert r.status_code == 200
    text = r.json()["result"]["content"][0]["text"]
    assert "1.F.P.2" in text


def test_proxy_host_header_accepted_by_default(http_client) -> None:
    r = http_client.get("/health", headers={"Host": "gacase.example.com"})
    assert r.status_code == 200


async def test_allowed_hosts_enables_protection(monkeypatch) -> None:
    monkeypatch.setenv("GACASE_ALLOWED_HOSTS", "gacase.example.com, gacase.example.com:*")
    monkeypatch.setenv("GACASE_PORT", "9123")
    m.configure_http()
    try:
        sec = m.mcp.settings.transport_security
        assert sec.enable_dns_rebinding_protection is True
        assert sec.allowed_hosts == ["gacase.example.com", "gacase.example.com:*"]
        assert m.mcp.settings.port == 9123
    finally:
        monkeypatch.delenv("GACASE_ALLOWED_HOSTS")
        monkeypatch.delenv("GACASE_PORT")
        m.configure_http()


async def test_invalid_transport_exits(monkeypatch) -> None:
    monkeypatch.setenv("GACASE_TRANSPORT", "carrier-pigeon")
    with pytest.raises(SystemExit):
        m.main()
