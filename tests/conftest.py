"""Shared fixtures: synthetic CASE responses (structure mirrors Georgia's SuitCASE API)."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from gacaseMCP import client

BASE = "https://case.example.test/ims/case/v1p1"
ELA = "ela-0000-current"
OLD = "ela-0000-retired"
CTAE = "ctae-0000-digital"


def _item(iid, code, itype, stmt, levels):
    return {"identifier": iid, "uri": f"{BASE}/CFItems/{iid}", "humanCodingScheme": code,
            "CFItemType": itype, "fullStatement": stmt, "educationLevel": levels}


def _child(aid, child, parent, seq, parent_is_doc=False):
    dest = {"identifier": parent, "uri": f"{BASE}/{'CFDocuments' if parent_is_doc else 'CFItems'}/{parent}", "title": parent}
    return {"identifier": aid, "associationType": "isChildOf", "sequenceNumber": seq,
            "originNodeURI": {"identifier": child, "uri": f"{BASE}/CFItems/{child}", "title": child},
            "destinationNodeURI": dest}


DOCUMENTS = {"CFDocuments": [
    {"identifier": ELA, "uri": f"{BASE}/CFDocuments/{ELA}", "title": "English Language Arts - Fixture Current",
     "adoptionStatus": "Adopted", "frameworkType": "Standards", "creator": "Fixture", "CFPackageURI": {"uri": f"{BASE}/CFPackages/{ELA}"}},
    {"identifier": OLD, "uri": f"{BASE}/CFDocuments/{OLD}", "title": "English Language Arts - Fixture Retired",
     "adoptionStatus": "Deprecated", "frameworkType": "Standards", "creator": "Fixture"},
    {"identifier": CTAE, "uri": f"{BASE}/CFDocuments/{CTAE}", "title": "CTAE Fixture: Digital Technology",
     "adoptionStatus": "Adopted", "frameworkType": "CourseCodes ", "creator": "Fixture"},
    {"identifier": "no-type", "uri": f"{BASE}/CFDocuments/no-type", "title": "Fixture Without Type",
     "adoptionStatus": "Adopted", "creator": "Fixture"},
]}

ELA_PKG = {
    "CFDocument": DOCUMENTS["CFDocuments"][0],
    "CFItems": [
        _item("kf", "K.F", "Domain", "**Foundations** Fixture domain.", ["KG"]),
        _item("kfp", "K.F.P", "Big Idea", "**Phonics** Fixture big idea.", ["KG"]),
        _item("kfp1", "K.F.P.1", "Standard", "**Phoneme-Grapheme Correspondences** Fixture letter-sound standard.", ["KG"]),
        _item("kfp2", "K.F.P.2", "Standard", "**Decoding words** Fixture: decode CVC words.", ["KG"]),
        _item("kfp21", "K.F.P.2.1", "Skill", "Fixture: blend sounds to decode CVC words.", ["KG"]),
        _item("1f", "1.F", "Domain", "**Foundations** Fixture grade 1 domain.", ["01"]),
        _item("1fp2", "1.F.P.2", "Standard", "**Decoding words** Fixture: decode words with silent-e and vowel teams.", ["01"]),
        _item("dupA", "X.1", "Standard", "Fixture duplicate code A.", ["01"]),
        _item("dupB", "X.1", "Standard", "Fixture duplicate code B.", ["01"]),
    ],
    "CFAssociations": [
        _child("a1", "kf", ELA, 1, parent_is_doc=True),
        _child("a2", "1f", ELA, 2, parent_is_doc=True),
        _child("a3", "kfp", "kf", 3),
        _child("a4", "kfp2", "kfp", 2),
        _child("a5", "kfp1", "kfp", 1),
        _child("a6", "kfp21", "kfp2", 1),
        _child("a7", "1fp2", "1f", 1),
        {"identifier": "x1", "associationType": "exactMatchOf",
         "originNodeURI": {"identifier": "1fp2", "uri": f"{BASE}/CFItems/1fp2", "title": "1.F.P.2"},
         "destinationNodeURI": {"identifier": "ext-ccss", "uri": "https://example.test/ccss/RF.1.3.c", "title": "CCSS.ELA-LITERACY.RF.1.3.C"}},
    ],
}

CTAE_PKG = {
    "CFDocument": DOCUMENTS["CFDocuments"][2],
    "CFItems": [
        _item("c1", "11.41500", "Course", "Introduction to Digital Technology", ["09", "10", "11", "12"]),
        _item("s1", "IT-IDT-1", "Content Standard", "Demonstrate employability skills. Fixture mentions a career pathway.", ["09"]),
        _item("e1", "IT-IDT-1.1", "Element", "Communicate effectively. Fixture.", ["09"]),
        _item("p1", "PW-1", "Pathway", "Fixture Programming pathway.", ["09"]),
    ],
    "CFAssociations": [_child("b1", "c1", CTAE, 1, parent_is_doc=True), _child("b2", "s1", "c1", 1), _child("b3", "e1", "s1", 1)],
}


@pytest.fixture(autouse=True)
def case_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GACASE_BASE_URL", BASE)
    client.clear_cache()
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{BASE}/CFDocuments").mock(return_value=Response(200, json=DOCUMENTS))
        router.get(f"{BASE}/CFPackages/{ELA}").mock(return_value=Response(200, json=ELA_PKG))
        router.get(f"{BASE}/CFPackages/{CTAE}").mock(return_value=Response(200, json=CTAE_PKG))
        router.get(f"{BASE}/CFPackages/missing").mock(return_value=Response(404))
        yield router
