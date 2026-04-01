"""Find semantically similar papers."""

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
from codeofpaper_cli.url_parser import extract_arxiv_id


def similar(
    paper_id: str = typer.Argument(..., help="ArXiv ID or URL (e.g. 2010.11929)."),
    limit: int = typer.Option(6, "--limit", "-l", help="Maximum similar papers to return."),
) -> None:
    """Find semantically similar papers."""
    fmt = state.output.value
    arxiv_id = extract_arxiv_id(paper_id)
    try:
        with Client(base_url=state.api_url, api_key=state.api_key, ca_bundle=state.ca_bundle, timeout=state.timeout) as client:
            data = client.get_similar(arxiv_id, limit=limit)
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    # API returns 200 even on error with {similar: [], error: "..."}
    if data.get("error"):
        print_error(data["error"], fmt)
        raise typer.Exit(code=1)

    papers = data.get("similar", [])

    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl(papers))
    elif fmt == "quiet":
        print(format_quiet(papers))
    elif fmt == "csv":
        print(format_csv(
            papers, columns=["arxiv_id", "title", "similarity_score", "has_repos"],
        ))
    elif fmt == "bibtex":
        print(format_bibtex(papers))
    else:
        print_table(build_paper_table(
            papers, title=f"Similar to {arxiv_id}",
            show_score=True, score_key="similarity_score",
        ))
