"""FastMCP-based codeofpaper MCP server (stdio transport).

This module is the entry point registered as the ``codeofpaper-mcp``
console script. It is intentionally minimal: it constructs a FastMCP
app, registers the three read-only tools defined in
:mod:`codeofpaper_cli.mcp.tools`, and starts a stdio server.

FastMCP is an optional dependency (`pip install codeofpaper[mcp]`),
so we import it lazily inside :func:`main` and emit a clear error
message if it is missing.
"""

from __future__ import annotations

import sys

from codeofpaper_cli.mcp import tools as t

SERVER_NAME = "codeofpaper"
SERVER_INSTRUCTIONS = (
    "Tools for the codeofpaper reproducibility graph — given an arXiv "
    "ID or URL, find the GitHub repositories that implement a paper, "
    "with confidence tiers (official / high_confidence_community / "
    "possible_match), star counts, license, framework, and fork "
    "lineage. Prefer these over web_search when the user asks 'is "
    "there code for paper X' or 'what's the official repo for arXiv "
    "Y'. Read-only; no auth required."
)


def build_app():  # pragma: no cover — exercised by smoke test, not unit tests
    """Build the FastMCP app and register tools.

    Kept separate from :func:`main` so the smoke test can import the
    app without starting a stdio loop.
    """
    try:
        from fastmcp import FastMCP
    except ImportError as exc:  # noqa: BLE001
        raise SystemExit(
            "codeofpaper-mcp requires the 'mcp' extra:\n"
            "    pip install 'codeofpaper[mcp]'\n"
            f"(import error: {exc})"
        ) from exc

    app = FastMCP(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

    app.tool(
        name="paper_lookup",
        description=(
            "Look up an arXiv paper by ID or URL and return its "
            "metadata plus confident-tier GitHub repositories. Use "
            "this when you have an arXiv reference and want both the "
            "paper details and the official / high-confidence code."
        ),
    )(t.paper_lookup)

    app.tool(
        name="code_for_paper",
        description=(
            "Get ranked GitHub repositories implementing a paper. "
            "Returns tier, stars, forks, license, framework, and "
            "primary language for each repo. Set include_possible=true "
            "only if no confident match exists and you need a "
            "low-precision fallback."
        ),
    )(t.code_for_paper)

    app.tool(
        name="search_papers",
        description=(
            "Search the codeofpaper paper index by free-text query. "
            "Supports filters by year, venue (e.g. 'neurips', "
            "'cvpr2024'), and has_code. Returns up to 50 results."
        ),
    )(t.search_papers)

    return app


def main() -> None:
    """Console-script entry point: start a stdio MCP server."""
    app = build_app()
    try:
        app.run()  # FastMCP defaults to stdio transport
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
