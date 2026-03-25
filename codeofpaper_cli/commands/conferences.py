"""List all conference series with stats."""

import typer

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import (
    build_conference_table,
    format_csv,
    format_json,
    format_jsonl,
    format_quiet,
    print_error,
    print_table,
)
from codeofpaper_cli.state import state


def conferences() -> None:
    """List all conference series with stats."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key) as client:
            data = client.get_conferences()
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
        for c in items:
            slug = f"{c.get('series', '')}_{c.get('year', '')}"
            print(slug)
    elif fmt == "csv":
        print(format_csv(
            items, columns=["name", "year", "series", "total_papers", "papers_with_code", "github_percentage"],
        ))
    else:
        print_table(build_conference_table(items))
