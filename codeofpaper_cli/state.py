"""Global CLI state shared between main.py and command modules."""

from __future__ import annotations

from enum import Enum


class OutputFormat(str, Enum):
    """Output format for CLI commands."""

    table = "table"
    json = "json"
    quiet = "quiet"
    jsonl = "jsonl"
    bibtex = "bibtex"
    csv = "csv"


class State:
    """Global CLI state passed to all commands via context."""

    output: OutputFormat = OutputFormat.table
    api_url: str = "https://api.codeofpaper.com"
    api_key: str | None = None
    ca_bundle: str | None = None
    timeout: float | None = None


state = State()
