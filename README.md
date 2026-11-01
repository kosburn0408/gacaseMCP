# gacaseMCP

**Give AI assistants a reliable way to read Georgia's academic standards, course codes and career pathways, and any other 1EdTech CASE® source you configure.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-1.26–1.x-purple)](https://modelcontextprotocol.io)
[![CASE](https://img.shields.io/badge/1EdTech%20CASE-1.1-orange)](https://www.1edtech.org/standards/case)
[![Tests](https://img.shields.io/badge/tests-23%20passing-brightgreen)](#-development)

gacaseMCP is a [Model Context Protocol](https://modelcontextprotocol.io) server. It connects Claude, Hermes, Antigravity and other MCP-capable assistants to **CASE 1.1** standards servers. Out of the box that means Georgia's SuitCASE and the Georgia CASE Council's shared server. With one setting it can also use another state's CASE server, a district's Satchel instance, or Common Good Learning Tools' Rosetta.

> Independent open project that reads public CASE APIs. It is not an official GaDOE service.

---

## Why this exists

CASE publishes standards as machine-readable data, organized as:
- **frameworks,**
- **items** (standards, skills, courses), and
- **associations** (parent and child, crosswalks, prerequisites).

That structure is what lets software align lessons, courses and credentials to standards. AI assistants can't use it well on their own, for three reasons:
- frameworks are large (Georgia's ELA framework has thousands of items)
- retired frameworks sit beside current ones
- the useful relationships are scattered across associations

gacaseMCP handles that for them:

- **Summaries and pages, not data dumps.** An assistant sees a framework's shape first, then drills in.
- **Tree navigation.** Find a standard by code (`1.F.P.2`), see its breadcrumb and children, and follow crosswalks.
- **Adoption status everywhere.** Deprecated frameworks are hidden by default and flagged when used.
- **Ranked search** that matches words, not exact strings, and filters by grade and item type.
- **More than one server.** Follow an association from Georgia K–12 to a postsecondary framework on another configured server.

---

## 💬 What you can ask an assistant

| Ask | Tools it will use |
|---|---|
| "Which Georgia standard covers decoding words with silent e in 1st grade?" | `get_framework_packages` → `search_standards` |
| "Show me everything under kindergarten phonics." | `get_children` (`K.F` → `K.F.P`) |
| "What's the path to standard 1.F.P.2, and what does it crosswalk to?" | `get_item` / `get_ancestors` / `get_associations` |
| "List the courses in the Digital Technology career cluster." | `get_courses_and_pathways` |
| "Is the ELA framework I'm using still current?" | `get_framework_packages` (adoption status) |
| "How does this K–12 standard connect to TCSG or USG programs?" | `get_item_associations` (server `georgiacase`) → `resolve_case_uri` |

---

## 🌐 CASE servers

| Name | What it holds | Base URL |
|---|---|---|
| `georgia` *(default)* | Georgia SuitCASE (GaDOE): K–12 standards (current ELA and Math plus other subjects), CTAE clusters and courses, course codes, high-demand career lists, educator standards | `https://case.georgiastandards.org/ims/case/v1p1` |
| `georgiacase` | Georgia CASE Council shared server: cross-agency frameworks (GaDOE, TCSG, USG institutions), High-Demand Career List, SOC reference data | `https://georgiacase.org/ims/case/v1p1` |
| *your own* | Another state, a district Satchel, Rosetta, … | set in `GACASE_SERVERS` |

Every tool takes an optional `server` argument; `list_case_servers` shows what's configured.

### Adding Rosetta or another CASE server

Add servers with a JSON setting. Tokens are read from the environment variable you name, never from the JSON itself:

```bash
export GACASE_SERVERS='{
  "rosetta": {
    "base_url": "https://<rosetta-api-host>/ims/case/v1p1",
    "description": "Common Good Learning Tools Rosetta",
    "token_env": "ROSETTA_TOKEN"
  },
  "alabama": {"base_url": "https://<state-case-host>/ims/case/v1p1"}
}'
export ROSETTA_TOKEN=...   # if the server requires a bearer token
```

Rosetta's API address and access terms come from Common Good Learning Tools; the public Rosetta site doesn't document them. Once configured, the same tools work against it. `resolve_case_uri` will then follow links into it, because it only fetches hosts you've configured.

---

## 🛠️ Tools

**Find and summarize frameworks**
| Tool | What it does |
|---|---|
| `list_case_servers` | Configured servers and whether each has a token |
| `get_framework_packages` | List frameworks with **adoption status**; hides Deprecated unless `include_deprecated=true`; filter by keyword or type |
| `get_framework_by_id` | Summary: metadata, item counts by type and grade, association types, top-level items |
| `get_framework_items` | Page through items, filtered by type and grade |

**Navigate and search**
| Tool | What it does |
|---|---|
| `get_item` | One item by identifier **or code**, with full statement, breadcrumb, children, crosswalks |
| `get_children` | Direct children in published order (or the framework's top level) |
| `get_ancestors` | Path from the top of the framework to an item |
| `get_associations` | An item's associations within its framework (`isChildOf`, `exactMatchOf`, `isRelatedTo`, …) |
| `search_standards` | Ranked search by code or keywords, with grade and type filters |
| `get_courses_and_pathways` | Courses (type `Course` or codes like `11.41500`), pathways and clusters |

**Across frameworks and servers**
| Tool | What it does |
|---|---|
| `get_item_associations` | All associations touching an item across a server's frameworks (CASE `getCFItemAssociations`), where articulations usually live |
| `resolve_case_uri` | Read any CASE item, framework or association URI on a configured server, to follow a link wherever it points |

Lists are paged (`limit` up to 200, `offset`, `next_offset`). Errors come back as `{"error": "..."}` with a readable message.

---

## 🚀 Quick start

```bash
git clone https://github.com/kosburn0408/gacaseMCP.git
cd gacaseMCP
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m gacaseMCP.main        # stdio MCP server
```

Try the tools in a browser with the MCP Inspector (included in `mcp[cli]`):

```bash
mcp dev main.py
```

### Connect an assistant

**Claude Desktop:** in `claude_desktop_config.json`:
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

**Claude Code:**
```bash
claude mcp add gacase -e PYTHONPATH=/path/to/gacaseMCP -- /path/to/gacaseMCP/.venv/bin/python -m gacaseMCP.main
```

**Hermes, Cursor, VS Code, Cline:** use the same command, args and env in the client's `mcp.json`.

**Antigravity CLI:** `.agents/mcp_config.json` is picked up automatically.

---

## ⚙️ Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GACASE_SERVERS` | *(none)* | JSON object adding or overriding servers (see above) |
| `GACASE_DEFAULT_SERVER` | `georgia` | Server used when a tool call doesn't name one |
| `GACASE_BASE_URL` | SuitCASE URL | Overrides the `georgia` server's URL |
| `GACASE_CACHE_TTL` | `86400` | Seconds to keep downloaded data in memory (`0` disables) |
| `GACASE_TIMEOUT` | `60` | Request timeout in seconds |

Each framework is downloaded once and cached, so drilling down or searching repeatedly is fast and gentle on the servers.

---

## 📌 Notes on Georgia's data

- **Retired frameworks stay listed.** For example, *English Language Arts – Georgia Standards of Excellence* is **Deprecated**; *English Language Arts – Georgia Department of Education* is the **Adopted** K–12 framework (codes like `K.F.P.2`).
- **Item types differ by framework.**
  - ELA uses Domain → Big Idea → Standard → Skill.
  - CTAE uses Course → Content Standard → Element → Component.
  - `get_framework_by_id` lists each framework's types.
- **Some codes repeat** within a framework. `get_item` returns the candidates and asks for an identifier.
- **Framework types can have trailing spaces** in the source (`"CourseCodes "`); filters handle this.

---

## 🧱 How it's built

```
gacaseMCP/
├── client.py     # server registry, bearer tokens, cached HTTP (CFDocuments, CFPackages, CFItemAssociations, URIs)
├── framework.py  # per-framework index: items, code lookup, isChildOf tree, associations, ranked search
└── main.py       # the 12 MCP tools
tests/            # 23 tests against synthetic CASE fixtures (no network)
```

---

## 🧪 Development

```bash
pip install -e ".[test]"
python -m pytest
```

Tests use synthetic fixtures modelled on the real SuitCASE structure: field names, item types, `isChildOf` with `sequenceNumber`, duplicate codes, and trailing-space types. They need no network.

---

## 🗺️ Roadmap

- One shared CASE library for this server and [sor-mcp-server](https://github.com/kosburn0408/sor-mcp-server), which looks up Georgia K–3 Foundations standards.
- MCP resources (browsable frameworks and items) and prompts, such as "align this lesson to Georgia standards".
- A license.

📘 Detailed reference: [User Guide](User_guide.MD)
