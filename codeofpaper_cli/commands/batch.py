"""Process multiple queries/IDs from stdin or file.

Always outputs JSONL regardless of -o flag:
    {"input": "2010.11929", "status": "ok", "data": {...}}
    {"input": "9999.99999", "status": "error", "error": "Not found"}

Usage:
    echo "2010.11929\\n1706.03762" | codeofpaper batch paper
    codeofpaper batch search ids.txt
    codeofpaper batch code ids.txt --delay 1.0
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import typer

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.state import state
from codeofpaper_cli.url_parser import extract_arxiv_id

# Maps command name → (client_method, input_transform)
# input_transform: how to call the method given a single input line
_COMMANDS: dict[str, str] = {
    "paper": "get_paper",
    "search": "search_papers",
    "code": "get_paper_repos",
    "similar": "get_similar",
    "suggest": "suggest",
}


def _read_inputs(file: str | None) -> list[str]:
    """Read input lines from file or stdin, stripping blanks."""
    if file:
        path = Path(file)
        if not path.exists():
            typer.echo(f"Error: file not found: {file}", err=True)
            raise typer.Exit(code=1)
        text = path.read_text()
    else:
        if sys.stdin.isatty():
            typer.echo("Reading from stdin (Ctrl+D to finish):", err=True)
        text = sys.stdin.read()
    return [line.strip() for line in text.splitlines() if line.strip()]


def _call(client: Client, method_name: str, input_line: str) -> dict[str, Any]:
    """Call the appropriate client method for one input line."""
    if method_name == "search_papers":
        return client.search_papers(query=input_line)
    if method_name == "suggest":
        return {"suggestions": client.suggest(query=input_line)}
    # Paper-based commands: normalize arXiv ID
    paper_id = extract_arxiv_id(input_line)
    method = getattr(client, method_name)
    return method(paper_id)


def _emit(record: dict[str, Any]) -> None:
    """Write a single JSONL record to stdout."""
    print(json.dumps(record, default=str, ensure_ascii=False), flush=True)


def batch(
    command: str = typer.Argument(..., help="Command to batch: paper, search, code, similar, suggest."),
    file: Optional[str] = typer.Argument(None, help="File with one query/ID per line (default: stdin)."),
    delay: float = typer.Option(0.5, "--delay", min=0.1, help="Delay between API calls in seconds (min 0.1)."),
) -> None:
    """Process multiple queries/IDs from stdin or a file.

    Always outputs JSONL (one JSON object per input line).
    """
    cmd = command.lower()
    if cmd not in _COMMANDS:
        typer.echo(
            f"Error: unknown batch command '{cmd}'. "
            f"Supported: {', '.join(sorted(_COMMANDS))}",
            err=True,
        )
        raise typer.Exit(code=1)

    method_name = _COMMANDS[cmd]
    inputs = _read_inputs(file)

    if not inputs:
        typer.echo("No input lines provided.", err=True)
        raise typer.Exit(code=0)

    ok = 0
    errors = 0

    with Client(base_url=state.api_url, api_key=state.api_key, ca_bundle=state.ca_bundle, timeout=state.timeout) as client:
        for i, input_line in enumerate(inputs):
            try:
                data = _call(client, method_name, input_line)
                _emit({"input": input_line, "status": "ok", "data": data})
                ok += 1
            except (APIError, ConnectionError_) as exc:
                _emit({"input": input_line, "status": "error", "error": str(exc)})
                errors += 1

            # Delay between calls (skip after last)
            if i < len(inputs) - 1 and delay > 0:
                time.sleep(delay)

    typer.echo(f"Batch complete: {ok} ok, {errors} errors, {len(inputs)} total.", err=True)
