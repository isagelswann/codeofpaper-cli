"""MCP (Model Context Protocol) server for codeofpaper.

Exposes a thin set of read-only tools over the public codeofpaper API
so MCP-compatible agents (Claude Desktop, Cursor, Continue, Cline, etc.)
can look up papers and their GitHub implementations without web search.

This package is an *optional* extra:

    pip install codeofpaper[mcp]

Then wire into an MCP client (e.g. Claude Desktop's config):

    {
      "mcpServers": {
        "codeofpaper": {
          "command": "uvx",
          "args": ["codeofpaper-mcp"]
        }
      }
    }

See `docs/features/STRATEGIC_REFLECTION_2026_05_22.md` §7 in the main
codeofpaper repo for the rationale (distribution billboard, not a
feature) and the kill criteria (2026-09-01 checkpoint).
"""

from codeofpaper_cli.mcp.server import main

__all__ = ["main"]
