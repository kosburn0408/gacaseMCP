"""Multi-server support: registry, tokens, cross-server associations and URI resolution."""

from __future__ import annotations

import json

import pytest
from httpx import Response

from gacaseMCP import client
from gacaseMCP import main as m
from tests.conftest import BASE, DOCUMENTS, ELA

pytestmark = pytest.mark.asyncio

SHARED = "https://shared.example.test/ims/case/v1p1"
ROSETTA = "https://rosetta.example.test/ims/case/v1p1"


@pytest.fixture
def extra_servers(monkeypatch: pytest.MonkeyPatch, case_api):
    monkeypatch.setenv("GACASE_SERVERS", json.dumps({
        "georgiacase": {"base_url": SHARED},
        "rosetta": {"base_url": ROSETTA, "description": "CGLT Rosetta", "token_env": "ROSETTA_TOKEN"},
    }))
    monkeypatch.setenv("ROSETTA_TOKEN", "secret-token")
    shared_docs = {"CFDocuments": [dict(DOCUMENTS["CFDocuments"][0], title="Shared copy of ELA")]}
    case_api.get(f"{SHARED}/CFDocuments").mock(return_value=Response(200, json=shared_docs))
    case_api.get(f"{SHARED}/CFItemAssociations/1fp2").mock(return_value=Response(200, json={
        "CFItem": {"identifier": "1fp2", "humanCodingScheme": "1.F.P.2", "fullStatement": "Fixture.", "CFItemType": "Standard"},
        "CFAssociations": [{
            "associationType": "isRelatedTo",
            "originNodeURI": {"identifier": "1fp2", "uri": f"{BASE}/CFItems/1fp2", "title": "1.F.P.2"},
            "destinationNodeURI": {"identifier": "tcsg-1", "uri": f"{ROSETTA}/CFItems/tcsg-1", "title": "TCSG READ 1"},
            "CFDocumentURI": {"uri": f"{SHARED}/CFDocuments/articulation"},
        }],
    }))
    case_api.get(f"{ROSETTA}/CFItems/tcsg-1").mock(return_value=Response(200, json={
        "identifier": "tcsg-1", "uri": f"{ROSETTA}/CFItems/tcsg-1", "humanCodingScheme": "READ 1",
        "fullStatement": "Fixture postsecondary reading competency.", "CFItemType": "Competency"}))
    case_api.get(f"{ROSETTA}/CFDocuments").mock(return_value=Response(401))
    return case_api


async def test_list_servers(extra_servers) -> None:
    r = await m.list_case_servers()
    names = {s["name"] for s in r["servers"]}
    assert {"georgia", "georgiacase", "rosetta"} <= names
    ros = next(s for s in r["servers"] if s["name"] == "rosetta")
    assert ros["authenticated"] is True and "secret-token" not in json.dumps(r)


async def test_server_param_routes_requests(extra_servers) -> None:
    r = await m.get_framework_packages(server="georgiacase")
    assert r["server"] == "georgiacase" and r["packages"][0]["title"] == "Shared copy of ELA"


async def test_bearer_token_sent(extra_servers) -> None:
    await m.resolve_case_uri(f"{ROSETTA}/CFItems/tcsg-1")
    req = extra_servers.calls.last.request
    assert req.headers["Authorization"] == "Bearer secret-token"


async def test_auth_error_message(extra_servers) -> None:
    r = await m.get_framework_packages(server="rosetta")
    assert "refused access" in r["error"] and "ROSETTA_TOKEN" in r["error"]


async def test_item_associations_and_follow_link(extra_servers) -> None:
    r = await m.get_item_associations("1fp2", server="georgiacase")
    link = r["associations"][0]
    assert link["association_type"] == "isRelatedTo" and link["direction"] == "outgoing"
    followed = await m.resolve_case_uri(link["other_uri"])
    assert followed["server"] == "rosetta" and followed["result"]["code"] == "READ 1"


async def test_resolve_refuses_unconfigured_host() -> None:
    r = await m.resolve_case_uri("https://evil.example.test/ims/case/v1p1/CFItems/x")
    assert "not a configured CASE server" in r["error"]


async def test_unknown_server() -> None:
    r = await m.get_framework_by_id(ELA, server="nowhere")
    assert "Unknown CASE server" in r["error"]


async def test_same_framework_id_on_two_servers_not_mixed(extra_servers) -> None:
    from gacaseMCP.framework import index_for
    from tests.conftest import ELA_PKG

    a = index_for(ELA_PKG, "georgia")
    b = index_for(dict(ELA_PKG), "georgiacase")
    assert a is not b


async def test_https_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GACASE_SERVERS", json.dumps({"bad": {"base_url": "http://insecure.test/ims/case/v1p1"}}))
    with pytest.raises(client.CaseAPIError, match="https"):
        client.servers()
