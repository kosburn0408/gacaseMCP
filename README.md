# gacaseMCP

Model Context Protocol (MCP) server for **Georgia's SuitCASE standards API** (`https://case.georgiastandards.org/ims/case/v1p1/`), which publishes Georgia's standards, course codes and CTAE frameworks in the 1EdTech CASE® 1.1 format.

It lets AI assistants find Georgia standards, course codes, CTAE clusters and pathways, and walk the standards hierarchy. Results come back as summaries and pages rather than whole frameworks, which can hold thousands of items.

📘 **Full documentation:** [User Guide](User_guide.MD)

> This is an independent project that reads the public SuitCASE API. It is not an official GaDOE service.

---

## 🛠️ Tools

| Tool | What it does |
|---|---|
| `get_framework_packages` | List frameworks with their **adoption status**. Deprecated frameworks are hidden unless `include_deprecated=true`. Filter by keyword or framework type |
| `get_framework_by_id` | Summarize one framework: metadata, item counts by type and grade, association types, top-level items |
| `get_framework_items` | Page through items, filtered by item type and grade |
| `get_item` | One item by identifier **or code** (e.g. `1.F.P.2`), with full statement, breadcrumb, children and crosswalk associations |
| `get_children` | Direct children of an item in teaching order (or the framework's top level) |
| `get_ancestors` | Path from the top of the framework down to an item |
| `get_associations` | An item's CASE associations (`isChildOf`, `exactMatchOf`, `isRelatedTo`, `precedes`, …) |
| `search_standards` | Ranked search by code or keywords, with grade and item-type filters. Word-based, so "silent e" finds "silent-e" |
| `get_courses_and_pathways` | Courses (item type `Course` or codes like `11.41500`), pathways and clusters, by item type |

Every list is paged with `limit` (max 200) and `offset`, and returns `next_offset` when there's more.

---

## 🚀 Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m gacaseMCP.main          # stdio MCP server
```

Inspect the tools interactively with the MCP Inspector (from `mcp[cli]`):

```bash
mcp dev main.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gacaseMCP": {
      "command": "/path/to/gacaseMCP/.venv/bin/python",
      "args": ["-m", "gacaseMCP.main"],
      "env": { "PYTHONPATH": "/path/to/gacaseMCP" }
    }
  }
}
```

Antigravity CLI picks up `.agents/mcp_config.json` automatically.

---

## ⚙️ Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GACASE_BASE_URL` | `https://case.georgiastandards.org/ims/case/v1p1` | CASE 1.1 API base URL |
| `GACASE_CACHE_TTL` | `86400` | Seconds to keep downloaded frameworks in memory (`0` disables caching) |
| `GACASE_TIMEOUT` | `60` | Request timeout in seconds |

Frameworks are downloaded once and cached, so walking the tree or searching repeatedly doesn't re-download multi-megabyte packages.

---

## 🧪 Tests

```bash
pip install -e ".[test]"
python -m pytest
```

Tests run against synthetic CASE responses (no network).

---

## Notes on Georgia's data

- Georgia lists retired frameworks alongside current ones (for example, the Georgia Standards of Excellence ELA framework is *Deprecated*; the current K–12 ELA framework is *Adopted*). Check `adoption_status` before aligning to a framework.
- Some item codes repeat within a framework. `get_item` returns the candidates and asks for an identifier when a code is ambiguous.
- Item types differ by framework: ELA uses Domain / Big Idea / Standard / Skill; CTAE uses Course / Content Standard / Element / Component. `get_framework_by_id` lists the types in each.
