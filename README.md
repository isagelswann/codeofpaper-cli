# Code of Paper CLI

Discover GitHub implementations of research papers — from the terminal.

Search 181k+ arXiv papers and find their code on GitHub. Works for humans and AI agents alike.

[![PyPI](https://img.shields.io/pypi/v/codeofpaper)](https://pypi.org/project/codeofpaper/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/codeofpaper)](https://pypi.org/project/codeofpaper/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Install

```bash
pip install codeofpaper
```

Or with [pipx](https://pipx.pypa.io/) for isolated installs:

```bash
pipx install codeofpaper
```

Requires Python 3.10+. No API key needed — works anonymously at 60 requests/minute.

## Quick Start

```bash
# Search for papers
codeofpaper search "vision transformers"

# Get paper details (arXiv IDs or full URLs both work)
codeofpaper paper 2010.11929
codeofpaper paper https://arxiv.org/abs/2010.11929

# Find code implementations
codeofpaper code 1706.03762

# Browse trending papers with code
codeofpaper trending --has-code

# JSON output for scripts and agents
codeofpaper -o json trending | jq '.trending[] | {title, stars: .max_stars}'

# One-shot reproducibility context for an agent: paper + confident repos
# (with tier + framework + license) + fork-graph in a single JSON payload.
codeofpaper -o json paper 2010.11929 | jq '{title, repos: [.repos[] | {full_name, tier}], forks: [.fork_graph[] | .full_name]}'

# Literature review in one command
codeofpaper research "reinforcement learning" --depth deep
```

## Output Formats

Use `-o` / `--output` **before** the subcommand:

```bash
codeofpaper -o json paper 2010.11929
codeofpaper -o quiet search "attention" | head -5
codeofpaper -o csv trending --has-code > papers.csv
```

| Format | Flag | Use case |
|--------|------|----------|
| Table | `-o table` | Human reading (default) |
| JSON | `-o json` | Scripts, `jq` pipelines, full response data |
| Quiet | `-o quiet` | IDs only, one per line — pipe into other commands |
| JSONL | `-o jsonl` | Streaming, append to files, batch processing |
| BibTeX | `-o bibtex` | Citation managers, LaTeX bibliographies |
| CSV | `-o csv` | Spreadsheets, pandas, data analysis |

The shorthand `-q` is equivalent to `-o quiet`:

```bash
codeofpaper -q search "transformers" | head -3
```

You can set a default format via config so you don't need `-o` every time:

```bash
codeofpaper auth setup    # then edit ~/.config/codeofpaper/config.json
```

## Commands

### Discovery

| Command | Description | Example |
|---------|-------------|---------|
| `search` | Full-text paper search | `codeofpaper search "vision transformers" --has-code` |
| `paper` | Paper details by arXiv ID or URL | `codeofpaper paper 2010.11929` |
| `code` | GitHub repos implementing a paper | `codeofpaper code 1706.03762` |
| `similar` | Semantically similar papers | `codeofpaper similar 2010.11929` |
| `suggest` | Autocomplete / quick lookup | `codeofpaper suggest "attention"` |
| `random` | Random interesting paper | `codeofpaper random --quality high` |

### Browsing

| Command | Description | Example |
|---------|-------------|---------|
| `trending` | Trending papers by category | `codeofpaper trending --category cs.CV --sort hot` |
| `categories` | List categories or get details | `codeofpaper categories cs.AI` |
| `conferences` | List all conference series | `codeofpaper conferences` |
| `conference` | Papers from a specific conference | `codeofpaper conference neurips_2024 --has-code` |
| `code-drops` | Recent conference papers with new code | `codeofpaper code-drops --days 7` |
| `repo` | Reverse lookup: repo → paper | `codeofpaper repo google-research/vision_transformer` |
| `open` | Open paper or repo in browser | `codeofpaper open 2010.11929 --code` |

### Bulk Operations

| Command | Description | Example |
|---------|-------------|---------|
| `research` | Structured research overview | `codeofpaper research "RL" --depth deep` |
| `batch` | Process multiple IDs from stdin/file | `cat ids.txt \| codeofpaper batch paper` |
| `export` | Paginated bulk export | `codeofpaper export trending -o csv > out.csv` |

### Configuration

| Command | Description | Example |
|---------|-------------|---------|
| `auth` | Manage API key (setup/status/clear) | `codeofpaper auth status` |
| `status` | Check API health and stats | `codeofpaper status` |

## Command Details

### search

```bash
codeofpaper search "reinforcement learning" --sort has_code --has-code
codeofpaper search "GAN" --limit 20 --offset 10
```

Options: `--limit`, `--offset`, `--sort` (relevant, recent, has_code), `--has-code`, `--category`.

### research

Multi-step orchestrated overview of a research topic:

```bash
codeofpaper research "vision transformers" --depth deep
```

| Depth | Steps | API calls |
|-------|-------|-----------|
| `shallow` | Search only + landscape statistics | 1 |
| `medium` | Search + repos for top papers (default) | ~6 |
| `deep` | Search + repos + similar papers from #1 | ~8 |

### batch

Process multiple queries or IDs from a file or stdin. Always outputs JSONL regardless of `-o`:

```bash
# From a file
codeofpaper batch paper ids.txt

# From stdin
echo -e "2010.11929\n1706.03762" | codeofpaper batch paper

# Pipe from another command
codeofpaper -q similar 2010.11929 | codeofpaper batch code
```

Supported commands: `paper`, `search`, `code`, `similar`, `suggest`.

Each line produces one JSON object:
```json
{"input": "2010.11929", "status": "ok", "data": {...}}
{"input": "9999.99999", "status": "error", "error": "Not found"}
```

Options: `--delay` (seconds between calls, default 0.5).

### export

Paginated bulk export from trending, conference, or search:

```bash
codeofpaper export trending --category cs.CV --has-code -o csv > cv.csv
codeofpaper export conference neurips_2024 --has-code -o bibtex > neurips.bib
codeofpaper export search "transformers" --max 500 -o jsonl > data.jsonl
```

Auto-paginates through results (100 per page, 0.5s delay). Options: `--max` (default 200), `--has-code`, `--category`, `--days`.

## Agent Integration

The CLI is designed for AI agent consumption. Key features:

### Stable Exit Codes

Agents can branch on exit codes without parsing error messages:

| Exit Code | Meaning | Agent Action |
|-----------|---------|-------------|
| 0 | Success | Parse stdout |
| 1 | General error | Log and report |
| 2 | Connection error | Retry with backoff |
| 3 | Not found (404) | Skip or try different ID |
| 4 | Rate limited (429) | Wait and retry |
| 5 | Auth required (401/403) | Run `codeofpaper auth setup` |

### Machine-Readable Output

```bash
# JSON for structured parsing
codeofpaper -o json paper 2010.11929 | jq '.title'

# Quiet mode for ID lists
codeofpaper -q search "attention" | head -5

# JSONL for streaming
codeofpaper -o jsonl trending --has-code | while read -r line; do
  echo "$line" | jq -r '.arxiv_id'
done
```

### HTTP Cache

Responses are cached on disk for 30 minutes (`~/.cache/codeofpaper/http/`), so repeated calls are instant and free.

## MCP Server (optional)

Code of Paper ships an optional [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes paper / code lookup as tools to any MCP-compatible agent — Claude Desktop, Cursor, Continue, Cline, Zed, etc.

Install with the `mcp` extra:

```bash
pip install 'codeofpaper[mcp]'
# or, with uv:
uv tool install 'codeofpaper[mcp]'
```

This adds a `codeofpaper-mcp` entry point that speaks MCP over stdio.

### Wire into Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "codeofpaper": {
      "command": "codeofpaper-mcp"
    }
  }
}
```

If you installed via `uv tool install`, use `uvx codeofpaper-mcp` instead.

### Wire into Cursor / Continue / Cline

Most MCP clients accept the same shape:

```json
{
  "mcpServers": {
    "codeofpaper": {
      "command": "codeofpaper-mcp",
      "env": {
        "CODEOFPAPER_API_URL": "https://api.codeofpaper.com"
      }
    }
  }
}
```

### Tools exposed

| Tool | Purpose |
|------|---------|
| `paper_lookup(paper_id_or_url)` | Paper metadata + confident-tier repos |
| `code_for_paper(paper_id_or_url, limit, include_possible)` | Ranked GitHub repos implementing a paper |
| `search_papers(query, limit, year, venue, has_code)` | Free-text paper search with filters |

All tools are read-only, return plain JSON, and surface API errors as `{"error": "...", "status": N}` rather than throwing — agents get structured output either way.

## Common Workflows

### Core Discovery

```bash
# Find papers with code about a topic
codeofpaper search "reinforcement learning" --sort has_code --has-code

# Get the best repo for a specific paper
codeofpaper code 1706.03762

# Accepts arXiv URLs — no need to extract the ID
codeofpaper paper https://arxiv.org/abs/2010.11929

# Reverse lookup: what paper does this repo implement?
codeofpaper repo google-research/vision_transformer

# Open a paper in the browser, or jump straight to its code
codeofpaper open 2010.11929
codeofpaper open 2010.11929 --code
```

### Browsing & Monitoring

```bash
# What's trending in computer vision?
codeofpaper trending --category cs.CV --sort hot

# Conference papers that just got new code
codeofpaper code-drops --days 7

# NeurIPS 2024 oral papers with code
codeofpaper conference neurips_2024 --track oral --has-code

# Daily monitoring: what's new in my field?
codeofpaper trending --category cs.CV --days 1 -o json >> ~/research/daily_cv.jsonl
```

### Composable Pipelines

```bash
# Find implementations of a paper's related work
codeofpaper similar 2010.11929 -o quiet | codeofpaper batch code

# Batch process a reading list
cat reading_list.txt | codeofpaper batch paper > enriched.jsonl

# Cross-reference with GitHub CLI
codeofpaper code 1706.03762 -o quiet | head -1 | xargs gh repo view

# Export conference papers as BibTeX
codeofpaper export conference neurips_2024 --has-code -o bibtex > neurips2024_code.bib

# Bulk export a category for meta-analysis
codeofpaper export trending --category cs.CV --has-code --days 365 -o csv > cv_with_code.csv
```

### Multi-Step Scripts

```bash
# Find a paper → get top repo → clone it
REPO=$(codeofpaper search "attention is all you need" -o quiet | head -1 | \
  xargs codeofpaper code -o json | jq -r '.top_repos[0].full_name')
gh repo clone "$REPO"

# Discover a random paper and explore its neighborhood
ID=$(codeofpaper random --quality high -o quiet)
codeofpaper paper "$ID"
codeofpaper similar "$ID"
codeofpaper code "$ID"

# Quick paper lookup in a script
ARXIV_ID="2010.11929"
TITLE=$(codeofpaper -o json paper "$ARXIV_ID" | jq -r '.title')
echo "Paper: $TITLE"
```

## Configuration

Config is stored as JSON via [platformdirs](https://pypi.org/project/platformdirs/):

| OS | Path |
|----|------|
| Linux | `~/.config/codeofpaper/config.json` |
| macOS | `~/Library/Application Support/codeofpaper/config.json` |
| Windows | `%APPDATA%\codeofpaper\config.json` |

Fields:

```json
{
  "api_url": "https://api.codeofpaper.com",
  "api_key": null,
  "default_format": "table",
  "ca_bundle": null
}
```

No config file needed — everything works out of the box with sensible defaults.

### Priority Chain

Options are resolved in this order (first wins):

1. CLI flag (`--api-url`, `--api-key`, `--ca-bundle`, `-o`)
2. Environment variable (`CODEOFPAPER_API_URL`, `CODEOFPAPER_API_KEY`, `CODEOFPAPER_CA_BUNDLE`, `CODEOFPAPER_OUTPUT`, `CODEOFPAPER_TIMEOUT`)
3. Config file
4. Built-in defaults

### Corporate Proxies / Custom TLS Certificates

If you're behind a corporate proxy that performs TLS inspection (man-in-the-middle), you'll see an SSL error like:

```
Cannot reach API: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain
```

To fix this, point the CLI at your corporate CA certificate bundle (PEM file). Three equivalent ways, in priority order:

```bash
# 1. CLI flag (per-invocation)
codeofpaper --ca-bundle /path/to/corporate-ca.pem search "transformers"

# 2. Environment variable (per-session or in .bashrc/.zshrc)
export CODEOFPAPER_CA_BUNDLE=/path/to/corporate-ca.pem

# 3. Config file (permanent — set once, forget)
# Add to ~/.config/codeofpaper/config.json:
#   {"ca_bundle": "/path/to/corporate-ca.pem"}
```

Ask your IT department for the CA certificate file if you don't have it.

> **Tip:** If you've already set `SSL_CERT_FILE` for other tools (pip, curl, etc.), httpx respects that variable automatically — no extra configuration needed.

## Alias: `cop`

Both `codeofpaper` and `cop` are installed as entry points:

```bash
cop search "transformers"
cop -o json trending | jq '.'
```

> **Note:** If `cop` conflicts with another tool on your system, use `codeofpaper` instead.

## Shell Completion

Install tab completion for your shell:

```bash
codeofpaper --install-completion
```

Supports bash, zsh, fish, and PowerShell. After installing, restart your shell or source the completion file.

## Help

```bash
codeofpaper --help          # List all commands
codeofpaper search --help   # Help for a specific command
codeofpaper -v              # Print version
```

## Links

- **Website:** https://codeofpaper.com
- **API docs:** https://api.codeofpaper.com/docs
- **Agent discovery:** https://codeofpaper.com/llms.txt

## License

MIT
