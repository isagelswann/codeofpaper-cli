"""MCP tool implementations.

Each tool is a thin synchronous function that:
- Constructs a short-lived `Client` against the public API.
- Calls a single existing convenience method.
- Returns a plain `dict` (never raises) — errors are surfaced as a
  dict with an `error` key so MCP clients see them as structured
  tool output rather than transport errors.

The functions are kept side-effect-free and easy to mock from
`tests/test_mcp_tools.py`.
"""

from __future__ import annotations

import os
from typing import Any

from codeofpaper_cli import __version__
from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.url_parser import extract_arxiv_id

# Override at process start with CODEOFPAPER_API_URL — useful for
# self-hosted instances or local dev.
DEFAULT_API_URL = os.environ.get(
    "CODEOFPAPER_API_URL", "https://api.codeofpaper.com"
)

# Distinguish MCP-shaped traffic from CLI in server-side telemetry.
MCP_USER_AGENT = f"codeofpaper-mcp/{__version__}"


def _client() -> Client:
    """Build a per-call `Client` with the MCP user agent.

    The CLI's `Client` sets a `codeofpaper-cli/<ver>` UA at construction
    time. We override it post-construction so server-side traffic logs
    can distinguish MCP from CLI installs against the same
    `api_request_logs.user_agent` column.
    """
    c = Client(base_url=DEFAULT_API_URL)
    # Best-effort UA override; if httpx internals change, fall back to
    # whatever the underlying Client set so we still function.
    try:
        c._client.headers["User-Agent"] = MCP_USER_AGENT  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — UA override is non-essential
        pass
    return c


def _error(msg: str, status: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"error": msg}
    if status is not None:
        out["status"] = status
    return out


def paper_lookup(paper_id_or_url: str) -> dict[str, Any]:
    """Get paper metadata + confident-tier repository matches.

    Args:
        paper_id_or_url: An arXiv ID (e.g. ``2010.11929``) or any
            arxiv.org URL (`/abs/`, `/pdf/`, `/html/`). Old-style IDs
            (``hep-th/9901001``) are also accepted.

    Returns:
        Dict with keys: ``paper`` (metadata), ``top_repos`` (list,
        confident tier only), ``no_confident_match`` (bool, true if no
        official / high-confidence-community repo exists). On error
        returns ``{"error": "...", "status": <int|None>}``.
    """
    try:
        arxiv_id = extract_arxiv_id(paper_id_or_url)
    except Exception as exc:  # noqa: BLE001 — surfaces as MCP tool error
        return _error(f"Could not parse paper id from {paper_id_or_url!r}: {exc}")

    try:
        with _client() as client:
            paper = client.get_paper(arxiv_id)
            repos_resp: dict[str, Any] = {}
            try:
                repos_resp = client.get_paper_repos(
                    arxiv_id, limit=10, include_possible=False
                )
            except APIError as exc:
                # 404 on repos is fine — the paper exists but has no
                # confident matches. Other API errors are surfaced.
                if exc.status_code != 404:
                    return _error(str(exc), exc.status_code)
            except ConnectionError_ as exc:
                return _error(str(exc))
    except APIError as exc:
        return _error(str(exc), exc.status_code)
    except ConnectionError_ as exc:
        return _error(str(exc))

    paper_meta = repos_resp.get("paper") if isinstance(repos_resp, dict) else None
    no_confident = bool(
        paper_meta and isinstance(paper_meta, dict)
        and paper_meta.get("no_confident_match")
    )

    return {
        "paper": paper,
        "top_repos": (repos_resp or {}).get("top_repos", []),
        "no_confident_match": no_confident,
    }


def code_for_paper(
    paper_id_or_url: str,
    limit: int = 5,
    include_possible: bool = False,
) -> dict[str, Any]:
    """Get ranked GitHub repositories that implement a paper.

    Args:
        paper_id_or_url: arXiv ID or arxiv.org URL.
        limit: Max repos to return (1-25). Clamped server-side.
        include_possible: Also include ``possible_match`` tier
            (low-confidence). Default false — agents almost always want
            high-precision results.

    Returns:
        Dict with keys: ``paper`` (compact metadata), ``top_repos``
        (list of repos, each with ``full_name``, ``html_url``, ``tier``,
        ``stars``, ``forks``, ``license_spdx``, ``framework``, etc.).
        On error returns ``{"error": "...", "status": <int|None>}``.
    """
    try:
        arxiv_id = extract_arxiv_id(paper_id_or_url)
    except Exception as exc:  # noqa: BLE001
        return _error(f"Could not parse paper id from {paper_id_or_url!r}: {exc}")

    safe_limit = max(1, min(int(limit), 25))

    try:
        with _client() as client:
            data = client.get_paper_repos(
                arxiv_id,
                limit=safe_limit,
                include_possible=include_possible,
            )
    except APIError as exc:
        return _error(str(exc), exc.status_code)
    except ConnectionError_ as exc:
        return _error(str(exc))

    return data if isinstance(data, dict) else _error("Unexpected response shape")


def search_papers(
    query: str,
    limit: int = 10,
    year: int | None = None,
    venue: str | None = None,
    has_code: bool = False,
) -> dict[str, Any]:
    """Search papers by free-text query.

    Args:
        query: Natural-language search query.
        limit: Max results to return (1-50). Clamped server-side.
        year: Restrict to a single publication year (e.g. 2024).
        venue: Conference series (e.g. ``neurips``), conference id
            (e.g. ``neurips2024``), or name substring.
        has_code: If true, drop results without any linked repository.
            Filtered client-side; result count after filtering can be
            < ``limit``.

    Returns:
        Dict with keys ``papers`` (list), ``total`` (int), ``query``,
        ``limit``. On error returns
        ``{"error": "...", "status": <int|None>}``.
    """
    safe_limit = max(1, min(int(limit), 50))

    try:
        with _client() as client:
            data = client.search_papers(
                query=query,
                limit=safe_limit,
                year=year,
                venue=venue,
            )
    except APIError as exc:
        return _error(str(exc), exc.status_code)
    except ConnectionError_ as exc:
        return _error(str(exc))

    if not isinstance(data, dict):
        return _error("Unexpected response shape")

    papers = data.get("papers", [])
    if has_code:
        papers = [
            p for p in papers
            if isinstance(p, dict)
            and (p.get("has_repos") or (p.get("repo_count") or 0) > 0)
        ]
        data = {**data, "papers": papers}
    return data
