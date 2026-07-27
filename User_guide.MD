# gacaseMCP User Guide

Welcome to the **gacaseMCP** User Guide. This guide provides step-by-step instructions on installing, configuring, running, and interacting with the Model Context Protocol (MCP) server for the Georgia Department of Education (GaDOE) SuitCASE API (`https://case.georgiastandards.org/ims/case/v1p1/`).

---

## 📋 Table of Contents
1. [Overview](#overview)
2. [Prerequisites & System Requirements](#prerequisites--system-requirements)
3. [Installation](#installation)
4. [Running the MCP Server](#running-the-mcp-server)
   - [Method A: Python Module Execution](#method-a-python-module-execution)
   - [Method B: FastMCP CLI](#method-b-fastmcp-cli)
   - [Method C: Antigravity CLI Integration](#method-c-antigravity-cli-integration)
   - [Method D: Claude Desktop / MCP Host Client](#method-d-claude-desktop--mcp-host-client)
5. [Tool Reference & Usage Examples](#tool-reference--usage-examples)
   - [1. get_framework_packages](#1-get_framework_packages)
   - [2. get_framework_by_id](#2-get_framework_by_id)
   - [3. get_courses_and_pathways](#3-get_courses_and_pathways)
   - [4. search_standards](#4-search_standards)
6. [Troubleshooting & FAQ](#troubleshooting--faq)

---

## ℹ️ Overview

**gacaseMCP** connects AI assistants (such as Antigravity, Claude, or custom LLM agents) to Georgia's official SuitCASE (State Standards Framework) repository using the 1.1 CASE open specification.

With `gacaseMCP`, AI models can automatically retrieve and analyze:
- **Georgia Standards of Excellence (GSE)** for Computer Science, Math, Science, ELA, Fine Arts, Social Studies, World Languages, etc.
- **CTAE Career Clusters & Pathways** (Digital Technology, Cybersecurity, Engineering, Healthcare, Business, Agriculture, etc.).
- **Official Course Codes & Titles** (following standard GaDOE course code formats like `11.41500`, `01.01210`).
- **State-Funded K-8 Subjects & 9-12 Courses**.

---

## 💻 Prerequisites & System Requirements

- **Python**: Version 3.10 or higher (Python 3.11+ recommended).
- **Dependencies**:
  - `mcp[cli]` (FastMCP server runtime)
  - `httpx` (Asynchronous HTTP client)
  - `pydantic` (Data validation)

---

## ⚙️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/kosburn0408/gacaseMCP.git
   cd gacaseMCP
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🚀 Running the MCP Server

### Method A: Python Module Execution
To run the MCP server directly via standard Python stdio transport:
```bash
python -m gacaseMCP.main
```
Or from the root directory:
```bash
python main.py
```

### Method B: FastMCP CLI
If `mcp[cli]` is installed, you can use `fastmcp`:
```bash
fastmcp run main.py
```
To inspect tool schemas and launch an interactive inspector interface in your browser:
```bash
fastmcp dev main.py
```

### Method C: Antigravity CLI Integration
This workspace includes a `.agents/mcp_config.json` configuration file. When working inside Antigravity CLI (`agy-cli`), the server is auto-discovered:
```json
{
  "mcpServers": {
    "gacaseMCP": {
      "command": "python3",
      "args": [
        "-m",
        "gacaseMCP.main"
      ],
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}
```
You can invoke tools directly from your prompts or verify connection via `/mcp` inside `agy-cli`.

### Method D: Claude Desktop / MCP Host Client
Add the following snippet to your `claude_desktop_config.json` (located at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "gacaseMCP": {
      "command": "/path/to/gacaseMCP/.venv/bin/python",
      "args": [
        "-m",
        "gacaseMCP.main"
      ],
      "env": {
        "PYTHONPATH": "/path/to/gacaseMCP"
      }
    }
  }
}
```

---

## 🛠️ Tool Reference & Usage Examples

### 1. `get_framework_packages`
Lists or searches framework documents registered on Georgia SuitCASE.

- **Parameters:**
  - `query` *(optional str)*: Keyword to filter document titles or descriptions (e.g. `'Computer Science'`, `'CTAE'`).
  - `framework_type` *(optional str)*: Filter by framework category (e.g. `'Standards'`, `'CourseCodes'`, `'High Demand Career List Regions'`).

- **Example Call:**
  ```python
  await get_framework_packages(query="Computer Science", framework_type="Standards")
  ```

- **Sample Output:**
  ```json
  {
    "total_packages": 2,
    "query": "Computer Science",
    "framework_type": "Standards",
    "packages": [
      {
        "identifier": "00fcf0e2-b9c3-11e7-a4ad-47f36833e889",
        "title": "Computer Science - Georgia Standards of Excellence",
        "framework_type": "Standards",
        "creator": "Georgia Department of Education",
        "publisher": "Georgia Department of Education",
        "last_change_date_time": "2025-06-30T23:05:56+00:00",
        "case_version": "1.1",
        "description": "The Georgia Standards of Excellence (GSE) for Computer Science...",
        "uri": "https://case.georgiastandards.org/ims/case/v1p1/CFDocuments/00fcf0e2-b9c3-11e7-a4ad-47f36833e889",
        "package_uri": "https://case.georgiastandards.org/ims/case/v1p1/CFPackages/00fcf0e2-b9c3-11e7-a4ad-47f36833e889"
      }
    ]
  }
  ```

---

### 2. `get_framework_by_id`
Retrieves a complete framework bundle by its UUID.

- **Parameters:**
  - `framework_uuid` *(str, required)*: UUID string of target framework.

- **Example Call:**
  ```python
  await get_framework_by_id(framework_uuid="00fcf0e2-b9c3-11e7-a4ad-47f36833e889")
  ```

- **Sample Output:**
  ```json
  {
    "framework_uuid": "00fcf0e2-b9c3-11e7-a4ad-47f36833e889",
    "CFDocument": {
      "identifier": "00fcf0e2-b9c3-11e7-a4ad-47f36833e889",
      "title": "Computer Science - Georgia Standards of Excellence",
      "framework_type": "Standards",
      "creator": "Georgia Department of Education"
    },
    "total_items": 2453,
    "CFItems": [
      {
        "identifier": "cbf16dd6-46b2-11ea-a7df-0242ac150004",
        "code": "11.07300",
        "statement": "Computer Science Kindergarten",
        "type": "Course",
        "education_level": ["KG"]
      }
    ],
    "total_associations": 2483,
    "CFAssociations": [...]
  }
  ```

---

### 3. `get_courses_and_pathways`
Extracts course codes (`XX.XXXXX`), course names, CTAE clusters, and CTAE pathways from a framework package.

- **Parameters:**
  - `framework_uuid` *(str, required)*: UUID string of target framework package.
  - `filter_type` *(optional str)*: Filter type (`'Course'`, `'Pathway'`, `'Cluster'`, `'CTAE'`).

- **Example Call:**
  ```python
  await get_courses_and_pathways(
      framework_uuid="a1215918-318b-4773-9229-26a266e3ad62", 
      filter_type="Course"
  )
  ```

- **Sample Output:**
  ```json
  {
    "framework_uuid": "a1215918-318b-4773-9229-26a266e3ad62",
    "framework_title": "CTAE - Georgia Standards of Excellence: Career Cluster: Digital Technology",
    "filter_applied": "Course",
    "total_matches": 28,
    "courses_and_pathways": [
      {
        "identifier": "b8f52e12-46b2-11ea-a7df-0242ac150004",
        "code": "11.41500",
        "name": "Introduction to Digital Technology",
        "item_type": "Course",
        "categories": ["Course", "CTAE"],
        "is_course_code": true,
        "education_level": ["09", "10", "11", "12"]
      },
      {
        "identifier": "b8f53c86-46b2-11ea-a7df-0242ac150004",
        "code": "11.48100",
        "name": "Introduction to Cybersecurity",
        "item_type": "Course",
        "categories": ["Course", "CTAE"],
        "is_course_code": true,
        "education_level": ["09", "10", "11", "12"]
      }
    ]
  }
  ```

---

### 4. `search_standards`
Searches across all items in a framework package by keyword.

- **Parameters:**
  - `framework_uuid` *(str, required)*: Framework package UUID.
  - `query` *(str, required)*: Keyword or search phrase.

- **Example Call:**
  ```python
  await search_standards(
      framework_uuid="a1215918-318b-4773-9229-26a266e3ad62", 
      query="Cybersecurity"
  )
  ```

- **Sample Output:**
  ```json
  {
    "framework_uuid": "a1215918-318b-4773-9229-26a266e3ad62",
    "framework_title": "CTAE - Georgia Standards of Excellence: Career Cluster: Digital Technology",
    "query": "Cybersecurity",
    "total_matches": 15,
    "matches": [
      {
        "identifier": "b8f53c86-46b2-11ea-a7df-0242ac150004",
        "code": "11.48100",
        "statement": "Introduction to Cybersecurity",
        "item_type": "Course",
        "grade_level": ["09", "10", "11", "12"]
      },
      {
        "identifier": "b8f53d26-46b2-11ea-a7df-0242ac150004",
        "code": "IT-ICS-3",
        "statement": "Demonstrate an understanding of cybersecurity concepts and research.",
        "item_type": "Content Standard",
        "grade_level": ["09", "10", "11", "12"]
      }
    ]
  }
  ```

---

## ❓ Troubleshooting & FAQ

#### Q: I get `ModuleNotFoundError: No module named 'mcp'`
**Fix:** Ensure your virtual environment is activated (`source .venv/bin/activate`) and dependencies are installed (`pip install -r requirements.txt`).

#### Q: Network requests time out or fail with HTTP errors
**Fix:** Verify internet access to `https://case.georgiastandards.org`. SuitCASE API is public and requires no API key.

#### Q: How do I find framework UUIDs?
**Fix:** Call `get_framework_packages()` first without a UUID parameter to search by title or keyword (e.g., `'Digital Technology'`, `'Mathematics'`, `'State-Funded'`) and extract the `identifier` UUID from the list.
