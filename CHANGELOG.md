# Changelog

## 0.3.1 — 2026-05-31

Repository hygiene + public-launch prep. No CLI or MCP surface changes.

### Added

- `LICENSE` file (MIT) shipped in sdist + wheel (pyproject already declared MIT, but the file was missing on disk).
- `[project.urls]` entries for Repository, Issues, Changelog — surfaced in the PyPI sidebar.
- GitHub Actions CI: `pytest` + `ruff` matrix on Python 3.10-3.13.
- README documents the `CODEOFPAPER_TIMEOUT` env var (previously undocumented).

### Fixed

- CLI error output no longer shows the spurious *"During handling of the above exception, another exception occurred"* tail — all `typer.Exit` and re-raised API errors now use `raise ... from None` / `from exc` (21 sites).

### Internal

- Ruff lint config under `[tool.ruff.lint]`; `B008` ignored project-wide (Typer's recommended `arg = typer.Option(...)` pattern); per-file `PLR2004` / `PLC0415` ignored for tests.
- `contextlib.suppress(Exception)` for the MCP User-Agent override (was `try/except/pass`).
- Modernised type annotations: `Optional[X]` → `X | None`, `typing.Sequence` → `collections.abc.Sequence`.
- Removed unused imports across the package and test suite.
- All 339 tests pass; ruff is clean.

## 0.3.0 — 2026-05-22

Optional MCP (Model Context Protocol) server. Exposes paper / code lookup
as tools to Claude Desktop, Cursor, Continue, Cline, Zed, and any other
MCP-compatible agent. Read-only, no auth, distribution-only release —
the existing CLI surface is unchanged.

### Added

- New optional extra `codeofpaper[mcp]` pulling in `fastmcp>=2.0,<3.0`.
- New console script `codeofpaper-mcp` speaking MCP over stdio.
- Three tools registered: `paper_lookup(paper_id_or_url)`, `code_for_paper(paper_id_or_url, limit, include_possible)`, `search_papers(query, limit, year, venue, has_code)`.
- Per-call MCP traffic is tagged with a `codeofpaper-mcp/<version>` User-Agent so server-side telemetry can distinguish MCP from CLI installs.
- API errors surface as `{"error": "...", "status": N}` dicts (never thrown) so MCP clients always get structured tool output.
- `CODEOFPAPER_API_URL` env var honoured by the MCP server for self-hosted / dev backends.
- README: new "MCP Server (optional)" section with Claude Desktop / Cursor / Continue config snippets.

## 0.2.0 — 2026-05-20

Tier + fork-graph surfacing. Aligns the CLI with the backend's Phase 0c
engineering metadata so agents that shell out get the full reproducibility
context in one call.

### Added

- `paper -o json` / `-o jsonl`: now also fetches `/papers/{id}/repos` (confident matches only) and `/papers/{id}/fork-graph` and merges them into the JSON payload as `repos`, `no_confident_match`, and `fork_graph`. Best-effort — enrichment failures fall back silently to the bare paper payload.
- `paper --with-repos / --no-repos` (default on) to skip the enrichment calls when you only need the bare paper record.
- `code -o json` / `-o jsonl`: now also fetches `/papers/{id}/fork-graph` and merges it as `fork_graph`.
- `code --with-fork-graph / --no-fork-graph` (default on) to skip the fork-graph call.
- `code -o csv`: new columns `tier`, `framework`, `license_spdx` so spreadsheets / agents can filter on Phase 0c confidence tier and engineering metadata.
- `code` default table: new `Tier` column (official / hcc / possible) replaces the `Official` column.
- Client: new `get_paper_fork_graph(paper_id, parent_limit=3, forks_per_parent=5)` method on `Client`.
- Client: `get_paper_repos` gains an optional `include_possible: bool | None = None` parameter (only sent on the wire when explicitly set, so server-side default behaviour is preserved).

### Changed

- `code` default table column set: `Repository | Tier | Stars | Forks | Score`. Framework / license remain available in `-o json` and `-o csv`.

## 0.1.3 — 2026-05-11

### Added

- `search` command: `--year`, `--after`, `--before`, `--venue` filters matching the API. `--after` / `--before` accept `YYYY` (expanded to Jan 1 / Dec 31) or `YYYY-MM-DD`.
- Per-phase HTTP timeouts: connect phase capped at 10s (or `--timeout`, whichever is lower) so corporate networks that black-hole packets fail fast instead of hanging until the global timeout.

### Fixed

- More precise error messages for connect-vs-read timeouts; connect failures now suggest checking network/proxy or passing `--api-url`.

## 0.1.2 — 2026-04-01

### Added

- `--timeout` flag and `CODEOFPAPER_TIMEOUT` env var (default: 30s, was 10s).

### Fixed

- `status` command now reads correct API response keys (`status`, `services.database`, `services.redis`, `paper_count`).

## 0.1.1 — 2026-04-01

### Added

- `--ca-bundle` flag, `CODEOFPAPER_CA_BUNDLE` env var, and `ca_bundle` config key for custom TLS certificate bundles. Fixes SSL errors behind corporate proxies that perform TLS inspection.
- Documentation for corporate proxy / custom TLS setup in README.

## 0.1.0 — 2026-03-18

Initial release.
