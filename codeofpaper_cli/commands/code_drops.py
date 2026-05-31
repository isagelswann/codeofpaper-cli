"""Recent conference papers that just got new code."""

import typer

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import (
    build_code_drops_table,
    format_csv,
    format_json,
    format_jsonl,
    print_error,
    print_table,
)
from codeofpaper_cli.state import state


def code_drops(
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results to return."),
    days: int = typer.Option(30, "--days", "-d", help="Look back N days."),
) -> None:
    """Recent conference papers with new code."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key, ca_bundle=state.ca_bundle, timeout=state.timeout) as client:
            data = client.get_recent_code_drops(limit=limit, days=days)
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code) from None

    # API returns a bare list
    items = data if isinstance(data, list) else []

    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl(items))
    elif fmt == "quiet":
        for d in items:
            print(d.get("repo_name", ""))
    elif fmt == "csv":
        print(format_csv(
            items, columns=["paper_title", "repo_name", "repo_stars", "conference_name", "is_official"],
        ))
    else:
        print_table(build_code_drops_table(items))
