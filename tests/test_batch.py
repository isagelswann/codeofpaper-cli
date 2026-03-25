"""Tests for the batch command.

Tests all 5 supported commands, file/stdin input, delay,
error handling (per-line and global), and JSONL output format.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from codeofpaper_cli.client import APIError, ConnectionError_
from codeofpaper_cli.exit_codes import NOT_FOUND, RATE_LIMITED
from codeofpaper_cli.main import app
from codeofpaper_cli.state import OutputFormat, state

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        elif isinstance(retval, list) and all(
            not isinstance(v, dict) or "side_effect" not in v for v in retval
        ):
            # Plain list of return values → side_effect for sequential calls
            if retval and isinstance(retval[0], (dict, list)):
                getattr(mock_instance, method).side_effect = retval
            else:
                getattr(mock_instance, method).return_value = retval
        else:
            getattr(mock_instance, method).return_value = retval
    mock_cls = MagicMock(return_value=mock_instance)
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    return mock_cls


def _jsonl_records(output: str) -> list[dict]:
    """Parse JSONL records from runner output, skipping non-JSON lines."""
    records = []
    for line in output.strip().split("\n"):
        line = line.strip()
        if line.startswith("{"):
            records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Paper batch
# ---------------------------------------------------------------------------


class TestBatchPaper:
    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_two_papers_from_file(self, MockClient, mock_sleep, tmp_path):
        paper1 = {"arxiv_id": "2010.11929", "title": "ViT"}
        paper2 = {"arxiv_id": "1706.03762", "title": "Attention"}
        mc = _mock_client()
        inst = mc.return_value.__enter__.return_value
        inst.get_paper.side_effect = [paper1, paper2]
        MockClient.return_value = mc.return_value

        f = tmp_path / "ids.txt"
        f.write_text("2010.11929\n1706.03762\n")

        result = runner.invoke(app, ["batch", "paper", str(f)])
        assert result.exit_code == 0
        records = _jsonl_records(result.output)
        assert len(records) == 2
        assert records[0]["status"] == "ok"
        assert records[0]["input"] == "2010.11929"
        assert records[0]["data"]["title"] == "ViT"
        assert records[1]["data"]["title"] == "Attention"
        mock_sleep.assert_called_once_with(0.5)

    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_stdin_input(self, MockClient, mock_sleep):
        paper = {"arxiv_id": "2010.11929", "title": "ViT"}
        mc = _mock_client(get_paper=paper)
        MockClient.return_value = mc.return_value

        result = runner.invoke(app, ["batch", "paper"], input="2010.11929\n")
        assert result.exit_code == 0
        records = _jsonl_records(result.output)
        assert len(records) == 1
        assert records[0]["status"] == "ok"


# ---------------------------------------------------------------------------
# Search batch
# ---------------------------------------------------------------------------


class TestBatchSearch:
    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_search_queries(self, MockClient, mock_sleep, tmp_path):
        resp1 = {"count": 1, "papers": [{"arxiv_id": "2010.11929", "title": "ViT"}]}
        resp2 = {"count": 1, "papers": [{"arxiv_id": "1706.03762", "title": "Attention"}]}
        mc = _mock_client()
        inst = mc.return_value.__enter__.return_value
        inst.search_papers.side_effect = [resp1, resp2]
        MockClient.return_value = mc.return_value

        f = tmp_path / "queries.txt"
        f.write_text("vision transformer\nattention mechanism\n")

        result = runner.invoke(app, ["batch", "search", str(f)])
        assert result.exit_code == 0
        records = _jsonl_records(result.output)
        assert len(records) == 2
        assert records[0]["data"]["count"] == 1
        assert records[1]["data"]["count"] == 1


# ---------------------------------------------------------------------------
# Code batch
# ---------------------------------------------------------------------------


class TestBatchCode:
    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_code_lookup(self, MockClient, mock_sleep):
        repos = {"top_repos": [{"full_name": "org/repo", "stars": 100}]}
        mc = _mock_client(get_paper_repos=repos)
        MockClient.return_value = mc.return_value

        result = runner.invoke(app, ["batch", "code"], input="2010.11929\n")
        assert result.exit_code == 0
        records = _jsonl_records(result.output)
        assert records[0]["data"]["top_repos"][0]["full_name"] == "org/repo"


# ---------------------------------------------------------------------------
# Similar batch
# ---------------------------------------------------------------------------


class TestBatchSimilar:
    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_similar_lookup(self, MockClient, mock_sleep):
        similar = {"papers": [{"arxiv_id": "2103.14030", "similarity": 0.9}]}
        mc = _mock_client(get_similar=similar)
        MockClient.return_value = mc.return_value

        result = runner.invoke(app, ["batch", "similar"], input="2010.11929\n")
        assert result.exit_code == 0
        records = _jsonl_records(result.output)
        assert records[0]["status"] == "ok"


# ---------------------------------------------------------------------------
# Suggest batch
# ---------------------------------------------------------------------------


class TestBatchSuggest:
    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_suggest_queries(self, MockClient, mock_sleep):
        suggs = [{"arxiv_id": "2010.11929", "title": "ViT"}]
        mc = _mock_client()
        inst = mc.return_value.__enter__.return_value
        inst.suggest.return_value = suggs
        MockClient.return_value = mc.return_value

        result = runner.invoke(app, ["batch", "suggest"], input="vision\n")
        assert result.exit_code == 0
        records = _jsonl_records(result.output)
        assert records[0]["data"]["suggestions"][0]["title"] == "ViT"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestBatchErrors:
    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_per_line_errors(self, MockClient, mock_sleep, tmp_path):
        """One success + one 404 = both appear in JSONL output."""
        paper = {"arxiv_id": "2010.11929", "title": "ViT"}
        mc = _mock_client()
        inst = mc.return_value.__enter__.return_value
        inst.get_paper.side_effect = [
            paper,
            APIError(status_code=404, detail="Not found", exit_code=NOT_FOUND),
        ]
        MockClient.return_value = mc.return_value

        f = tmp_path / "ids.txt"
        f.write_text("2010.11929\n9999.99999\n")

        result = runner.invoke(app, ["batch", "paper", str(f)])
        assert result.exit_code == 0  # batch always exits 0
        records = _jsonl_records(result.output)
        assert len(records) == 2
        assert records[0]["status"] == "ok"
        assert records[1]["status"] == "error"
        assert "Not found" in records[1]["error"]

    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_connection_error_per_line(self, MockClient, mock_sleep):
        mc = _mock_client(
            get_paper=ConnectionError_(detail="Timeout")
        )
        MockClient.return_value = mc.return_value

        result = runner.invoke(app, ["batch", "paper"], input="2010.11929\n")
        assert result.exit_code == 0
        records = _jsonl_records(result.output)
        assert records[0]["status"] == "error"
        assert "Timeout" in records[0]["error"]

    def test_unknown_command(self):
        result = runner.invoke(app, ["batch", "badcmd"], input="test\n")
        assert result.exit_code == 1

    def test_missing_file(self):
        result = runner.invoke(app, ["batch", "paper", "/nonexistent/file.txt"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Delay and empty input
# ---------------------------------------------------------------------------


class TestBatchDelay:
    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_custom_delay(self, MockClient, mock_sleep, tmp_path):
        mc = _mock_client()
        inst = mc.return_value.__enter__.return_value
        inst.get_paper.side_effect = [
            {"arxiv_id": "1"}, {"arxiv_id": "2"}, {"arxiv_id": "3"}
        ]
        MockClient.return_value = mc.return_value

        f = tmp_path / "ids.txt"
        f.write_text("1\n2\n3\n")

        result = runner.invoke(app, ["batch", "paper", str(f), "--delay", "1.5"])
        assert result.exit_code == 0
        assert mock_sleep.call_count == 2  # between 3 calls
        mock_sleep.assert_called_with(1.5)

    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_no_delay_between_single(self, MockClient, mock_sleep):
        mc = _mock_client(get_paper={"arxiv_id": "2010.11929"})
        MockClient.return_value = mc.return_value

        result = runner.invoke(app, ["batch", "paper"], input="2010.11929\n")
        assert result.exit_code == 0
        mock_sleep.assert_not_called()  # Only 1 item, no delay needed


class TestBatchEmpty:
    def test_empty_input(self):
        result = runner.invoke(app, ["batch", "paper"], input="")
        assert result.exit_code == 0

    def test_blank_lines_skipped(self, tmp_path):
        f = tmp_path / "ids.txt"
        f.write_text("\n  \n\n")
        result = runner.invoke(app, ["batch", "paper", str(f)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# JSONL format validation
# ---------------------------------------------------------------------------


class TestBatchJsonlFormat:
    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_each_line_is_valid_json(self, MockClient, mock_sleep, tmp_path):
        mc = _mock_client()
        inst = mc.return_value.__enter__.return_value
        inst.get_paper.side_effect = [
            {"arxiv_id": "2010.11929", "title": "ViT"},
            APIError(status_code=404, detail="Not found", exit_code=NOT_FOUND),
            {"arxiv_id": "1706.03762", "title": "Attention"},
        ]
        MockClient.return_value = mc.return_value

        f = tmp_path / "ids.txt"
        f.write_text("2010.11929\n9999.99999\n1706.03762\n")

        result = runner.invoke(app, ["batch", "paper", str(f)])
        records = _jsonl_records(result.output)
        assert len(records) == 3
        for r in records:
            assert "input" in r
            assert "status" in r
            assert r["status"] in ("ok", "error")

    @patch("codeofpaper_cli.commands.batch.time.sleep")
    @patch("codeofpaper_cli.commands.batch.Client")
    def test_arxiv_url_normalized(self, MockClient, mock_sleep):
        """ArXiv URLs in input should be normalized to IDs."""
        paper = {"arxiv_id": "2010.11929", "title": "ViT"}
        mc = _mock_client(get_paper=paper)
        MockClient.return_value = mc.return_value

        result = runner.invoke(
            app, ["batch", "paper"],
            input="https://arxiv.org/abs/2010.11929\n",
        )
        assert result.exit_code == 0
        records = _jsonl_records(result.output)
        assert records[0]["status"] == "ok"
        # Verify the URL was passed to extract_arxiv_id → get_paper
        inst = mc.return_value.__enter__.return_value
        inst.get_paper.assert_called_once_with("2010.11929")
