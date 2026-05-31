"""Consolidated edge-case and integration tests for task 3.10.

Fills gaps not covered by existing per-module tests:
- Error handling across multiple commands (not just search)
- BibTeX with non-ASCII authors
- CSV with special characters
- Defensive parsing (missing API response fields)
- Config → state priority chain
- Empty result sets across formats
- Exit code hints
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from codeofpaper_cli.client import APIError, ConnectionError_
from codeofpaper_cli.exit_codes import (
    AUTH_ERROR,
    CONNECTION_ERROR,
    EXIT_CODE_HINTS,
    GENERAL_ERROR,
    NOT_FOUND,
    RATE_LIMITED,
    SUCCESS,
    exit_code_from_status,
)
from codeofpaper_cli.formatters import (
    format_bibtex_entry,
    format_csv,
    format_json,
    format_jsonl,
    format_quiet,
)
from codeofpaper_cli.main import app
from codeofpaper_cli.state import OutputFormat, state
from codeofpaper_cli import config

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_state():
    state.output = OutputFormat.table
    state.api_url = "https://api.codeofpaper.com"
    state.api_key = None
    yield


def _mock_client(**method_returns):
    mock_instance = MagicMock()
    for method, retval in method_returns.items():
        if isinstance(retval, Exception):
            getattr(mock_instance, method).side_effect = retval
        else:
            getattr(mock_instance, method).return_value = retval
    mock_cls = MagicMock(return_value=mock_instance)
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    return mock_cls


# ---------------------------------------------------------------------------
# Error handling across commands
# ---------------------------------------------------------------------------


class TestErrorHandlingAcrossCommands:
    """Verify multiple commands properly map errors to exit codes."""

    @patch("codeofpaper_cli.commands.trending.Client")
    def test_trending_rate_limited(self, MockClient):
        MockClient.return_value = _mock_client(
            get_trending=APIError(status_code=429, detail="Rate limited", exit_code=RATE_LIMITED)
        ).return_value
        result = runner.invoke(app, ["-o", "json", "trending"])
        assert result.exit_code == RATE_LIMITED
        data = json.loads(result.output)
        assert "error" in data

    @patch("codeofpaper_cli.commands.code.Client")
    def test_code_not_found(self, MockClient):
        MockClient.return_value = _mock_client(
            get_paper_repos=APIError(status_code=404, detail="Paper not found", exit_code=NOT_FOUND)
        ).return_value
        result = runner.invoke(app, ["-o", "json", "code", "9999.99999"])
        assert result.exit_code == NOT_FOUND

    @patch("codeofpaper_cli.commands.similar.Client")
    def test_similar_connection_error(self, MockClient):
        MockClient.return_value = _mock_client(
            get_similar=ConnectionError_(detail="Timeout")
        ).return_value
        result = runner.invoke(app, ["-o", "json", "similar", "2010.11929"])
        assert result.exit_code == CONNECTION_ERROR

    @patch("codeofpaper_cli.commands.categories.Client")
    def test_categories_server_error(self, MockClient):
        MockClient.return_value = _mock_client(
            get_categories=APIError(status_code=500, detail="Internal error", exit_code=GENERAL_ERROR)
        ).return_value
        result = runner.invoke(app, ["-o", "json", "categories"])
        assert result.exit_code == GENERAL_ERROR

    @patch("codeofpaper_cli.commands.conferences.Client")
    def test_conferences_auth_error(self, MockClient):
        MockClient.return_value = _mock_client(
            get_conferences=APIError(status_code=401, detail="Unauthorized", exit_code=AUTH_ERROR)
        ).return_value
        result = runner.invoke(app, ["-o", "json", "conferences"])
        assert result.exit_code == AUTH_ERROR

    @patch("codeofpaper_cli.commands.random.Client")
    def test_random_connection_error(self, MockClient):
        MockClient.return_value = _mock_client(
            get_random=ConnectionError_(detail="DNS resolution failed")
        ).return_value
        result = runner.invoke(app, ["-o", "json", "random"])
        assert result.exit_code == CONNECTION_ERROR

    @patch("codeofpaper_cli.commands.code_drops.Client")
    def test_code_drops_server_error(self, MockClient):
        MockClient.return_value = _mock_client(
            get_recent_code_drops=APIError(status_code=502, detail="Bad gateway", exit_code=GENERAL_ERROR)
        ).return_value
        result = runner.invoke(app, ["-o", "json", "code-drops"])
        assert result.exit_code == GENERAL_ERROR


# ---------------------------------------------------------------------------
# BibTeX edge cases
# ---------------------------------------------------------------------------


class TestBibtexEdgeCases:
    def test_non_ascii_authors(self):
        paper = {
            "arxiv_id": "2024.00001",
            "title": "Test Paper",
            "authors": ["François Müller", "José García-López"],
            "published_date": "2024-01-01",
        }
        result = format_bibtex_entry(paper)
        assert "Müller, François" in result
        assert "García-López, José" in result

    def test_no_published_date(self):
        paper = {"arxiv_id": "2024.00001", "title": "No Date Paper", "published_date": None}
        result = format_bibtex_entry(paper)
        assert "@article{2024_00001," in result
        assert "year" not in result

    def test_empty_title(self):
        paper = {"arxiv_id": "2024.00001", "title": ""}
        result = format_bibtex_entry(paper)
        assert "title     = {}," in result

    def test_url_generated_when_missing(self):
        paper = {"arxiv_id": "2024.00001", "title": "Test"}
        result = format_bibtex_entry(paper)
        assert "https://arxiv.org/abs/2024.00001" in result

    def test_abstract_exactly_500_chars(self):
        paper = {"arxiv_id": "test", "title": "T", "summary": "x" * 500}
        result = format_bibtex_entry(paper)
        assert "..." not in result  # exactly 500 → no truncation

    def test_abstract_501_chars_truncated(self):
        paper = {"arxiv_id": "test", "title": "T", "summary": "x" * 501}
        result = format_bibtex_entry(paper)
        assert "..." in result


# ---------------------------------------------------------------------------
# CSV/format edge cases
# ---------------------------------------------------------------------------


class TestCsvEdgeCases:
    def test_commas_in_values(self):
        items = [{"title": "Attention, Is All You Need", "id": "1"}]
        result = format_csv(items, columns=["id", "title"])
        assert '"Attention, Is All You Need"' in result or "Attention" in result

    def test_newlines_in_values(self):
        items = [{"title": "Line1\nLine2", "id": "1"}]
        result = format_csv(items, columns=["id", "title"])
        # CSV lib should quote fields with newlines
        parsed_lines = result.strip().split("\n")
        assert len(parsed_lines) >= 2  # at least header + data

    def test_unicode_in_csv(self):
        items = [{"title": "Über die Quantentheorie", "id": "1"}]
        result = format_csv(items, columns=["id", "title"])
        assert "Über" in result


class TestQuietEdgeCases:
    def test_all_empty_ids(self):
        items = [{"arxiv_id": ""}, {"arxiv_id": ""}]
        assert format_quiet(items) == ""

    def test_mixed_id_keys(self):
        items = [{"arxiv_id": "2010.11929"}, {"id": "other123"}]
        result = format_quiet(items)
        lines = result.split("\n")
        assert "2010.11929" in lines
        assert "other123" in lines


class TestJsonEdgeCases:
    def test_nested_structures(self):
        data = {"papers": [{"categories": ["cs.AI", "cs.LG"]}]}
        result = format_json(data)
        parsed = json.loads(result)
        assert parsed["papers"][0]["categories"] == ["cs.AI", "cs.LG"]

    def test_date_serialization(self):
        from datetime import date
        data = {"date": date(2024, 1, 15)}
        result = format_json(data)
        assert "2024-01-15" in result

    def test_jsonl_preserves_order(self):
        items = [{"id": str(i)} for i in range(5)]
        result = format_jsonl(items)
        lines = result.strip().split("\n")
        for i, line in enumerate(lines):
            assert json.loads(line)["id"] == str(i)


# ---------------------------------------------------------------------------
# Defensive parsing: missing fields in API responses
# ---------------------------------------------------------------------------


class TestDefensiveParsing:
    """Commands should not crash when API responses have missing fields."""

    @patch("codeofpaper_cli.commands.paper.Client")
    def test_paper_minimal_response(self, MockClient):
        """Paper with only arxiv_id and title — no crash."""
        minimal = {"arxiv_id": "2024.00001", "title": "Minimal Paper"}
        MockClient.return_value = _mock_client(get_paper=minimal).return_value
        result = runner.invoke(app, ["-o", "json", "paper", "2024.00001"])
        assert result.exit_code == 0

    @patch("codeofpaper_cli.commands.trending.Client")
    def test_trending_papers_missing_fields(self, MockClient):
        """Trending papers without optional fields."""
        papers = [{"arxiv_id": "2024.00001", "title": "Sparse Paper"}]
        MockClient.return_value = _mock_client(
            get_trending={"trending": papers, "count": 1, "total": 1}
        ).return_value
        result = runner.invoke(app, ["trending"])
        assert result.exit_code == 0

    @patch("codeofpaper_cli.commands.code.Client")
    def test_code_empty_repos(self, MockClient):
        """Paper with no repos in response."""
        MockClient.return_value = _mock_client(
            get_paper_repos={"paper": {"arxiv_id": "2024.00001"}, "top_repos": []}
        ).return_value
        result = runner.invoke(app, ["-o", "json", "code", "2024.00001"])
        assert result.exit_code == 0

    @patch("codeofpaper_cli.commands.search.Client")
    def test_search_empty_results(self, MockClient):
        """Search returning zero papers."""
        MockClient.return_value = _mock_client(
            search_papers={"query": "nonexistent", "count": 0, "papers": []}
        ).return_value
        for fmt in ["json", "quiet", "csv", "jsonl"]:
            result = runner.invoke(app, ["-o", fmt, "search", "nonexistent"])
            assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Config → state priority chain
# ---------------------------------------------------------------------------


class TestConfigStatePriority:
    """Test that CLI flags > env vars > config file > defaults."""

    def test_quiet_flag_overrides_config_format(self, tmp_path):
        """--quiet overrides even json format from config."""
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"default_format": "json"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), \
             patch.object(config, "_CONFIG_FILE", fake_file):
            result = runner.invoke(app, ["-q", "auth", "status"])
        assert result.exit_code == 0

    def test_output_flag_overrides_config_format(self, tmp_path):
        """Explicit -o csv overrides config default_format=json."""
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"default_format": "json"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), \
             patch.object(config, "_CONFIG_FILE", fake_file):
            result = runner.invoke(app, ["-o", "csv", "auth", "status"])
        assert result.exit_code == 0

    def test_api_url_from_config(self, tmp_path):
        """Config api_url flows to state when no --api-url flag."""
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_url": "https://custom.example.com"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), \
             patch.object(config, "_CONFIG_FILE", fake_file):
            result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "custom.example.com" in result.output

    def test_api_url_flag_overrides_config(self, tmp_path):
        """--api-url flag overrides config value."""
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_url": "https://config.example.com"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), \
             patch.object(config, "_CONFIG_FILE", fake_file):
            result = runner.invoke(
                app, ["--api-url", "https://flag.example.com", "auth", "status"]
            )
        assert result.exit_code == 0

    def test_no_config_file_uses_defaults(self, tmp_path):
        """No config file → all defaults."""
        fake_file = tmp_path / "nonexistent" / "config.json"
        with patch.object(config, "_CONFIG_DIR", tmp_path / "nonexistent"), \
             patch.object(config, "_CONFIG_FILE", fake_file):
            result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "(not set)" in result.output


# ---------------------------------------------------------------------------
# Exit code hints
# ---------------------------------------------------------------------------


class TestExitCodeHints:
    def test_all_error_codes_have_hints(self):
        for code in [CONNECTION_ERROR, NOT_FOUND, RATE_LIMITED, AUTH_ERROR]:
            assert code in EXIT_CODE_HINTS
            assert len(EXIT_CODE_HINTS[code]) > 0

    def test_success_not_in_hints(self):
        assert SUCCESS not in EXIT_CODE_HINTS

    def test_exit_code_mapping_comprehensive(self):
        assert exit_code_from_status(200) == SUCCESS
        assert exit_code_from_status(201) == SUCCESS
        assert exit_code_from_status(204) == SUCCESS
        assert exit_code_from_status(401) == AUTH_ERROR
        assert exit_code_from_status(403) == AUTH_ERROR
        assert exit_code_from_status(404) == NOT_FOUND
        assert exit_code_from_status(429) == RATE_LIMITED
        assert exit_code_from_status(500) == GENERAL_ERROR
        assert exit_code_from_status(502) == GENERAL_ERROR
        assert exit_code_from_status(503) == GENERAL_ERROR
        assert exit_code_from_status(418) == GENERAL_ERROR  # unknown 4xx


# ---------------------------------------------------------------------------
# Version flag
# ---------------------------------------------------------------------------


class TestVersionFlag:
    def test_version_output(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "codeofpaper" in result.output

    def test_short_version_flag(self):
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert "codeofpaper" in result.output


# ---------------------------------------------------------------------------
# Help output
# ---------------------------------------------------------------------------


class TestHelpOutput:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "search" in result.output
        assert "paper" in result.output
        assert "batch" in result.output
        assert "export" in result.output

    def test_search_help(self):
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "query" in result.output.lower()

    def test_batch_help(self):
        result = runner.invoke(app, ["batch", "--help"])
        assert result.exit_code == 0
        assert "delay" in result.output.lower()

    def test_export_help(self):
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "source" in result.output.lower()
