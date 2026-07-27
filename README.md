# gacaseMCP

Model Context Protocol (MCP) server written in Python using FastMCP for the **Georgia Department of Education SuitCASE API** (`https://case.georgiastandards.org/ims/case/v1p1/`).

This MCP server enables AI assistants and agents to search, fetch, and parse Georgia learning standards, course codes, course names, CTAE clusters, and CTAE pathways directly from official state framework documents.

📘 **For detailed documentation, parameter specifications, and client integration instructions, view the [User Guide](User_guide.MD).**

---

## 🛠️ Tools Available

### 1. `get_framework_packages`
- **Description:** Search or list top-level framework documents (e.g., CTAE Pathways, High Demand Careers, Course Guides, Subject Standards).
- **Parameters:**
  - `query` (optional str): Keyword search term.
  - `framework_type` (optional str): Filter by framework type (e.g., `'Standards'`, `'CourseCodes'`).

### 2. `get_framework_by_id`
- **Description:** Pull complete standard framework bundle by UUID.
- **Parameters:**
  - `framework_uuid` (str): UUID identifier (e.g., `'00fcf0e2-b9c3-11e7-a4ad-47f36833e889'`).

### 3. `get_courses_and_pathways`
- **Description:** Extract and filter course codes (format `XX.XXXXX`), course names, CTAE clusters, and CTAE pathways within a framework package.
- **Parameters:**
  - `framework_uuid` (str): UUID identifier of framework package.
  - `filter_type` (optional str): Filter string e.g. `'Course'`, `'Pathway'`, `'Cluster'`, `'CTAE'`.

### 4. `search_standards`
- **Description:** Search across framework items by keyword.
- **Parameters:**
  - `framework_uuid` (str): UUID identifier.
  - `query` (str): Search term (e.g., `'Cybersecurity'`, `'Web Development'`, `'Algebra'`).

---

## 🚀 Quick Start

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run as Module:**
   ```bash
   python -m gacaseMCP.main
   ```

3. **Run using FastMCP CLI:**
   ```bash
   fastmcp run main.py
   ```

4. **Integration with Antigravity CLI:**
   Pre-configured at `.agents/mcp_config.json`. `agy-cli` automatically discovers and loads `gacaseMCP` via `/mcp`.

---

## 📖 Complete Documentation

Read [User_guide.MD](User_guide.MD) for full setup guides, JSON response schemas, and integration details for Claude Desktop, Antigravity CLI, and custom agents.
