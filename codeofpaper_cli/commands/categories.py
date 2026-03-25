"""List categories or get category details."""

from typing import Optional

import typer
from rich.table import Table

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import (
    build_category_table,
    format_csv,
    format_json,
    format_jsonl,
    format_quiet,
    print_error,
    print_table,
)
from codeofpaper_cli.state import state


def categories(
    category_id: Optional[str] = typer.Argument(None, help="Category ID for details (e.g. cv_classification)."),
) -> None:
    """List all categories or get details for one."""
    fmt = state.output.value
    try:
        with Client(base_url=state.api_url, api_key=state.api_key) as client:
            if category_id:
                data = client.get_category(category_id)
            else:
                data = client.get_categories()
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    if category_id:
        _output_category_detail(data, fmt)
    else:
        _output_category_list(data, fmt)


def _output_category_detail(data: dict, fmt: str) -> None:
    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl([data]))
    elif fmt == "quiet":
        print(data.get("id", ""))
    elif fmt == "csv":
        print(format_csv([data], columns=["id", "name", "area", "paper_count"]))
    else:
        table = Table(
            title=f"Category: {data.get('name', '')}",
            show_header=False, pad_edge=False,
        )
        table.add_column("Key", style="bold", width=12)
        table.add_column("Value")
        table.add_row("ID", data.get("id", ""))
        table.add_row("Name", data.get("name", ""))
        table.add_row("Area", data.get("area", ""))
        table.add_row("Papers", str(data.get("paper_count", "")))
        print_table(table)


def _output_category_list(data: dict, fmt: str) -> None:
    areas = data.get("areas", [])
    # Flatten for non-table formats
    flat = []
    for area in areas:
        for cat in area.get("categories", []):
            flat.append({**cat, "area": area.get("name", "")})

    if fmt == "json":
        print(format_json(data))
    elif fmt == "jsonl":
        print(format_jsonl(flat))
    elif fmt == "quiet":
        print(format_quiet(flat, id_key="id"))
    elif fmt == "csv":
        print(format_csv(flat, columns=["id", "name", "area", "paper_count"]))
    else:
        print_table(build_category_table(areas))
