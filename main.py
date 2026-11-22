"""
Root entrypoint for Georgia Department of Education SuitCASE MCP Server (gacaseMCP).
"""

from gacaseMCP.main import main, mcp  # noqa: F401  (mcp is used by `mcp dev main.py`)

if __name__ == "__main__":
    main()
