"""Output formatters for CLI commands.

Supports 6 output formats:
- table: Human-readable Rich tables (default)
- json: Full JSON pass-through
- quiet: IDs only, one per line
- jsonl: One JSON object per line
- bibtex: BibTeX entries (paper/search commands)
- csv: CSV with headers

Error formatting follows the Polymarket pattern:
- table mode → human message to stderr
- json/jsonl mode → {"error": "..."} to stdout
- quiet mode → exit code only (no output)
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any
from collections.abc import Sequence

from rich.console import Console
from rich.table import Table

# Shared console for stderr (errors/status) and stdout (output)
_err_console = Console(stderr=True)
_out_console = Console()


# ---------------------------------------------------------------------------
# JSON / JSONL
# ---------------------------------------------------------------------------


def format_json(data: Any) -> str:
    """Format data as pretty-printed JSON."""
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def format_jsonl(items: Sequence[dict]) -> str:
    """Format a list of items as JSONL (one JSON object per line)."""
    lines = [json.dumps(item, default=str, ensure_ascii=False) for item in items]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quiet (IDs only)
# ---------------------------------------------------------------------------


def format_quiet(items: Sequence[dict], id_key: str = "arxiv_id") -> str:
    """Format items as IDs only, one per line.

    Falls back to 'id' if id_key is missing from an item.
    """
    ids = []
    for item in items:
        val = item.get(id_key) or item.get("id", "")
        if val:
            ids.append(str(val))
    return "\n".join(ids)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def format_csv(items: Sequence[dict], columns: list[str] | None = None) -> str:
    """Format items as CSV with headers.

    If columns is None, uses keys from the first item.
    """
    if not items:
        return ""
    if columns is None:
        columns = list(items[0].keys())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow({k: item.get(k, "") for k in columns})
    return output.getvalue().rstrip("\n")


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------


def _format_bibtex_author(name: str) -> str:
    """Convert a name like 'First Middle Last' to 'Last, First Middle'.

    Best-effort: splits on last space. Single-word names pass through.
    """
    parts = name.strip().split()
    if len(parts) <= 1:
        return name.strip()
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def _format_bibtex_authors(authors: list[str]) -> str:
    """Format an author list for BibTeX: '{Last, First and Last, First}'."""
    if not authors:
        return ""
    formatted = [_format_bibtex_author(a) for a in authors]
    return " and ".join(formatted)


def format_bibtex_entry(paper: dict) -> str:
    """Format a single paper as a BibTeX entry."""
    arxiv_id = paper.get("arxiv_id", paper.get("id", "unknown"))
    # BibTeX key: replace dots/slashes with underscores
    key = arxiv_id.replace(".", "_").replace("/", "_")
    title = paper.get("title", "")
    authors = _format_bibtex_authors(paper.get("authors", []))
    year = ""
    pub_date = paper.get("published_date", "")
    if pub_date:
        year = str(pub_date)[:4]
    url = paper.get("url", f"https://arxiv.org/abs/{arxiv_id}")
    summary = paper.get("summary", "")

    lines = [f"@article{{{key},"]
    lines.append(f"  title     = {{{title}}},")
    if authors:
        lines.append(f"  author    = {{{authors}}},")
    if year:
        lines.append(f"  year      = {{{year}}},")
    lines.append(f"  url       = {{{url}}},")
    lines.append(f"  eprint    = {{{arxiv_id}}},")
    lines.append("  archivePrefix = {arXiv},")
    if summary:
        # Truncate very long abstracts for BibTeX
        abstract = summary[:500] + ("..." if len(summary) > 500 else "")
        lines.append(f"  abstract  = {{{abstract}}},")
    lines.append("}")
    return "\n".join(lines)


def format_bibtex(papers: Sequence[dict]) -> str:
    """Format multiple papers as BibTeX entries."""
    return "\n\n".join(format_bibtex_entry(p) for p in papers)


# ---------------------------------------------------------------------------
# Rich table helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if not text or len(text) <= max_len:
        return text or ""
    return text[: max_len - 3] + "..."


def _format_stars(stars: int | None) -> str:
    """Format star count: 1234 → '1.2k', 12345 → '12.3k'."""
    if not stars:
        return ""
    if stars >= 1000:
        return f"{stars / 1000:.1f}k"
    return str(stars)


def _code_indicator(item: dict) -> str:
    """Return ✓ if paper has code, empty string otherwise."""
    if item.get("has_repos") or item.get("repo_count", 0) > 0:
        return "✓"
    return ""


def _official_indicator(item: dict) -> str:
    """Return ✓ if repo is official, empty string otherwise."""
    if item.get("is_official") or item.get("has_official_repo"):
        return "✓"
    return ""


def build_paper_detail_table(paper: dict) -> Table:
    """Build a Rich key-value table for a single paper detail view."""
    arxiv_id = paper.get("arxiv_id", paper.get("id", "unknown"))
    table = Table(
        title=f"Paper: {arxiv_id}",
        show_header=False,
        pad_edge=False,
    )
    table.add_column("Key", style="bold", width=14)
    table.add_column("Value")

    table.add_row("Title", paper.get("title", ""))

    authors = paper.get("authors", [])
    if authors:
        if len(authors) <= 3:
            table.add_row("Authors", ", ".join(authors))
        else:
            table.add_row(
                "Authors", f"{', '.join(authors[:3])} et al. ({len(authors)} total)"
            )

    table.add_row("Published", str(paper.get("published_date", ""))[:10])

    cats = paper.get("categories", [])
    if cats:
        table.add_row("Categories", ", ".join(str(c) for c in cats))

    repo_count = paper.get("repo_count", 0)
    has_repos = paper.get("has_repos", False)
    official = paper.get("has_official_repo", False)
    if has_repos or repo_count:
        code_text = f"✓ {repo_count} repos"
        if official:
            code_text += " (official)"
        table.add_row("Code", code_text)
    else:
        table.add_row("Code", "No repos found")

    confs = paper.get("conferences", [])
    if confs:
        conf_names = []
        for c in confs:
            if isinstance(c, dict):
                conf_names.append(c.get("name", str(c)))
            else:
                conf_names.append(str(c))
        table.add_row("Conferences", ", ".join(conf_names))

    url = paper.get("url", f"https://arxiv.org/abs/{arxiv_id}")
    table.add_row("URL", url)

    summary = paper.get("summary", "")
    if summary:
        table.add_row("Summary", _truncate(summary, 200))

    return table


def build_paper_table(
    papers: Sequence[dict],
    title: str | None = None,
    show_score: bool = False,
    score_key: str = "similarity_score",
    show_rank: bool = False,
) -> Table:
    """Build a Rich table for a list of papers.

    Handles both search results, trending, similar, and conference papers.
    """
    table = Table(title=title, show_header=True, header_style="bold", pad_edge=False)

    if show_rank:
        table.add_column("#", style="dim", width=3)
    table.add_column("ArXiv ID", style="cyan", width=12)
    table.add_column("Title", min_width=30, max_width=50)
    if show_score:
        table.add_column(score_key.replace("_", " ").title(), justify="right", width=10)
    table.add_column("Date", width=10)
    table.add_column("Code", justify="center", width=4)
    table.add_column("Repos", justify="right", width=5)

    for i, p in enumerate(papers, 1):
        arxiv_id = p.get("arxiv_id", p.get("id", ""))
        title_text = _truncate(p.get("title", ""), 47)
        date = str(p.get("published_date", ""))[:10]
        code = _code_indicator(p)
        repos = str(p.get("repo_count", "")) if p.get("repo_count") else ""

        row: list[str] = []
        if show_rank:
            row.append(str(i))
        row.extend([str(arxiv_id), title_text])
        if show_score:
            score_val = p.get(score_key, p.get("similarity", ""))
            if isinstance(score_val, float):
                row.append(f"{score_val:.2f}")
            else:
                row.append(str(score_val) if score_val else "")
        row.extend([date, code, repos])
        table.add_row(*row)

    return table


def build_repo_table(repos: Sequence[dict], title: str | None = None) -> Table:
    """Build a Rich table for a list of repos."""
    table = Table(title=title, show_header=True, header_style="bold", pad_edge=False)

    table.add_column("Repository", min_width=25, max_width=40)
    # Phase 0c tier (official / hcc / possible_match) replaces the old
    # "Official" column. Framework + license / license_spdx are in `-o json`
    # / `-o csv` to keep the default table within an 80-column terminal.
    table.add_column("Tier", width=9)
    table.add_column("Stars", justify="right", width=7)
    table.add_column("Forks", justify="right", width=7)
    table.add_column("Score", justify="right", width=6)

    for r in repos:
        table.add_row(
            _truncate(r.get("full_name", ""), 37),
            _tier_label(r.get("tier")),
            _format_stars(r.get("stars")),
            str(r.get("forks", "")),
            f"{r.get('score', 0):.2f}" if r.get("score") else "",
        )

    return table


_TIER_LABELS = {
    "official": "official",
    "high_confidence_community": "hcc",
    "possible_match": "possible",
}


def _tier_label(tier: str | None) -> str:
    """Compact label for the tier column. Empty when unknown."""
    if not tier:
        return ""
    return _TIER_LABELS.get(tier, str(tier))


def build_category_table(areas: Sequence[dict]) -> Table:
    """Build a grouped table for categories listing."""
    table = Table(show_header=True, header_style="bold", pad_edge=False)

    table.add_column("Area", min_width=20)
    table.add_column("ID", style="cyan", width=22)
    table.add_column("Name", min_width=25)
    table.add_column("Papers", justify="right", width=8)

    for area in areas:
        area_name = area.get("name", "")
        for i, cat in enumerate(area.get("categories", [])):
            table.add_row(
                area_name if i == 0 else "",
                cat.get("id", ""),
                cat.get("name", ""),
                str(cat.get("paper_count", "")),
            )

    return table


def build_conference_table(conferences: Sequence[dict]) -> Table:
    """Build a Rich table for conference listing."""
    table = Table(show_header=True, header_style="bold", pad_edge=False)

    table.add_column("Conference", width=12)
    table.add_column("Year", width=6)
    table.add_column("Papers", justify="right", width=8)
    table.add_column("With Code", justify="right", width=10)
    table.add_column("Code %", justify="right", width=8)

    for c in conferences:
        pct = c.get("github_percentage", 0)
        table.add_row(
            c.get("name", c.get("series", "")),
            str(c.get("year", "")),
            str(c.get("total_papers", "")),
            str(c.get("papers_with_code", "")),
            f"{pct:.1f}%" if pct else "",
        )

    return table


def build_code_drops_table(drops: Sequence[dict]) -> Table:
    """Build a table for recent code drops."""
    table = Table(
        title="\U0001f195 Recent Code Drops", show_header=True, header_style="bold", pad_edge=False
    )

    table.add_column("Paper", min_width=30, max_width=45)
    table.add_column("Repo", min_width=20, max_width=30)
    table.add_column("Stars", justify="right", width=7)
    table.add_column("Conference", width=12)
    table.add_column("Official", justify="center", width=8)

    for d in drops:
        table.add_row(
            _truncate(d.get("paper_title", ""), 42),
            _truncate(d.get("repo_name", ""), 27),
            _format_stars(d.get("repo_stars")),
            d.get("conference_name", ""),
            "✓" if d.get("is_official") else "",
        )

    return table


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------


def print_error(message: str, output_format: str) -> None:
    """Print an error in the appropriate format.

    - table: human message to stderr
    - json/jsonl: {"error": "..."} to stdout
    - quiet: nothing (caller handles exit code)
    - csv/bibtex: human message to stderr
    """
    if output_format in ("json", "jsonl"):
        print(json.dumps({"error": message}))
    elif output_format == "quiet":
        pass  # exit code only
    else:
        _err_console.print(f"[red]Error:[/red] {message}")


# ---------------------------------------------------------------------------
# Convenience: render a Rich table to stdout
# ---------------------------------------------------------------------------


def print_table(table: Table) -> None:
    """Print a Rich table to stdout."""
    _out_console.print(table)
