"""Tests for the export command.

Tests pagination, all 3 sources (trending/conference/search),
output formats, --max limit, error handling, and edge cases.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest
from typer.testing import CliRunner

from codeofpaper_cli.client import APIError, ConnectionError_
from codeofpaper_cli.exit_codes import CONNECTION_ERROR, RATE_LIMITED
from codeofpaper_cli.main import app
from codeofpaper_cli.state import OutputFormat, state

runner = CliRunner()


def _parse_json_output(output: str) -> dict:
    """Parse JSON from runner output, stripping any stderr lines mixed in."""
    # CliRunner mixes stdout+stderr; find the JSON object
    start = output.index("{")
    depth = 0
    for i, ch in enumerate(output[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(output[start : i + 1])
    return json.loads(output)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_state():
    state.output = OutputFormat.table
    state.api_url = "https://api.codeofpaper.com"
    state.api_key = None
    yield


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

def _make_papers(n: int, start: int = 0) -> list[dict]:
    """Generate n fake papers for testing."""
    return [
        {
            "arxiv_id": f"2024.{10000 + start + i}",
            "title": f"Paper number {start + i}",
            "authors": [f"Author {start + i}"],
            "published_date": "2024-01-15",
            "categories": ["cs.AI"],
            "has_repos": i % 2 == 0,
            "repo_count": i * 2 if i % 2 == 0 else 0,
            "max_stars": i * 100 if i % 2 == 0 else 0,
        }
        for i in range(n)
    ]


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
# Trending export
# ---------------------------------------------------------------------------


class TestExportTrending:
    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_csv_output(self, MockClient, mock_sleep):
        papers = _make_papers(3)
        MockClient.return_value = _mock_client(
            get_trending={"trending": papers, "count": 3, "total": 3}
        ).return_value
        result = runner.invoke(app, ["-o", "csv", "export", "trending"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        # Header + 3 data rows (+ "Exported" on stderr, not in output)
        assert lines[0].startswith("arxiv_id,")
        assert len([l for l in lines if l.startswith("2024.")]) == 3

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_jsonl_output(self, MockClient, mock_sleep):
        papers = _make_papers(2)
        MockClient.return_value = _mock_client(
            get_trending={"trending": papers, "count": 2, "total": 2}
        ).return_value
        result = runner.invoke(app, ["-o", "jsonl", "export", "trending"])
        assert result.exit_code == 0
        lines = [l for l in result.output.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 2
        parsed = json.loads(lines[0])
        assert "arxiv_id" in parsed

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_json_output(self, MockClient, mock_sleep):
        papers = _make_papers(2)
        MockClient.return_value = _mock_client(
            get_trending={"trending": papers, "count": 2, "total": 2}
        ).return_value
        result = runner.invoke(app, ["-o", "json", "export", "trending"])
        assert result.exit_code == 0
        data = _parse_json_output(result.output)
        assert data["count"] == 2
        assert len(data["papers"]) == 2

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_bibtex_output(self, MockClient, mock_sleep):
        papers = _make_papers(2)
        MockClient.return_value = _mock_client(
            get_trending={"trending": papers, "count": 2, "total": 2}
        ).return_value
        result = runner.invoke(app, ["-o", "bibtex", "export", "trending"])
        assert result.exit_code == 0
        assert "@article{" in result.output
        assert result.output.count("@article{") == 2

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_quiet_output(self, MockClient, mock_sleep):
        papers = _make_papers(3)
        MockClient.return_value = _mock_client(
            get_trending={"trending": papers, "count": 3, "total": 3}
        ).return_value
        result = runner.invoke(app, ["-q", "export", "trending"])
        assert result.exit_code == 0
        ids = [l for l in result.output.strip().split("\n") if l.startswith("2024.")]
        assert len(ids) == 3

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_with_category_and_has_code(self, MockClient, mock_sleep):
        papers = _make_papers(1)
        mc = _mock_client(
            get_trending={"trending": papers, "count": 1, "total": 1}
        )
        MockClient.return_value = mc.return_value
        result = runner.invoke(
            app, ["-o", "csv", "export", "trending", "--has-code", "--category", "cs.CV", "--days", "7"]
        )
        assert result.exit_code == 0
        # Verify the client was called with right params
        inst = mc.return_value.__enter__.return_value
        inst.get_trending.assert_called_once()
        kwargs = inst.get_trending.call_args
        assert kwargs[1]["has_code"] is True or kwargs.kwargs.get("has_code") is True


# ---------------------------------------------------------------------------
# Conference export
# ---------------------------------------------------------------------------


class TestExportConference:
    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_csv_output(self, MockClient, mock_sleep):
        papers = _make_papers(5)
        MockClient.return_value = _mock_client(
            get_conference_papers={"papers": papers, "count": 5, "total": 5}
        ).return_value
        result = runner.invoke(app, ["-o", "csv", "export", "conference", "neurips_2024"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0].startswith("arxiv_id,")
        assert len([l for l in lines if l.startswith("2024.")]) == 5

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_missing_conference_id(self, MockClient, mock_sleep):
        MockClient.return_value = _mock_client().return_value
        result = runner.invoke(app, ["-o", "csv", "export", "conference"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Search export
# ---------------------------------------------------------------------------


class TestExportSearch:
    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_jsonl_output(self, MockClient, mock_sleep):
        papers = _make_papers(4)
        MockClient.return_value = _mock_client(
            search_papers={"papers": papers, "count": 4}
        ).return_value
        result = runner.invoke(app, ["-o", "jsonl", "export", "search", "transformers"])
        assert result.exit_code == 0
        lines = [l for l in result.output.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 4

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_missing_query(self, MockClient, mock_sleep):
        MockClient.return_value = _mock_client().return_value
        result = runner.invoke(app, ["-o", "csv", "export", "search"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestExportPagination:
    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_auto_paginates(self, MockClient, mock_sleep):
        """Two pages of results (100 + 50) should be combined."""
        page1 = _make_papers(100, start=0)
        page2 = _make_papers(50, start=100)
        mc = _mock_client()
        inst = mc.return_value.__enter__.return_value
        inst.get_trending.side_effect = [
            {"trending": page1, "count": 100, "total": 150},
            {"trending": page2, "count": 50, "total": 150},
        ]
        MockClient.return_value = mc.return_value
        result = runner.invoke(app, ["-o", "json", "export", "trending", "--max", "200"])
        assert result.exit_code == 0
        data = _parse_json_output(result.output)
        assert data["count"] == 150
        assert len(data["papers"]) == 150
        assert inst.get_trending.call_count == 2
        # Should have slept between pages
        mock_sleep.assert_called_once_with(0.5)

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_max_limits_results(self, MockClient, mock_sleep):
        """--max 5 should stop after 5 papers even if more available."""
        page = _make_papers(100)
        MockClient.return_value = _mock_client(
            get_trending={"trending": page, "count": 100, "total": 1000}
        ).return_value
        result = runner.invoke(app, ["-o", "json", "export", "trending", "--max", "5"])
        assert result.exit_code == 0
        data = _parse_json_output(result.output)
        assert data["count"] == 5
        assert len(data["papers"]) == 5

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_stops_on_empty_page(self, MockClient, mock_sleep):
        """Stops pagination when API returns empty results."""
        mc = _mock_client()
        inst = mc.return_value.__enter__.return_value
        inst.get_trending.side_effect = [
            {"trending": _make_papers(3), "count": 3, "total": 3},
        ]
        MockClient.return_value = mc.return_value
        result = runner.invoke(app, ["-o", "json", "export", "trending", "--max", "200"])
        assert result.exit_code == 0
        data = _parse_json_output(result.output)
        assert data["count"] == 3
        # Only 1 call because len(3) < limit(100) signals end
        assert inst.get_trending.call_count == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestExportErrors:
    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_api_error(self, MockClient, mock_sleep):
        MockClient.return_value = _mock_client(
            get_trending=APIError(status_code=429, detail="Rate limited", exit_code=RATE_LIMITED)
        ).return_value
        result = runner.invoke(app, ["-o", "json", "export", "trending"])
        assert result.exit_code == RATE_LIMITED

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_connection_error(self, MockClient, mock_sleep):
        MockClient.return_value = _mock_client(
            get_trending=ConnectionError_(detail="Timeout")
        ).return_value
        result = runner.invoke(app, ["-o", "json", "export", "trending"])
        assert result.exit_code == CONNECTION_ERROR

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_unknown_source(self, MockClient, mock_sleep):
        MockClient.return_value = _mock_client().return_value
        result = runner.invoke(app, ["-o", "csv", "export", "badSource"])
        assert result.exit_code != 0

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_empty_results(self, MockClient, mock_sleep):
        MockClient.return_value = _mock_client(
            get_trending={"trending": [], "count": 0, "total": 0}
        ).return_value
        result = runner.invoke(app, ["-o", "json", "export", "trending"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# CSV flattening
# ---------------------------------------------------------------------------


class TestExportFlatten:
    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_categories_flattened(self, MockClient, mock_sleep):
        """Categories list should be semicolon-joined in CSV."""
        papers = [
            {
                "arxiv_id": "2024.99999",
                "title": "Test Paper",
                "published_date": "2024-01-01",
                "categories": ["cs.AI", "cs.LG", "cs.CL"],
                "has_repos": True,
                "repo_count": 5,
                "max_stars": 100,
            }
        ]
        MockClient.return_value = _mock_client(
            get_trending={"trending": papers, "count": 1, "total": 1}
        ).return_value
        result = runner.invoke(app, ["-o", "csv", "export", "trending"])
        assert result.exit_code == 0
        assert "cs.AI;cs.LG;cs.CL" in result.output

    @patch("codeofpaper_cli.commands.export.time.sleep")
    @patch("codeofpaper_cli.commands.export.Client")
    def test_url_generated_when_missing(self, MockClient, mock_sleep):
        """Papers without url field get arxiv URL generated."""
        papers = [
            {
                "arxiv_id": "2024.12345",
                "title": "No URL Paper",
                "published_date": "2024-01-01",
                "categories": ["cs.AI"],
                "has_repos": False,
                "repo_count": 0,
                "max_stars": 0,
            }
        ]
        MockClient.return_value = _mock_client(
            get_trending={"trending": papers, "count": 1, "total": 1}
        ).return_value
        result = runner.invoke(app, ["-o", "csv", "export", "trending"])
        assert result.exit_code == 0
        assert "https://arxiv.org/abs/2024.12345" in result.output
