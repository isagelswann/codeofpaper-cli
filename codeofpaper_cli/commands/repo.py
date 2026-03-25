"""Reverse lookup: find which paper(s) a GitHub repo implements."""

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
from codeofpaper_cli.url_parser import extract_github_repo


def repo(
    repo_name: str = typer.Argument(..., help="GitHub repo (owner/repo or URL)."),
) -> None:
    """Reverse lookup: find paper(s) a repo implements."""
    fmt = state.output.value
    owner_repo = extract_github_repo(repo_name)
    try:
        with Client(base_url=state.api_url, api_key=state.api_key) as client:
            data = client.search_papers(query=owner_repo, limit=10)
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    papers = data.get("papers", [])

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
        print_table(build_paper_table(papers, title=f"Papers for {owner_repo}"))
