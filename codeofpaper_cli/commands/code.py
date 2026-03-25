"""Get GitHub repos implementing a paper."""

import typer

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import (
    build_repo_table,
    format_bibtex_entry,
    format_csv,
    format_json,
    format_jsonl,
    format_quiet,
    print_error,
    print_table,
)
from codeofpaper_cli.state import state
from codeofpaper_cli.url_parser import extract_arxiv_id


def code(
    paper_id: str = typer.Argument(..., help="ArXiv ID or URL (e.g. 2010.11929)."),
    limit: int = typer.Option(5, "--limit", "-l", help="Maximum repos to return."),
) -> None:
    """Get GitHub repos implementing a paper."""
    fmt = state.output.value
    arxiv_id = extract_arxiv_id(paper_id)
    try:
        with Client(base_url=state.api_url, api_key=state.api_key) as client:
            data = client.get_paper_repos(arxiv_id, limit=limit)
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    repos = data.get("top_repos", [])

    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl(repos))
    elif fmt == "quiet":
        print(format_quiet(repos, id_key="full_name"))
    elif fmt == "csv":
        print(format_csv(repos, columns=["full_name", "stars", "forks", "score", "is_official"]))
    elif fmt == "bibtex":
        paper_data = data.get("paper", {})
        if paper_data:
            print(format_bibtex_entry(paper_data))
        else:
            print_error("BibTeX format not applicable for repo listings.", fmt)
    else:
        print_table(build_repo_table(repos, title=f"Repos for {arxiv_id}"))
