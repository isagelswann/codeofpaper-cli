"""Browse trending papers."""

from typing import Optional

import typer

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import (
    build_paper_table,
    format_bibtex,
    format_csv,
    format_json,
    format_jsonl,
    format_quiet,
    print_error,
    print_table,
)
from codeofpaper_cli.state import state


def trending(
    sort: str = typer.Option("hot", "--sort", "-s", help="Sort by: hot, top, new, rising."),
    has_code: bool = typer.Option(False, "--has-code", help="Only show papers with code."),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results to return."),
    offset: int = typer.Option(0, "--offset", help="Offset for pagination."),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by arXiv category (e.g. cs.CV)."),
    days: int = typer.Option(7, "--days", "-d", help="Trending window in days."),
) -> None:
    """Browse trending papers."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key, ca_bundle=state.ca_bundle, timeout=state.timeout) as client:
            data = client.get_trending(
                sort=sort, has_code=has_code, limit=limit,
                offset=offset, category=category, days=days,
            )
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    # Use 'trending' array, NOT 'papers' (they're duplicated)
    papers = data.get("trending", [])

    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl(papers))
    elif fmt == "quiet":
        print(format_quiet(papers))
    elif fmt == "csv":
        print(format_csv(
            papers, columns=["arxiv_id", "title", "trending_score", "max_stars", "repo_count"],
        ))
    elif fmt == "bibtex":
        print(format_bibtex(papers))
    else:
        print_table(build_paper_table(
            papers, title="Trending Papers",
            show_score=True, score_key="trending_score", show_rank=True,
        ))
