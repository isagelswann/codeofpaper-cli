"""Get details for a specific paper."""

import typer

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import (
    build_paper_detail_table,
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


def paper(
    paper_id: str = typer.Argument(..., help="ArXiv ID or URL (e.g. 2010.11929)."),
) -> None:
    """Get details for a specific paper."""
    fmt = state.output.value
    arxiv_id = extract_arxiv_id(paper_id)
    try:
        with Client(base_url=state.api_url, api_key=state.api_key, ca_bundle=state.ca_bundle, timeout=state.timeout) as client:
            data = client.get_paper(arxiv_id)
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl([data]))
    elif fmt == "quiet":
        print(format_quiet([data]))
    elif fmt == "csv":
        print(format_csv([data], columns=["arxiv_id", "title", "published_date", "repo_count"]))
    elif fmt == "bibtex":
        print(format_bibtex_entry(data))
    else:
        print_table(build_paper_detail_table(data))
