"""Search papers by text query."""

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


def search(
    query: str = typer.Argument(..., help="Search query text."),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results to return."),
    offset: int = typer.Option(0, "--offset", help="Offset for pagination."),
    sort: str = typer.Option(
        "relevant", "--sort", "-s", help="Sort by: relevant, recent, has_code, trending."
    ),
    has_code: bool = typer.Option(False, "--has-code", help="Only show papers with code."),
) -> None:
    """Search papers by text query."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key) as client:
            data = client.search_papers(query=query, limit=limit, offset=offset, sort_by=sort)
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    papers = data.get("papers", [])

    # Client-side --has-code filter (API doesn't support this directly)
    if has_code:
        papers = [p for p in papers if p.get("has_repos") or p.get("repo_count", 0) > 0]

    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl(papers))
    elif fmt == "quiet":
        print(format_quiet(papers))
    elif fmt == "csv":
        print(format_csv(papers, columns=["arxiv_id", "title", "published_date", "repo_count"]))
    elif fmt == "bibtex":
        print(format_bibtex(papers))
    else:
        print_table(build_paper_table(
            papers, title=f"Search: {query}", show_score=True, score_key="similarity_score",
        ))
