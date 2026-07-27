import re
import httpx
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server for Georgia SuitCASE
mcp = FastMCP("gacaseMCP")

BASE_URL = "https://case.georgiastandards.org/ims/case/v1p1"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "gacaseMCP/1.0 (Georgia Department of Education SuitCASE MCP Server)"
}
COURSE_CODE_REGEX = re.compile(r'\b\d{2}\.\d{5}\b')


@mcp.tool()
async def get_framework_packages(
    query: Optional[str] = None,
    framework_type: Optional[str] = None
) -> Dict[str, Any]:
    """Search or list top-level framework documents from Georgia SuitCASE API (e.g., CTAE Pathways, High Demand Careers, Course Guides, Subject Standards).

    Args:
        query: Optional keyword to filter framework documents by title, description, or notes.
        framework_type: Optional framework type to filter by (e.g., 'Standards', 'CourseCodes', 'High Demand Career List Regions').

    Returns:
        List of framework titles, identifiers (UUIDs), subject/framework types, publication dates, and metadata.
    """
    url = f"{BASE_URL}/CFDocuments"
    try:
        async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error {e.response.status_code} while fetching framework packages: {str(e)}"}
    except httpx.RequestError as e:
        return {"error": f"Request error while fetching framework packages: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error while fetching framework packages: {str(e)}"}

    raw_docs = data.get("CFDocuments", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    parsed_docs = []
    for doc in raw_docs:
        title = doc.get("title") or ""
        desc = doc.get("description") or ""
        notes = doc.get("notes") or ""
        ftype = doc.get("frameworkType") or ""

        # Filter by framework_type if provided
        if framework_type and framework_type.lower() not in ftype.lower():
            continue

        # Filter by query if provided
        if query:
            q_lower = query.lower()
            if (q_lower not in title.lower() and 
                q_lower not in desc.lower() and 
                q_lower not in notes.lower() and 
                q_lower not in ftype.lower()):
                continue

        package_uri_val = doc.get("CFPackageURI")
        pkg_uri = package_uri_val.get("uri") if isinstance(package_uri_val, dict) else package_uri_val

        parsed_docs.append({
            "identifier": doc.get("identifier"),
            "title": title,
            "framework_type": ftype,
            "creator": doc.get("creator"),
            "publisher": doc.get("publisher"),
            "last_change_date_time": doc.get("lastChangeDateTime"),
            "case_version": doc.get("caseVersion"),
            "description": desc,
            "notes": notes,
            "uri": doc.get("uri"),
            "package_uri": pkg_uri
        })

    return {
        "total_packages": len(parsed_docs),
        "query": query,
        "framework_type": framework_type,
        "packages": parsed_docs
    }


@mcp.tool()
async def get_framework_by_id(framework_uuid: str) -> Dict[str, Any]:
    """Pull the complete standard framework bundle by UUID from Georgia SuitCASE API.

    Args:
        framework_uuid: UUID identifier of the framework package (e.g., '00fcf0e2-b9c3-11e7-a4ad-47f36833e889').

    Returns:
        Parsed payload returning document metadata (CFDocument), list of competencies/standards (CFItems), and relationships (CFAssociations).
    """
    if not framework_uuid or not framework_uuid.strip():
        return {"error": "framework_uuid parameter is required and cannot be empty."}

    uuid_clean = framework_uuid.strip()
    url = f"{BASE_URL}/CFPackages/{uuid_clean}"

    try:
        async with httpx.AsyncClient(timeout=45.0, headers=HEADERS) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return {"error": f"Framework UUID '{uuid_clean}' not found (HTTP 404)."}
            response.raise_for_status()
            pkg = response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error {e.response.status_code} while fetching framework '{uuid_clean}': {str(e)}"}
    except httpx.RequestError as e:
        return {"error": f"Request error while fetching framework '{uuid_clean}': {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error while fetching framework '{uuid_clean}': {str(e)}"}

    if not isinstance(pkg, dict):
        return {"error": f"Invalid payload structure returned for framework UUID '{uuid_clean}'."}

    doc = pkg.get("CFDocument", {})
    items = pkg.get("CFItems", [])
    assocs = pkg.get("CFAssociations", [])

    parsed_doc = {
        "identifier": doc.get("identifier"),
        "title": doc.get("title"),
        "framework_type": doc.get("frameworkType"),
        "creator": doc.get("creator"),
        "publisher": doc.get("publisher"),
        "last_change_date_time": doc.get("lastChangeDateTime"),
        "case_version": doc.get("caseVersion"),
        "description": doc.get("description"),
        "notes": doc.get("notes"),
        "uri": doc.get("uri")
    }

    parsed_items = []
    for item in items:
        code = item.get("humanCodingScheme") or item.get("fullStatementCode") or ""
        parsed_items.append({
            "identifier": item.get("identifier"),
            "code": code,
            "statement": item.get("fullStatement"),
            "type": item.get("CFItemType"),
            "education_level": item.get("educationLevel"),
            "status_start_date": item.get("statusStartDate"),
            "extensions": item.get("extensions")
        })

    parsed_assocs = []
    for assoc in assocs:
        origin = assoc.get("originNodeURI", {})
        dest = assoc.get("destinationNodeURI", {})
        origin_id = origin.get("identifier") if isinstance(origin, dict) else origin
        dest_id = dest.get("identifier") if isinstance(dest, dict) else dest

        parsed_assocs.append({
            "identifier": assoc.get("identifier"),
            "association_type": assoc.get("associationType"),
            "origin_identifier": origin_id,
            "destination_identifier": dest_id
        })

    return {
        "framework_uuid": uuid_clean,
        "CFDocument": parsed_doc,
        "total_items": len(parsed_items),
        "CFItems": parsed_items,
        "total_associations": len(parsed_assocs),
        "CFAssociations": parsed_assocs
    }


@mcp.tool()
async def get_courses_and_pathways(
    framework_uuid: str,
    filter_type: Optional[str] = None
) -> Dict[str, Any]:
    """Filter items within a framework package to extract course codes, course names, CTAE clusters, and CTAE pathways.

    Args:
        framework_uuid: UUID identifier of the framework package.
        filter_type: Optional filter string to narrow results ('Course', 'Pathway', 'Cluster', 'CTAE', etc.).

    Returns:
        Structured payload containing matching course codes, names, CTAE clusters, and CTAE pathways.
    """
    if not framework_uuid or not framework_uuid.strip():
        return {"error": "framework_uuid parameter is required and cannot be empty."}

    uuid_clean = framework_uuid.strip()
    url = f"{BASE_URL}/CFPackages/{uuid_clean}"

    try:
        async with httpx.AsyncClient(timeout=45.0, headers=HEADERS) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return {"error": f"Framework UUID '{uuid_clean}' not found (HTTP 404)."}
            response.raise_for_status()
            pkg = response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error {e.response.status_code} while fetching framework '{uuid_clean}': {str(e)}"}
    except httpx.RequestError as e:
        return {"error": f"Request error while fetching framework '{uuid_clean}': {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error while fetching framework '{uuid_clean}': {str(e)}"}

    if not isinstance(pkg, dict):
        return {"error": f"Invalid payload structure returned for framework UUID '{uuid_clean}'."}

    doc = pkg.get("CFDocument", {})
    items = pkg.get("CFItems", [])

    if not items:
        return {
            "framework_uuid": uuid_clean,
            "framework_title": doc.get("title"),
            "filter_applied": filter_type,
            "total_matches": 0,
            "courses_and_pathways": [],
            "message": "Framework package contained no items."
        }

    results = []
    norm_filter = filter_type.strip().lower() if filter_type else None

    for item in items:
        code = item.get("humanCodingScheme") or item.get("fullStatementCode") or ""
        stmt = item.get("fullStatement") or ""
        itype = item.get("CFItemType") or ""
        ed_level = item.get("educationLevel")

        is_course_code = bool(COURSE_CODE_REGEX.search(code)) or (itype.lower() == 'course')
        is_pathway = ('pathway' in stmt.lower()) or ('pathway' in itype.lower())
        is_cluster = ('cluster' in stmt.lower()) or ('cluster' in itype.lower())
        is_ctae = ('ctae' in stmt.lower()) or ('ctae' in doc.get("title", "").lower()) or is_pathway or is_cluster

        categories = []
        if is_course_code:
            categories.append("Course")
        if is_pathway:
            categories.append("Pathway")
        if is_cluster:
            categories.append("Cluster")
        if is_ctae:
            categories.append("CTAE")
        if not categories:
            categories.append(itype or "Other")

        if norm_filter:
            match = False
            if norm_filter in ['course', 'courses'] and is_course_code:
                match = True
            elif norm_filter in ['pathway', 'pathways'] and is_pathway:
                match = True
            elif norm_filter in ['cluster', 'clusters'] and is_cluster:
                match = True
            elif norm_filter == 'ctae' and is_ctae:
                match = True
            elif any(norm_filter in cat.lower() for cat in categories):
                match = True
            elif norm_filter in code.lower() or norm_filter in stmt.lower() or norm_filter in itype.lower():
                match = True

            if not match:
                continue

        results.append({
            "identifier": item.get("identifier"),
            "code": code,
            "name": stmt,
            "item_type": itype,
            "categories": categories,
            "is_course_code": is_course_code,
            "education_level": ed_level,
            "status_start_date": item.get("statusStartDate"),
            "extensions": item.get("extensions")
        })

    return {
        "framework_uuid": uuid_clean,
        "framework_title": doc.get("title"),
        "filter_applied": filter_type,
        "total_matches": len(results),
        "courses_and_pathways": results
    }


@mcp.tool()
async def search_standards(
    framework_uuid: str,
    query: str
) -> Dict[str, Any]:
    """Search across parsed framework items by keyword (e.g., 'Web Development', 'Cybersecurity', 'Algebra').

    Args:
        framework_uuid: UUID identifier of the framework package.
        query: Keyword or phrase to search for within standard statements, codes, types, and levels.

    Returns:
        List of matching items showing code, statement, type, and grade level/cluster mappings.
    """
    if not framework_uuid or not framework_uuid.strip():
        return {"error": "framework_uuid parameter is required and cannot be empty."}
    if not query or not query.strip():
        return {"error": "query parameter is required and cannot be empty."}

    uuid_clean = framework_uuid.strip()
    query_clean = query.strip()
    url = f"{BASE_URL}/CFPackages/{uuid_clean}"

    try:
        async with httpx.AsyncClient(timeout=45.0, headers=HEADERS) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return {"error": f"Framework UUID '{uuid_clean}' not found (HTTP 404)."}
            response.raise_for_status()
            pkg = response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error {e.response.status_code} while fetching framework '{uuid_clean}': {str(e)}"}
    except httpx.RequestError as e:
        return {"error": f"Request error while fetching framework '{uuid_clean}': {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error while fetching framework '{uuid_clean}': {str(e)}"}

    if not isinstance(pkg, dict):
        return {"error": f"Invalid payload structure returned for framework UUID '{uuid_clean}'."}

    doc = pkg.get("CFDocument", {})
    items = pkg.get("CFItems", [])

    if not items:
        return {
            "framework_uuid": uuid_clean,
            "framework_title": doc.get("title"),
            "query": query_clean,
            "total_matches": 0,
            "matches": [],
            "message": "Framework package contained no items."
        }

    q_lower = query_clean.lower()
    matches = []

    for item in items:
        code = item.get("humanCodingScheme") or item.get("fullStatementCode") or ""
        stmt = item.get("fullStatement") or ""
        itype = item.get("CFItemType") or ""
        ed_level = item.get("educationLevel") or []
        ed_str = " ".join(ed_level) if isinstance(ed_level, list) else str(ed_level)

        if (q_lower in code.lower() or 
            q_lower in stmt.lower() or 
            q_lower in itype.lower() or 
            q_lower in ed_str.lower()):

            matches.append({
                "identifier": item.get("identifier"),
                "code": code,
                "statement": stmt,
                "item_type": itype,
                "grade_level": ed_level,
                "status_start_date": item.get("statusStartDate"),
                "extensions": item.get("extensions")
            })

    return {
        "framework_uuid": uuid_clean,
        "framework_title": doc.get("title"),
        "query": query_clean,
        "total_matches": len(matches),
        "matches": matches
    }


if __name__ == "__main__":
    mcp.run()
