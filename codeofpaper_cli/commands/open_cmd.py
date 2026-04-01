"""Open a paper or its top repo in the browser."""

import typer

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import print_error
from codeofpaper_cli.state import state
from codeofpaper_cli.url_parser import extract_arxiv_id


def open_paper(
    paper_id: str = typer.Argument(..., help="ArXiv ID or URL (e.g. 2010.11929)."),
    code: bool = typer.Option(False, "--code", help="Open the top GitHub repo instead."),
    pdf: bool = typer.Option(False, "--pdf", help="Open the PDF directly."),
) -> None:
    """Open a paper or its top repo in the browser."""
    fmt = state.output.value
    arxiv_id = extract_arxiv_id(paper_id)

    if code:
        # Fetch repos and open the top one
        try:
            with Client(base_url=state.api_url, api_key=state.api_key, ca_bundle=state.ca_bundle, timeout=state.timeout) as client:
                data = client.get_paper_repos(arxiv_id, limit=1)
        except (APIError, ConnectionError_) as exc:
            print_error(str(exc), fmt)
            raise typer.Exit(code=exc.exit_code)

        repos = data.get("top_repos", [])
        if not repos:
            print_error(f"No repos found for {arxiv_id}.", fmt)
            raise typer.Exit(code=1)
        url = repos[0].get("html_url", f"https://github.com/{repos[0].get('full_name', '')}")
    elif pdf:
        url = f"https://arxiv.org/pdf/{arxiv_id}"
    else:
        url = f"https://arxiv.org/abs/{arxiv_id}"

    typer.launch(url)
    if fmt not in ("json", "quiet"):
        typer.echo(f"Opened: {url}")
