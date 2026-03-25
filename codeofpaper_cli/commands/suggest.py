"""Autocomplete / quick paper lookup."""

import typer

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import (
    build_paper_table,
    format_csv,
    format_json,
    format_jsonl,
    format_quiet,
    print_error,
    print_table,
)
from codeofpaper_cli.state import state


def suggest(
    query: str = typer.Argument(..., help="Partial title or query text."),
) -> None:
    """Autocomplete / quick paper lookup."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key) as client:
            data = client.suggest(query)
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    # API returns a bare list
    items = data if isinstance(data, list) else []

    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl(items))
    elif fmt == "quiet":
        print(format_quiet(items))
    elif fmt == "csv":
        print(format_csv(items, columns=["arxiv_id", "title", "has_repos"]))
    else:
        print_table(build_paper_table(items, title=f"Suggestions: {query}"))
