"""Tests for the MCP tool wrappers (codeofpaper_cli.mcp.tools).

The MCP layer is a thin adapter over `codeofpaper_cli.client.Client`,
so these tests mock the Client's convenience methods and assert the
tools return the documented shape (and swallow API errors into a
`{"error": ...}` dict rather than raising).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from codeofpaper_cli.client import APIError, ConnectionError_
from codeofpaper_cli.exit_codes import GENERAL_ERROR, NOT_FOUND, RATE_LIMITED
from codeofpaper_cli.mcp import tools


# ---------- helpers ---------------------------------------------------------


def _patch_client(monkeypatch, mock_client):
    """Patch `tools._client()` to return a context-manager wrapping
    the provided MagicMock.
    """
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_client)
    cm.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(tools, "_client", lambda: cm)


# ---------- paper_lookup ----------------------------------------------------


class TestPaperLookup:
    def test_happy_path_returns_paper_and_repos(self, monkeypatch):
        mock = MagicMock()
        mock.get_paper.return_value = {"arxiv_id": "2010.11929", "title": "ViT"}
        mock.get_paper_repos.return_value = {
            "paper": {"arxiv_id": "2010.11929", "no_confident_match": False},
            "top_repos": [{"full_name": "google-research/vision_transformer", "tier": "official"}],
        }
        _patch_client(monkeypatch, mock)

        result = tools.paper_lookup("2010.11929")

        assert result["paper"]["arxiv_id"] == "2010.11929"
        assert result["top_repos"][0]["full_name"] == "google-research/vision_transformer"
        assert result["no_confident_match"] is False
        mock.get_paper.assert_called_once_with("2010.11929")
        mock.get_paper_repos.assert_called_once_with(
            "2010.11929", limit=10, include_possible=False
        )

    def test_accepts_arxiv_url(self, monkeypatch):
        mock = MagicMock()
        mock.get_paper.return_value = {"arxiv_id": "2010.11929"}
        mock.get_paper_repos.return_value = {"top_repos": []}
        _patch_client(monkeypatch, mock)

        result = tools.paper_lookup("https://arxiv.org/abs/2010.11929v2")

        assert "error" not in result
        mock.get_paper.assert_called_once_with("2010.11929")

    def test_404_on_repos_is_not_fatal(self, monkeypatch):
        """Paper exists but has no confident matches → return paper anyway."""
        mock = MagicMock()
        mock.get_paper.return_value = {"arxiv_id": "1234.56789"}
        mock.get_paper_repos.side_effect = APIError(404, "not found", NOT_FOUND)
        _patch_client(monkeypatch, mock)

        result = tools.paper_lookup("1234.56789")

        assert result["paper"]["arxiv_id"] == "1234.56789"
        assert result["top_repos"] == []
        assert result["no_confident_match"] is False

    def test_paper_api_error_surfaces_as_dict(self, monkeypatch):
        mock = MagicMock()
        mock.get_paper.side_effect = APIError(404, "not found", NOT_FOUND)
        _patch_client(monkeypatch, mock)

        result = tools.paper_lookup("2010.11929")

        assert result == {"error": "not found", "status": 404}

    def test_connection_error_surfaces_as_dict(self, monkeypatch):
        mock = MagicMock()
        mock.get_paper.side_effect = ConnectionError_("dns fail")
        _patch_client(monkeypatch, mock)

        result = tools.paper_lookup("2010.11929")

        assert result["error"] == "dns fail"
        assert "status" not in result

    def test_unparseable_id_surfaces_api_404(self, monkeypatch):
        """extract_arxiv_id() is permissive (returns input as-is for
        unknown formats, since OpenReview IDs etc. are also valid),
        so unparseable input falls through to the API and we surface
        the resulting 404 as a structured error dict.
        """
        mock = MagicMock()
        mock.get_paper.side_effect = APIError(404, "Paper not found", NOT_FOUND)
        _patch_client(monkeypatch, mock)

        result = tools.paper_lookup("not-an-arxiv-id")

        assert result == {"error": "Paper not found", "status": 404}


# ---------- code_for_paper --------------------------------------------------


class TestCodeForPaper:
    def test_happy_path(self, monkeypatch):
        mock = MagicMock()
        mock.get_paper_repos.return_value = {
            "top_repos": [{"full_name": "owner/repo", "tier": "official", "stars": 1000}],
            "paper": {"arxiv_id": "2010.11929"},
        }
        _patch_client(monkeypatch, mock)

        result = tools.code_for_paper("2010.11929", limit=3)

        assert result["top_repos"][0]["full_name"] == "owner/repo"
        mock.get_paper_repos.assert_called_once_with(
            "2010.11929", limit=3, include_possible=False
        )

    def test_limit_is_clamped(self, monkeypatch):
        mock = MagicMock()
        mock.get_paper_repos.return_value = {"top_repos": []}
        _patch_client(monkeypatch, mock)

        tools.code_for_paper("2010.11929", limit=999)
        assert mock.get_paper_repos.call_args.kwargs["limit"] == 25

        mock.reset_mock()
        tools.code_for_paper("2010.11929", limit=0)
        assert mock.get_paper_repos.call_args.kwargs["limit"] == 1

    def test_include_possible_pass_through(self, monkeypatch):
        mock = MagicMock()
        mock.get_paper_repos.return_value = {"top_repos": []}
        _patch_client(monkeypatch, mock)

        tools.code_for_paper("2010.11929", include_possible=True)
        assert mock.get_paper_repos.call_args.kwargs["include_possible"] is True

    def test_api_error_surfaces_as_dict(self, monkeypatch):
        mock = MagicMock()
        mock.get_paper_repos.side_effect = APIError(429, "rate limited", RATE_LIMITED)
        _patch_client(monkeypatch, mock)

        result = tools.code_for_paper("2010.11929")

        assert result == {"error": "rate limited", "status": 429}


# ---------- search_papers ---------------------------------------------------


class TestSearchPapers:
    def test_happy_path(self, monkeypatch):
        mock = MagicMock()
        mock.search_papers.return_value = {
            "papers": [{"arxiv_id": "2010.11929", "title": "ViT", "has_repos": True}],
            "total": 1,
        }
        _patch_client(monkeypatch, mock)

        result = tools.search_papers("vision transformer", limit=5, year=2020)

        assert result["total"] == 1
        assert result["papers"][0]["arxiv_id"] == "2010.11929"
        mock.search_papers.assert_called_once_with(
            query="vision transformer", limit=5, year=2020, venue=None
        )

    def test_limit_is_clamped(self, monkeypatch):
        mock = MagicMock()
        mock.search_papers.return_value = {"papers": []}
        _patch_client(monkeypatch, mock)

        tools.search_papers("x", limit=999)
        assert mock.search_papers.call_args.kwargs["limit"] == 50

    def test_has_code_filters_client_side(self, monkeypatch):
        mock = MagicMock()
        mock.search_papers.return_value = {
            "papers": [
                {"arxiv_id": "1", "has_repos": True},
                {"arxiv_id": "2", "has_repos": False, "repo_count": 0},
                {"arxiv_id": "3", "repo_count": 4},
            ],
            "total": 3,
        }
        _patch_client(monkeypatch, mock)

        result = tools.search_papers("x", has_code=True)

        ids = [p["arxiv_id"] for p in result["papers"]]
        assert ids == ["1", "3"]

    def test_api_error_surfaces_as_dict(self, monkeypatch):
        mock = MagicMock()
        mock.search_papers.side_effect = APIError(500, "server error", GENERAL_ERROR)
        _patch_client(monkeypatch, mock)

        result = tools.search_papers("x")

        assert result == {"error": "server error", "status": 500}


# ---------- server module ---------------------------------------------------


class TestServerModule:
    """Light smoke checks that don't require fastmcp to be installed."""

    def test_main_is_importable_from_package(self):
        from codeofpaper_cli.mcp import main
        assert callable(main)

    def test_build_app_raises_clear_error_without_fastmcp(self, monkeypatch):
        """If fastmcp isn't installed, build_app() should SystemExit with
        a message pointing the user at the `[mcp]` extra."""
        import builtins

        from codeofpaper_cli.mcp import server

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "fastmcp":
                raise ImportError("No module named 'fastmcp'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        with pytest.raises(SystemExit) as exc:
            server.build_app()
        assert "codeofpaper[mcp]" in str(exc.value)
