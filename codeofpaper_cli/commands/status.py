"""Check API health and basic stats."""

import typer
from rich.table import Table

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import format_json, print_error, print_table
from codeofpaper_cli.state import state


def status() -> None:
    """Check API health and basic stats."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key) as client:
            health = client.get_health()
            paper_health = client.get_paper_health()
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    combined = {**health, **paper_health}

    if fmt in ("json", "jsonl"):
        print(format_json(combined))
    elif fmt == "quiet":
        # Just print ok/error for agents
        print(health.get("api_status", "unknown"))
    else:
        table = Table(title="API Status", show_header=False, pad_edge=False)
        table.add_column("Key", style="bold", width=14)
        table.add_column("Value")
        table.add_row("API", health.get("api_status", "unknown"))
        table.add_row("Database", health.get("database", "unknown"))
        table.add_row("Redis", health.get("redis", "unknown"))
        total = paper_health.get("total_papers", 0)
        with_repos = paper_health.get("papers_with_repos", 0)
        table.add_row("Total Papers", f"{total:,}" if total else "unknown")
        table.add_row("With Code", f"{with_repos:,}" if with_repos else "unknown")
        print_table(table)
