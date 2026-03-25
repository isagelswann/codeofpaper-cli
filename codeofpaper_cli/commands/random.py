"""Get a random interesting paper."""

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


def random_paper(
    quality: str = typer.Option("high", "--quality", "-q", help="Quality filter: high, medium, any."),
) -> None:
    """Get a random interesting paper."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key) as client:
            data = client.get_random(quality=quality)
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
