"""Bulk export papers as CSV, JSONL, or BibTeX.

Paginate through trending, conference, or search results and output
in a streaming-friendly format. Designed for piping:

    codeofpaper export trending --category cs.CV --has-code -o csv > cv_trending.csv
    codeofpaper export conference neurips_2024 --has-code -o jsonl > data.jsonl
    codeofpaper export search "reinforcement learning" --max 100 -o bibtex > rl.bib
"""

from __future__ import annotations

import time
from typing import Optional

import typer

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import (
    format_bibtex,
    format_csv,
    format_json,
    format_jsonl,
    format_quiet,
    print_error,
)
from codeofpaper_cli.state import state

_PAGE_SIZE = 100
_DELAY = 0.5  # seconds between paginated requests

# CSV columns for papers
_CSV_COLUMNS = [
    "arxiv_id",
    "title",
    "published_date",
    "categories",
    "has_repos",
    "repo_count",
    "max_stars",
    "url",
]


def _flatten_paper(paper: dict) -> dict:
    """Flatten nested fields for CSV output."""
    flat = dict(paper)
    cats = flat.get("categories")
    if isinstance(cats, list):
        flat["categories"] = ";".join(str(c) for c in cats)
    if "url" not in flat:
        aid = flat.get("arxiv_id", flat.get("id", ""))
        flat["url"] = f"https://arxiv.org/abs/{aid}" if aid else ""
    return flat


def _fetch_pages(
    client: Client,
    source: str,
    source_arg: str | None,
    has_code: bool,
    category: str | None,
    days: int,
    max_results: int,
) -> list[dict]:
    """Paginate through the chosen source and collect papers."""
    collected: list[dict] = []
    offset = 0

    while len(collected) < max_results:
        remaining = max_results - len(collected)
        limit = min(_PAGE_SIZE, remaining)

        if source == "trending":
            data = client.get_trending(
                sort="hot",
                has_code=has_code,
                limit=limit,
                offset=offset,
                category=category,
                days=days,
            )
            papers = data.get("trending", [])
        elif source == "conference":
            if not source_arg:
                raise typer.BadParameter("Conference source requires an ID, e.g.: export conference neurips_2024")
            data = client.get_conference_papers(
                conference_id=source_arg,
                has_code=True if has_code else None,
                limit=limit,
                offset=offset,
            )
            papers = data.get("papers", [])
        elif source == "search":
            if not source_arg:
                raise typer.BadParameter("Search source requires a query, e.g.: export search \"transformers\"")
            data = client.search_papers(
                query=source_arg,
                limit=limit,
                offset=offset,
            )
            papers = data.get("papers", [])
        else:
            raise typer.BadParameter(f"Unknown source: {source}. Use: trending, conference, or search.")

        if not papers:
            break

        collected.extend(papers)

        # End of results: fewer items than requested
        if len(papers) < limit:
            break

        offset += len(papers)

        # Rate limit: delay between calls (skip after last page)
        if len(collected) < max_results:
            time.sleep(_DELAY)

    # Trim to exact max
    return collected[:max_results]


def _output(papers: list[dict], fmt: str) -> None:
    """Render collected papers in the requested format."""
    if not papers:
        print_error("No papers found.", fmt)
        return

    if fmt == "json":
        print(format_json({"count": len(papers), "papers": papers}))
    elif fmt == "jsonl":
        print(format_jsonl(papers))
    elif fmt == "quiet":
        print(format_quiet(papers))
    elif fmt == "bibtex":
        print(format_bibtex(papers))
    elif fmt == "csv":
        flat = [_flatten_paper(p) for p in papers]
        print(format_csv(flat, columns=_CSV_COLUMNS))
    else:
        # table — same as csv for export (bulk data)
        flat = [_flatten_paper(p) for p in papers]
        print(format_csv(flat, columns=_CSV_COLUMNS))


def export(
    source: str = typer.Argument(..., help="Source: trending, conference, or search."),
    source_arg: Optional[str] = typer.Argument(None, help="Conference ID or search query."),
    has_code: bool = typer.Option(False, "--has-code", help="Only include papers with code."),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by arXiv category."),
    days: int = typer.Option(30, "--days", "-d", help="Time window for trending (days)."),
    max_results: int = typer.Option(200, "--max", help="Maximum total papers to export."),
) -> None:
    """Bulk export papers from trending, a conference, or a search query."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key) as client:
            papers = _fetch_pages(
                client,
                source=source.lower(),
                source_arg=source_arg,
                has_code=has_code,
                category=category,
                days=days,
                max_results=max_results,
            )
    except typer.BadParameter:
        raise
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    _output(papers, fmt)
