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
    with_repos: bool = typer.Option(
        True,
        "--with-repos/--no-repos",
        help=(
            "In JSON / JSONL output, also include the paper's confident "
            "repositories (tier + engineering fields) and fork-graph. "
            "Ignored by table / csv / bibtex / quiet formats. Default on."
        ),
    ),
) -> None:
    """Get details for a specific paper."""
    fmt = state.output.value
    arxiv_id = extract_arxiv_id(paper_id)
    try:
        with Client(base_url=state.api_url, api_key=state.api_key, ca_bundle=state.ca_bundle, timeout=state.timeout) as client:
            data = client.get_paper(arxiv_id)
            # Best-effort enrichment for machine-readable formats only —
            # surface tier + engineering fields + fork-graph so agents that
            # shell out to `codeofpaper paper -o json <id>` get the full
            # reproducibility-graph context in one call. Failures fall back
            # silently to the bare paper payload.
            if with_repos and fmt in ("json", "jsonl") and isinstance(data, dict):
                try:
                    repos_resp = client.get_paper_repos(
                        arxiv_id, limit=10, include_possible=False
                    )
                    if isinstance(repos_resp, dict):
                        data["repos"] = repos_resp.get("top_repos", [])
                        paper_meta = repos_resp.get("paper")
                        if isinstance(paper_meta, dict) and paper_meta.get(
                            "no_confident_match"
                        ):
                            data["no_confident_match"] = True
                except (APIError, ConnectionError_):
                    pass
                try:
                    fg = client.get_paper_fork_graph(arxiv_id)
                    if isinstance(fg, dict):
                        data["fork_graph"] = fg.get("repos", [])
                except (APIError, ConnectionError_):
                    pass
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code) from None

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
