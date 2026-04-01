"""Structured research overview of a topic.

Multi-step orchestration:
  shallow: search only + landscape statistics
  medium:  search + repos for top papers (default)
  deep:    search + repos + similar papers from #1
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from codeofpaper_cli.client import APIError, Client, ConnectionError_
from codeofpaper_cli.formatters import (
    _format_stars,
    _official_indicator,
    _truncate,
    format_bibtex,
    format_csv,
    format_json,
    format_jsonl,
    format_quiet,
    print_error,
    print_table,
)
from codeofpaper_cli.state import state

_console = Console(stderr=True)


def research(
    query: str = typer.Argument(..., help="Research topic query."),
    depth: str = typer.Option("medium", "--depth", help="Depth: shallow, medium, deep."),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum papers in overview."),
) -> None:
    """Structured research overview of a topic."""
    fmt = state.output.value

    if depth not in ("shallow", "medium", "deep"):
        print_error(f"Invalid depth: {depth!r}. Use shallow, medium, or deep.", fmt)
        raise typer.Exit(code=1)

    try:
        with Client(base_url=state.api_url, api_key=state.api_key, ca_bundle=state.ca_bundle, timeout=state.timeout) as client:
            result = _run_research(client, query, depth, limit)
    except (APIError, ConnectionError_) as exc:
        print_error(str(exc), fmt)
        raise typer.Exit(code=exc.exit_code)

    _output_result(result, fmt)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _run_research(
    client: Client, query: str, depth: str, limit: int,
) -> dict[str, Any]:
    """Run the research pipeline and return structured results."""
    api_calls = 0
    warnings: list[dict[str, str]] = []

    # Step 1: Search
    search_data = client.search_papers(query=query, limit=limit, sort_by="relevant")
    api_calls += 1
    papers = search_data.get("papers", [])

    # Build landscape stats from search results
    landscape = _build_landscape(papers)

    # Step 2 (medium/deep): Get repos for top papers
    all_repos: list[dict] = []
    if depth in ("medium", "deep"):
        repo_limit = min(len(papers), 5)
        for p in papers[:repo_limit]:
            pid = p.get("arxiv_id", "")
            try:
                repos_data = client.get_paper_repos(pid, limit=5)
                api_calls += 1
                top_repos = repos_data.get("top_repos", [])
                for r in top_repos:
                    r["_paper_id"] = pid
                all_repos.extend(top_repos)
            except APIError as exc:
                warnings.append({"paper_id": pid, "error": str(exc)})

    # Dedupe & sort repos by stars
    seen_repos: set[str] = set()
    unique_repos: list[dict] = []
    for r in sorted(all_repos, key=lambda x: x.get("stars", 0), reverse=True):
        name = r.get("full_name", "")
        if name not in seen_repos:
            seen_repos.add(name)
            unique_repos.append(r)

    # Step 3 (deep): Follow similar from #1
    related: list[dict] = []
    if depth == "deep" and papers:
        top_id = papers[0].get("arxiv_id", "")
        try:
            sim_data = client.get_similar(top_id, limit=6)
            api_calls += 1
            related = sim_data.get("similar", [])
            if sim_data.get("error"):
                warnings.append({"paper_id": top_id, "error": sim_data["error"]})
                related = []
        except APIError as exc:
            warnings.append({"paper_id": top_id, "error": f"similar: {exc}"})

    return {
        "query": query,
        "depth": depth,
        "landscape": landscape,
        "papers": papers,
        "repos": unique_repos[:10],
        "related": related,
        "warnings": warnings,
        "_meta": {"api_calls": api_calls},
    }


def _build_landscape(papers: list[dict]) -> dict[str, Any]:
    """Aggregate field statistics from search result papers."""
    total = len(papers)
    with_code = sum(1 for p in papers if p.get("has_repos") or p.get("repo_count", 0) > 0)
    official = sum(1 for p in papers if p.get("has_official_repo"))

    # Category distribution
    cat_counter: Counter[str] = Counter()
    for p in papers:
        for cat in p.get("categories", []):
            cat_counter[str(cat)] += 1
    top_categories = cat_counter.most_common(5)

    # Date range
    dates = [p.get("published_date", "") for p in papers if p.get("published_date")]
    dates_sorted = sorted(d for d in dates if d)
    date_range = (dates_sorted[0][:7], dates_sorted[-1][:7]) if dates_sorted else ("", "")

    return {
        "total_papers": total,
        "with_code": with_code,
        "official_repos": official,
        "top_categories": [{"category": c, "count": n} for c, n in top_categories],
        "date_range": list(date_range),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _output_result(result: dict[str, Any], fmt: str) -> None:
    """Dispatch result to the appropriate output format."""
    papers = result["papers"]

    if fmt == "json":
        print(format_json(result))
    elif fmt == "jsonl":
        print(format_jsonl(papers))
    elif fmt == "quiet":
        print(format_quiet(papers))
    elif fmt == "csv":
        print(format_csv(
            papers, columns=["arxiv_id", "title", "published_date", "repo_count"],
        ))
    elif fmt == "bibtex":
        print(format_bibtex(papers))
    else:
        _print_research_table(result)


def _print_research_table(result: dict[str, Any]) -> None:
    """Print the rich multi-section research report."""
    console = Console()
    query = result["query"]
    landscape = result["landscape"]
    papers = result["papers"]
    repos = result["repos"]
    related = result["related"]
    warnings = result["warnings"]
    api_calls = result["_meta"]["api_calls"]

    console.print()
    console.print(f"[bold]Research: \"{query}\"[/bold]")
    console.print()

    # --- Landscape section ---
    total = landscape["total_papers"]
    with_code = landscape["with_code"]
    official = landscape["official_repos"]
    top_cats = landscape["top_categories"]
    date_range = landscape["date_range"]

    console.print("[bold]📊 Landscape[/bold]")
    code_pct = f" ({with_code * 100 // total}%)" if total else ""
    console.print(f"  Papers found:   {total:<12} With code: {with_code}{code_pct}")
    console.print(f"  Official repos: {official:<12} Date range: {date_range[0]} → {date_range[1]}")
    if top_cats:
        cats_str = ", ".join(f"{c['category']} ({c['count']})" for c in top_cats[:3])
        console.print(f"  Top areas:      {cats_str}")
    console.print()

    # --- Key Papers section ---
    if papers:
        table = Table(
            title="📄 Key Papers", show_header=True, header_style="bold", pad_edge=False,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("ArXiv ID", style="cyan", width=12)
        table.add_column("Title", min_width=30, max_width=45)
        table.add_column("Stars", justify="right", width=7)
        table.add_column("Code", justify="center", width=12)

        for i, p in enumerate(papers, 1):
            code_str = ""
            if p.get("has_repos") or p.get("repo_count", 0) > 0:
                code_str = "✓"
                if p.get("has_official_repo"):
                    code_str = "✓ official"
            stars = p.get("max_stars") or p.get("repo_count", 0)
            table.add_row(
                str(i),
                p.get("arxiv_id", ""),
                _truncate(p.get("title", ""), 42),
                _format_stars(stars) if stars else "",
                code_str,
            )
        print_table(table)
        console.print()

    # --- Top Implementations section ---
    if repos:
        table = Table(
            title="🔗 Top Implementations", show_header=True, header_style="bold", pad_edge=False,
        )
        table.add_column("Repository", min_width=25, max_width=38)
        table.add_column("Paper", style="cyan", width=12)
        table.add_column("Stars", justify="right", width=7)
        table.add_column("Official", justify="center", width=8)

        for r in repos[:8]:
            table.add_row(
                _truncate(r.get("full_name", ""), 35),
                r.get("_paper_id", ""),
                _format_stars(r.get("stars")),
                _official_indicator(r),
            )
        print_table(table)
        console.print()

    # --- Related section (deep only) ---
    if related:
        table = Table(
            title="🔭 Related (via semantic similarity to #1)",
            show_header=True, header_style="bold", pad_edge=False,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("ArXiv ID", style="cyan", width=12)
        table.add_column("Title", min_width=30, max_width=45)
        table.add_column("Similarity", justify="right", width=10)

        for i, s in enumerate(related, 1):
            score = s.get("similarity_score", s.get("similarity", ""))
            score_str = f"{score:.2f}" if isinstance(score, float) else str(score)
            table.add_row(
                str(i),
                s.get("arxiv_id", ""),
                _truncate(s.get("title", ""), 42),
                score_str,
            )
        print_table(table)
        console.print()

    # --- Warnings footer ---
    if warnings:
        console.print(f"[yellow]⚠ {len(warnings)} item(s) skipped:[/yellow]")
        for w in warnings:
            console.print(f"  {w['paper_id']}: {w['error']}", style="dim")
        console.print()

    console.print(f"[dim]({api_calls} API calls, depth={result['depth']})[/dim]")
