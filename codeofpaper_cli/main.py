"""Code of Paper CLI — discover GitHub implementations of research papers.

Usage:
    codeofpaper search "transformers"
    codeofpaper paper 2010.11929
    codeofpaper code 2010.11929
    codeofpaper trending --has-code
    codeofpaper -o json trending | jq '...'

Install shell completion:
    codeofpaper --install-completion

Full docs: https://codeofpaper.com
"""


import typer

from codeofpaper_cli import __version__
from codeofpaper_cli.state import OutputFormat, state
from codeofpaper_cli.commands import (
    auth,
    batch,
    categories,
    code,
    code_drops,
    conference,
    conferences,
    export,
    open_cmd,
    paper,
    random,
    repo,
    research,
    search,
    similar,
    status,
    suggest,
    trending,
)


app = typer.Typer(
    name="codeofpaper",
    help=(
        "Code of Paper CLI — discover GitHub implementations of research papers.\n\n"
        "Search 181k+ arXiv papers and find their code on GitHub.\n"
        "Works for humans and AI agents alike.\n\n"
        "Output formats: table (default), json, quiet, jsonl, bibtex, csv\n\n"
        "Install shell completion: codeofpaper --install-completion"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"codeofpaper {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(
        OutputFormat.table,
        "-o",
        "--output",
        help="Output format: table, json, quiet, jsonl, bibtex, csv.",
        envvar="CODEOFPAPER_OUTPUT",
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Shortcut for -o quiet (IDs only, one per line).",
    ),
    api_url: str = typer.Option(
        "https://api.codeofpaper.com",
        "--api-url",
        help="Override API base URL.",
        envvar="CODEOFPAPER_API_URL",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Override API key (default: from config file).",
        envvar="CODEOFPAPER_API_KEY",
    ),
    ca_bundle: str | None = typer.Option(
        None,
        "--ca-bundle",
        help="Path to a CA certificate bundle (PEM) for TLS verification.",
        envvar="CODEOFPAPER_CA_BUNDLE",
    ),
    timeout: float | None = typer.Option(
        None,
        "--timeout",
        help="Request timeout in seconds (default: 30).",
        envvar="CODEOFPAPER_TIMEOUT",
    ),
    version: bool = typer.Option(
        False,
        "-v",
        "--version",
        help="Print version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Global options applied before any subcommand."""
    from codeofpaper_cli import config

    cfg = config.load_config()

    # Output: --quiet > --output flag > config default_format > table
    if quiet:
        state.output = OutputFormat.quiet
    elif output != OutputFormat.table:
        # Explicit flag was passed
        state.output = output
    else:
        # Use config default_format (falls back to "table" from DEFAULTS)
        try:
            state.output = OutputFormat(cfg.get("default_format", "table"))
        except ValueError:
            state.output = OutputFormat.table

    # API URL: --api-url flag > env var > config > default
    if api_url != "https://api.codeofpaper.com":
        state.api_url = api_url
    else:
        state.api_url = cfg.get("api_url", "https://api.codeofpaper.com")

    # API key: --api-key flag > env var > config > None
    state.api_key = api_key if api_key is not None else cfg.get("api_key")

    # CA bundle: --ca-bundle flag > env var > config > None (system default)
    state.ca_bundle = ca_bundle if ca_bundle is not None else cfg.get("ca_bundle")

    # Timeout: --timeout flag > env var > config > None (use client default)
    if timeout is not None:
        state.timeout = timeout
    else:
        cfg_timeout = cfg.get("timeout")
        state.timeout = float(cfg_timeout) if cfg_timeout is not None else None


# Register all commands
app.command(name="search", help="Search papers by text query.")(search.search)
app.command(name="paper", help="Get details for a specific paper.")(paper.paper)
app.command(name="code", help="Get GitHub repos implementing a paper.")(code.code)
app.command(name="trending", help="Browse trending papers.")(trending.trending)
app.command(name="categories", help="List categories or get category details.")(
    categories.categories
)
app.command(name="conferences", help="List all conference series with stats.")(
    conferences.conferences
)
app.command(name="conference", help="Browse papers from a specific conference.")(
    conference.conference
)
app.command(name="similar", help="Find semantically similar papers.")(similar.similar)
app.command(name="random", help="Get a random interesting paper.")(random.random_paper)
app.command(name="open", help="Open a paper or repo in the browser.")(open_cmd.open_paper)
app.command(name="repo", help="Reverse lookup: find paper(s) a repo implements.")(repo.repo)
app.command(name="code-drops", help="Recent conference papers with new code.")(
    code_drops.code_drops
)
app.command(name="suggest", help="Autocomplete / quick paper lookup.")(suggest.suggest)
app.command(name="research", help="Structured research overview of a topic.")(research.research)
app.command(name="batch", help="Process multiple queries/IDs from stdin or file.")(batch.batch)
app.command(name="export", help="Bulk export papers as CSV, JSONL, or BibTeX.")(export.export)
app.command(name="auth", help="Manage API key authentication.")(auth.auth)
app.command(name="status", help="Check API health and basic stats.")(status.status)


if __name__ == "__main__":
    app()
