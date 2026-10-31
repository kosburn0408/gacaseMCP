"""Tool behavior against synthetic CASE responses."""

from __future__ import annotations

import pytest

from gacaseMCP import main as m
from tests.conftest import BASE, CTAE, ELA

pytestmark = pytest.mark.asyncio


async def test_list_hides_deprecated_and_reports_status() -> None:
    r = await m.get_framework_packages()
    titles = [p["title"] for p in r["packages"]]
    assert "English Language Arts - Fixture Retired" not in titles
    assert r["deprecated_hidden"] == 1
    assert all("adoption_status" in p for p in r["packages"])
    r2 = await m.get_framework_packages(include_deprecated=True)
    assert r2["total_packages"] == 4


async def test_framework_type_trailing_space() -> None:
    r = await m.get_framework_packages(framework_type="CourseCodes")
    assert [p["identifier"] for p in r["packages"]] == [CTAE]
    assert r["packages"][0]["framework_type"] == "CourseCodes"


async def test_documents_requested_with_limit(case_api) -> None:
    await m.get_framework_packages()
    call = case_api.calls.last.request
    assert "limit=1000" in str(call.url)


async def test_framework_summary_not_full_dump() -> None:
    r = await m.get_framework_by_id(ELA)
    assert r["framework"]["adoption_status"] == "Adopted"
    assert r["total_items"] == 9
    assert r["item_types"]["Standard"] == 5
    assert [i["code"] for i in r["top_level"]["items"]] == ["K.F", "1.F"]
    assert "CFItems" not in r


async def test_packages_are_cached(case_api) -> None:
    await m.get_framework_by_id(ELA)
    await m.search_standards(ELA, "decode")
    await m.get_children(ELA, "K.F.P")
    pkg_calls = [c for c in case_api.calls if "/CFPackages/" in str(c.request.url)]
    assert len(pkg_calls) == 1


async def test_children_in_sequence_order() -> None:
    r = await m.get_children(ELA, "K.F.P")
    assert [c["code"] for c in r["children"]] == ["K.F.P.1", "K.F.P.2"]
    assert r["children"][1]["has_children"] is True


async def test_get_item_by_code_with_breadcrumb_and_crosswalk() -> None:
    r = await m.get_item(ELA, "1.F.P.2")
    assert r["item"]["identifier"] == "1fp2"
    assert [b["code"] for b in r["breadcrumb"]] == ["1.F"]
    xw = r["associations"][0]
    assert xw["association_type"] == "exactMatchOf"
    assert xw["other"]["title"] == "CCSS.ELA-LITERACY.RF.1.3.C"


async def test_duplicate_codes_return_candidates() -> None:
    r = await m.get_item(ELA, "X.1")
    assert "error" in r and len(r["candidates"]) == 2


async def test_ancestors() -> None:
    r = await m.get_ancestors(ELA, "K.F.P.2.1")
    assert [a["code"] for a in r["ancestors"]] == ["K.F", "K.F.P", "K.F.P.2"]


async def test_search_matches_words_and_ranks() -> None:
    r = await m.search_standards(ELA, "silent e")
    assert r["matches"][0]["code"] == "1.F.P.2"
    r2 = await m.search_standards(ELA, "decode", education_level="K")
    codes = [x["code"] for x in r2["matches"]]
    assert codes and all(c.startswith("K.") for c in codes)
    assert codes[0] == "K.F.P.2"  # standard ranks above its sub-skill
    r3 = await m.search_standards(ELA, "K.F.P.2")
    assert r3["matches"][0]["code"] == "K.F.P.2"


async def test_paging() -> None:
    r = await m.get_framework_items(ELA, item_type="Standard", limit=2)
    assert r["total"] == 5 and len(r["items"]) == 2 and r["next_offset"] == 2


async def test_courses_use_item_types_not_text() -> None:
    r = await m.get_courses_and_pathways(CTAE)
    cats = {c["code"]: c["category"] for c in r["courses_and_pathways"]}
    assert cats == {"11.41500": "Course", "PW-1": "Pathway"}  # 'IT-IDT-1' mentions 'pathway' but isn't one
    course = next(c for c in r["courses_and_pathways"] if c["category"] == "Course")
    assert course["standards_count"] == 1


async def test_deprecated_framework_warns() -> None:
    # Retired framework isn't mocked as a package; check the warning logic via a status override.
    from gacaseMCP.framework import FrameworkIndex
    from tests.conftest import ELA_PKG

    pkg = dict(ELA_PKG, CFDocument=dict(ELA_PKG["CFDocument"], adoptionStatus="Deprecated"))
    assert m._status_warning(FrameworkIndex.build(pkg))


async def test_not_found_is_clean_error() -> None:
    r = await m.get_framework_by_id("missing")
    assert r["error"].startswith("Not found")
