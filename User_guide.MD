# gacaseMCP User Guide

## 📋 Contents
1. [Overview](#ℹ️-overview)
2. [Installation](#️-installation)
3. [Running the server](#-running-the-server)
4. [How to use the tools](#-how-to-use-the-tools)
5. [Tool reference](#️-tool-reference)
6. [Configuration](#-configuration)
7. [Troubleshooting](#-troubleshooting)

---

## ℹ️ Overview

**gacaseMCP** connects AI assistants (Claude, Antigravity, Hermes or custom agents) to Georgia's SuitCASE repository, which publishes Georgia's frameworks in the 1EdTech CASE® 1.1 format. The frameworks include:
- **Subject standards:** the current K–12 English Language Arts and Mathematics standards, Science, Social Studies, Computer Science, Fine Arts, World Languages, Health, PE, and the Georgia Early Learning and Development Standards.
- **CTAE career clusters,** with courses and their content standards.
- **Course codes and titles,** in GaDOE's `NN.NNNNN` format, e.g. `11.41500`, plus the State-Funded List of K–8 Subjects and 9–12 Courses.
- **Other frameworks,** such as high-demand career lists and educator performance standards (TAPS, LAPS).

Georgia keeps retired frameworks in the repository. Each framework's **adoption status** (*Adopted*, *Draft* or *Deprecated*) is shown, and Deprecated frameworks are hidden unless you ask for them.

This is an independent project that reads the public SuitCASE API; it is not an official GaDOE service.

---

## ⚙️ Installation

Requires Python 3.10+.

```bash
git clone https://github.com/kosburn0408/gacaseMCP.git
cd gacaseMCP
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` pins `mcp` below 2.0, because the server uses `FastMCP`, which MCP 2.x removed.

---

## 🚀 Running the server

**Python (stdio):**
```bash
python -m gacaseMCP.main      # or: python main.py
```

**MCP Inspector** (browser UI to try tools; included with `mcp[cli]`):
```bash
mcp dev main.py
```

**Antigravity CLI:** `.agents/mcp_config.json` is discovered automatically; check with `/mcp`.

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):
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

---

## 🧭 How to use the tools

Frameworks can hold thousands of items, so the tools are built to be used in steps:

1. **Find the framework.**
   `get_framework_packages(query="Language Arts")` returns titles, identifiers and adoption status. Use an **Adopted** one.
2. **See its shape.**
   `get_framework_by_id(framework_uuid)` returns item counts by type and grade, plus the top-level items (e.g. `K.F Foundations`).
3. **Then either walk the tree or search.**
   - Walk down: `get_children(framework_uuid, "K.F")` → `get_children(framework_uuid, "K.F.P")` → `get_item(framework_uuid, "K.F.P.2")`
   - Or search: `search_standards(framework_uuid, "decode silent e", education_level="1")`
4. **Follow relationships.**
   `get_item` shows an item's breadcrumb, its children, and crosswalks to other frameworks. `get_associations` lists them all, filtered by type.

Lists return `total`, `offset`, `limit` and `next_offset`; pass `offset=next_offset` for the next page.

---

## 🛠️ Tool reference

### `get_framework_packages(query=None, framework_type=None, include_deprecated=False)`
Lists frameworks.
- **query** matches the title, description, notes, subject and type.
- **framework_type** is a partial match on Georgia's types: `Standards`, `CourseCodes`, `Credential List`, `Resource Collection`, `High Demand Career List Regions`. Some frameworks have no type and won't match a type filter.
- Each result includes `identifier`, `title`, `adoption_status`, `framework_type`, `subject`, dates, `uri` and `package_uri`.
- `deprecated_hidden` reports how many retired frameworks were left out.

### `get_framework_by_id(framework_uuid)`
Returns a summary, not every item:
- `framework` metadata, including `adoption_status`
- `warnings` if the framework isn't Adopted
- `total_items` and `item_types` (counts)
- `education_levels`
- `association_types`
- the first 50 `top_level` items

### `get_framework_items(framework_uuid, item_type=None, education_level=None, limit=50, offset=0)`
Pages through items.
- **item_type** must match exactly (e.g. `Standard`, `Course`, `Content Standard`).
- **education_level** accepts `K`, `KG`, `1`, `01`, `1st` or `09`.

### `get_item(framework_uuid, item)`
**item** is an identifier, item URI or code (e.g. `1.F.P.2`, `IT-IDT-1`). Returns:
- the full item
- the `breadcrumb` (ancestors, top first)
- direct `children`
- non-hierarchy `associations` such as `exactMatchOf` crosswalks

If a code matches more than one item (some Georgia codes repeat), it returns `candidates` instead; call it again with an identifier.

### `get_children(framework_uuid, item=None, limit=50, offset=0)`
Lists direct children in their published order. With no item, it lists the framework's top level. Each child shows `has_children`.

### `get_ancestors(framework_uuid, item)`
Returns the path from the top level down to the item.

### `get_associations(framework_uuid, item, association_type=None)`
Lists all associations to or from the item, with `direction` (outgoing or incoming) and a summary of the other item. Items outside the framework are shown by title and URI.

### `search_standards(framework_uuid, query, education_level=None, item_type=None, limit=20, offset=0)`
Ranked search:
- an exact code match ranks first, then codes that start with the query
- then items containing all the words, with a bonus for the exact phrase
- hyphens and punctuation are ignored, so "silent e" matches "silent-e"
- broader items (standards) rank above their sub-skills on ties

Each match includes a `score`.

### `get_courses_and_pathways(framework_uuid, filter_type=None, limit=50, offset=0)`
Lists items by type:
- **Course:** item type `Course`, or a code like `11.41500`. Courses include `standards_count`, the number of direct child standards.
- **Pathway:** item types containing "pathway".
- **Cluster:** item types containing "cluster".

**filter_type** is `Course`, `Pathway` or `Cluster`.

All tools return `{"error": "..."}` with a readable message if the API can't be reached or an item isn't found.

---

## ⚙️ Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GACASE_BASE_URL` | `https://case.georgiastandards.org/ims/case/v1p1` | CASE 1.1 API base URL |
| `GACASE_CACHE_TTL` | `86400` | Seconds to keep downloaded data in memory (`0` disables) |
| `GACASE_TIMEOUT` | `60` | Request timeout (seconds) |

---

## ❓ Troubleshooting

**`ModuleNotFoundError: No module named 'mcp'`**
Activate the virtual environment and run `pip install -r requirements.txt`.

**`cannot import name 'FastMCP'`**
MCP 2.x is installed. Reinstall from `requirements.txt`, which pins `mcp<2`.

**Requests time out or fail**
Check access to `https://case.georgiastandards.org`. The API is public and needs no key. Large frameworks can take a few seconds the first time; after that they're cached.

**A code returns "matches N items"**
That code is used more than once in the framework. Pick the right item from `candidates` and pass its `identifier`.

**Results come from a retired framework**
Check `adoption_status`. Use `get_framework_packages()` (which hides Deprecated frameworks) to find the current one.
