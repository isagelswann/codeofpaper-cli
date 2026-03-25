"""Tests for the research command.

Tests the multi-step orchestration across all three depth levels,
partial failure handling, and all output formats.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from codeofpaper_cli.client import APIError, ConnectionError_
from codeofpaper_cli.exit_codes import CONNECTION_ERROR, NOT_FOUND
from codeofpaper_cli.main import app
from codeofpaper_cli.state import OutputFormat, state

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_state():
    state.output = OutputFormat.table
    state.api_url = "https://api.codeofpaper.com"
    state.api_key = None
    yield


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

PAPERS = [
    {
        "arxiv_id": "2010.11929",
        "title": "An Image is Worth 16x16 Words",
        "authors": ["Alexei Dosovitskiy"],
        "published_date": "2020-10-22",
        "categories": ["cs.CV", "cs.AI"],
        "has_repos": True,
        "repo_count": 47,
        "has_official_repo": True,
    },
    {
        "arxiv_id": "2103.14030",
        "title": "Swin Transformer",
        "authors": ["Ze Liu"],
        "published_date": "2021-03-25",
        "categories": ["cs.CV"],
        "has_repos": True,
        "repo_count": 20,
        "has_official_repo": True,
    },
    {
        "arxiv_id": "2106.09681",
        "title": "CoAtNet: Marrying Convolution and Attention",
        "authors": ["Zihang Dai"],
        "published_date": "2021-06-17",
        "categories": ["cs.CV", "cs.LG"],
        "has_repos": True,
        "repo_count": 5,
        "has_official_repo": False,
    },
]

SEARCH_RESPONSE = {"query": "vision transformers", "count": 3, "papers": PAPERS}

REPOS_RESPONSE = {
    "paper": {"arxiv_id": "2010.11929"},
    "top_repos": [
        {
            "full_name": "google-research/vision_transformer",
            "html_url": "https://github.com/google-research/vision_transformer",
            "stars": 9842,
            "forks": 1203,
            "score": 0.95,
            "is_official": True,
        },
    ],
}

REPOS_RESPONSE_2 = {
    "paper": {"arxiv_id": "2103.14030"},
    "top_repos": [
        {
            "full_name": "microsoft/Swin-Transformer",
            "html_url": "https://github.com/microsoft/Swin-Transformer",
            "stars": 8500,
            "forks": 900,
            "score": 0.90,
            "is_official": True,
        },
    ],
}

SIMILAR_RESPONSE = {
    "paper_id": "2010.11929",
    "similar": [
        {
            "arxiv_id": "2012.12877",
            "title": "Training data-efficient image transformers",
            "similarity_score": 0.94,
            "has_repos": True,
            "published_date": "2020-12-23",
        },
        {
            "arxiv_id": "2105.15075",
            "title": "Scaling Vision Transformers",
            "similarity_score": 0.91,
            "has_repos": True,
            "published_date": "2021-05-31",
        },
    ],
}


def _mock_client_instance():
    """Create a mock Client with default responses for all methods."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.search_papers.return_value = SEARCH_RESPONSE
    mock.get_paper_repos.side_effect = [REPOS_RESPONSE, REPOS_RESPONSE_2, REPOS_RESPONSE]
    mock.get_similar.return_value = SIMILAR_RESPONSE
    return mock


# ---------------------------------------------------------------------------
# Shallow depth (search only)
# ---------------------------------------------------------------------------


class TestResearchShallow:
    @patch("codeofpaper_cli.commands.research.Client")
    def test_json(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "--depth", "shallow", "vision transformers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query"] == "vision transformers"
        assert data["depth"] == "shallow"
        assert data["landscape"]["total_papers"] == 3
        assert data["landscape"]["with_code"] == 3
        assert data["_meta"]["api_calls"] == 1
        # Shallow doesn't fetch repos
        assert data["repos"] == []
        assert data["related"] == []

    @patch("codeofpaper_cli.commands.research.Client")
    def test_quiet(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-q", "research", "--depth", "shallow", "vision transformers"])
        assert result.exit_code == 0
        ids = result.output.strip().split("\n")
        assert "2010.11929" in ids

    @patch("codeofpaper_cli.commands.research.Client")
    def test_table(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["research", "--depth", "shallow", "vision transformers"])
        assert result.exit_code == 0
        assert "Landscape" in result.output
        assert "Key Papers" in result.output
        # No implementations section in shallow
        assert "Top Implementations" not in result.output


# ---------------------------------------------------------------------------
# Medium depth (default — search + repos)
# ---------------------------------------------------------------------------


class TestResearchMedium:
    @patch("codeofpaper_cli.commands.research.Client")
    def test_json(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "vision transformers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["depth"] == "medium"
        assert data["_meta"]["api_calls"] == 4  # 1 search + 3 repo calls
        assert len(data["repos"]) >= 1
        assert data["related"] == []  # No similar in medium

    @patch("codeofpaper_cli.commands.research.Client")
    def test_table_has_implementations(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["research", "vision transformers"])
        assert result.exit_code == 0
        assert "Top Implementations" in result.output
        assert "vision_transformer" in result.output

    @patch("codeofpaper_cli.commands.research.Client")
    def test_csv(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "csv", "research", "vision transformers"])
        assert result.exit_code == 0
        assert "arxiv_id" in result.output
        assert "2010.11929" in result.output

    @patch("codeofpaper_cli.commands.research.Client")
    def test_bibtex(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "bibtex", "research", "vision transformers"])
        assert result.exit_code == 0
        assert "@article{2010_11929" in result.output

    @patch("codeofpaper_cli.commands.research.Client")
    def test_jsonl(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "jsonl", "research", "vision transformers"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["arxiv_id"] == "2010.11929"


# ---------------------------------------------------------------------------
# Deep depth (search + repos + similar)
# ---------------------------------------------------------------------------


class TestResearchDeep:
    @patch("codeofpaper_cli.commands.research.Client")
    def test_json(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "--depth", "deep", "vision transformers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["depth"] == "deep"
        assert data["_meta"]["api_calls"] == 5  # 1 search + 3 repos + 1 similar
        assert len(data["related"]) == 2
        assert data["related"][0]["similarity_score"] == 0.94

    @patch("codeofpaper_cli.commands.research.Client")
    def test_table_has_related(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["research", "--depth", "deep", "vision transformers"])
        assert result.exit_code == 0
        assert "Related (via semantic similarity" in result.output
        assert "2012.12877" in result.output


# ---------------------------------------------------------------------------
# Landscape statistics
# ---------------------------------------------------------------------------


class TestLandscape:
    @patch("codeofpaper_cli.commands.research.Client")
    def test_category_aggregation(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "--depth", "shallow", "test"])
        data = json.loads(result.output)
        cats = data["landscape"]["top_categories"]
        # cs.CV should be most frequent (appears in all 3 papers)
        assert cats[0]["category"] == "cs.CV"
        assert cats[0]["count"] == 3

    @patch("codeofpaper_cli.commands.research.Client")
    def test_date_range(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "--depth", "shallow", "test"])
        data = json.loads(result.output)
        date_range = data["landscape"]["date_range"]
        assert date_range[0] == "2020-10"
        assert date_range[1] == "2021-06"

    @patch("codeofpaper_cli.commands.research.Client")
    def test_official_count(self, MockClient):
        mock = _mock_client_instance()
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "--depth", "shallow", "test"])
        data = json.loads(result.output)
        assert data["landscape"]["official_repos"] == 2  # papers 1 and 2 have official


# ---------------------------------------------------------------------------
# Partial failure handling
# ---------------------------------------------------------------------------


class TestPartialFailure:
    @patch("codeofpaper_cli.commands.research.Client")
    def test_one_repo_call_fails(self, MockClient):
        """If one repo lookup 404s, it's skipped with a warning."""
        mock = _mock_client_instance()
        mock.get_paper_repos.side_effect = [
            REPOS_RESPONSE,
            APIError(status_code=404, detail="Paper not found", exit_code=NOT_FOUND),
            REPOS_RESPONSE,
        ]
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "vision transformers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["warnings"]) == 1
        assert data["warnings"][0]["paper_id"] == "2103.14030"
        # Still got repos from the other calls
        assert len(data["repos"]) >= 1

    @patch("codeofpaper_cli.commands.research.Client")
    def test_similar_fails_gracefully(self, MockClient):
        """Deep mode: if similar call fails, related is empty with warning."""
        mock = _mock_client_instance()
        mock.get_similar.side_effect = APIError(
            status_code=500, detail="Internal error", exit_code=1,
        )
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "--depth", "deep", "test"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["related"] == []
        assert any("similar" in w["error"] for w in data["warnings"])

    @patch("codeofpaper_cli.commands.research.Client")
    def test_similar_error_in_200(self, MockClient):
        """API returns 200 with error field in similar response."""
        mock = _mock_client_instance()
        mock.get_similar.return_value = {
            "paper_id": "2010.11929",
            "similar": [],
            "error": "No embedding found",
        }
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "--depth", "deep", "test"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["related"] == []
        assert len(data["warnings"]) >= 1

    @patch("codeofpaper_cli.commands.research.Client")
    def test_table_shows_warnings(self, MockClient):
        """Warnings shown in table mode footer."""
        mock = _mock_client_instance()
        mock.get_paper_repos.side_effect = [
            REPOS_RESPONSE,
            APIError(status_code=404, detail="Not found", exit_code=NOT_FOUND),
            REPOS_RESPONSE,
        ]
        MockClient.return_value = mock
        result = runner.invoke(app, ["research", "vision transformers"])
        assert result.exit_code == 0
        assert "skipped" in result.output.lower()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestResearchErrors:
    @patch("codeofpaper_cli.commands.research.Client")
    def test_search_fails(self, MockClient):
        """If the initial search fails, entire command fails."""
        MockClient.return_value.__enter__ = MagicMock(return_value=MockClient.return_value)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        MockClient.return_value.search_papers.side_effect = ConnectionError_(
            detail="Cannot reach API"
        )
        result = runner.invoke(app, ["-o", "json", "research", "test"])
        assert result.exit_code == CONNECTION_ERROR

    def test_invalid_depth(self):
        result = runner.invoke(app, ["-o", "json", "research", "--depth", "extreme", "test"])
        assert result.exit_code == 1
        assert "error" in result.output.lower()


# ---------------------------------------------------------------------------
# Repo deduplication
# ---------------------------------------------------------------------------


class TestRepoDedup:
    @patch("codeofpaper_cli.commands.research.Client")
    def test_duplicate_repos_deduped(self, MockClient):
        """Same repo appearing for multiple papers gets deduped."""
        mock = _mock_client_instance()
        # Both papers return the same repo
        mock.get_paper_repos.side_effect = [REPOS_RESPONSE, REPOS_RESPONSE, REPOS_RESPONSE]
        MockClient.return_value = mock
        result = runner.invoke(app, ["-o", "json", "research", "test"])
        data = json.loads(result.output)
        repo_names = [r["full_name"] for r in data["repos"]]
        assert len(repo_names) == len(set(repo_names))  # all unique
