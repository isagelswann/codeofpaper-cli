"""Browse papers from a specific conference."""

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


def conference(
    conference_id: str = typer.Argument(..., help="Conference ID (e.g. neurips_2024)."),
    has_code: bool = typer.Option(False, "--has-code", help="Only show papers with code."),
    track: Optional[str] = typer.Option(None, "--track", help="Filter by track (e.g. oral, poster)."),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results to return."),
    offset: int = typer.Option(0, "--offset", help="Offset for pagination."),
) -> None:
    """Browse papers from a specific conference."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key, ca_bundle=state.ca_bundle, timeout=state.timeout) as client:
            data = client.get_conference_papers(
                conference_id,
                has_code=True if has_code else None,
                track=track,
                limit=limit,
                offset=offset,
            )
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    papers = data.get("papers", [])
    title = data.get("name", conference_id)

    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl(papers))
    elif fmt == "quiet":
        print(format_quiet(papers))
    elif fmt == "csv":
        print(format_csv(
            papers, columns=["arxiv_id", "title", "track", "has_repos", "repo_count", "max_stars"],
        ))
    elif fmt == "bibtex":
        print(format_bibtex(papers))
    else:
        print_table(build_paper_table(papers, title=title))
