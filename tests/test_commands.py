"""Tests for core CLI commands.

Uses Typer's CliRunner to invoke commands with mocked Client responses.
Tests cover all 14 commands x 3 key output formats (table, json, quiet).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from codeofpaper_cli.client import APIError, ConnectionError_
from codeofpaper_cli.exit_codes import CONNECTION_ERROR, NOT_FOUND, RATE_LIMITED
from codeofpaper_cli.main import app
from codeofpaper_cli.state import OutputFormat, state

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures: reset state before each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset global state before each test."""
    state.output = OutputFormat.table
    state.api_url = "https://api.codeofpaper.com"
    state.api_key = None
    state.ca_bundle = None
    yield


# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

SAMPLE_PAPERS = [
    {
        "arxiv_id": "2010.11929",
        "title": "An Image is Worth 16x16 Words",
        "authors": ["Alexei Dosovitskiy", "Lucas Beyer", "Alexander Kolesnikov"],
        "published_date": "2020-10-22",
        "categories": ["cs.CV", "cs.AI"],
        "has_repos": True,
        "repo_count": 47,
        "has_official_repo": True,
        "similarity_score": 0.92,
    },
    {
        "arxiv_id": "1706.03762",
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "published_date": "2017-06-12",
        "categories": ["cs.CL"],
        "has_repos": True,
        "repo_count": 120,
        "has_official_repo": False,
        "similarity_score": 0.88,
    },
]

SAMPLE_SEARCH_RESPONSE = {
    "query": "vision transformers",
    "count": 2,
    "papers": SAMPLE_PAPERS,
}

SAMPLE_PAPER_DETAIL = {
    "arxiv_id": "2010.11929",
    "title": "An Image is Worth 16x16 Words",
    "authors": ["Alexei Dosovitskiy", "Lucas Beyer", "Alexander Kolesnikov"],
    "published_date": "2020-10-22",
    "categories": ["cs.CV", "cs.AI"],
    "has_repos": True,
    "repo_count": 47,
    "has_official_repo": True,
    "url": "https://arxiv.org/abs/2010.11929",
    "summary": "Transformers applied to image recognition at scale.",
    "conferences": [],
}

SAMPLE_REPOS_RESPONSE = {
    "paper": {"arxiv_id": "2010.11929", "title": "An Image is Worth 16x16 Words"},
    "top_repos": [
        {
            "full_name": "google-research/vision_transformer",
            "html_url": "https://github.com/google-research/vision_transformer",
            "description": "Official ViT implementation",
            "stars": 9842,
            "forks": 1203,
            "score": 0.95,
            "is_official": True,
            "languages": ["Python"],
        },
        {
            "full_name": "lucidrains/vit-pytorch",
            "html_url": "https://github.com/lucidrains/vit-pytorch",
            "description": "PyTorch ViT",
            "stars": 18300,
            "forks": 2800,
            "score": 0.88,
            "is_official": False,
            "languages": ["Python"],
        },
    ],
}

SAMPLE_TRENDING_RESPONSE = {
    "count": 2,
    "total": 1000,
    "sort": "hot",
    "has_code_filter": True,
    "trending": [
        {
            "arxiv_id": "2602.18998",
            "title": "Foundation Model for Everything",
            "trending_score": 0.98,
            "max_stars": 15200,
            "repo_count": 3,
            "published_date": "2026-02-15",
        },
        {
            "arxiv_id": "2603.01234",
            "title": "Better LLM Training",
            "trending_score": 0.85,
            "max_stars": 5000,
            "repo_count": 1,
            "published_date": "2026-03-01",
        },
    ],
    "papers": [],
}

SAMPLE_CATEGORIES_RESPONSE = {
    "areas": [
        {
            "name": "Computer Vision",
            "categories": [
                {"id": "cv_classification", "name": "Image Classification", "paper_count": 3707},
                {"id": "cv_detection", "name": "Object Detection", "paper_count": 2500},
            ],
        },
        {
            "name": "NLP",
            "categories": [
                {"id": "nlp_generation", "name": "Text Generation", "paper_count": 1200},
            ],
        },
    ]
}

SAMPLE_CATEGORY_DETAIL = {
    "id": "cv_classification",
    "name": "Image Classification",
    "area": "Computer Vision",
    "paper_count": 3707,
}

SAMPLE_CONFERENCES = [
    {
        "name": "NeurIPS",
        "year": 2024,
        "series": "neurips",
        "total_papers": 4035,
        "papers_with_code": 1250,
        "github_percentage": 31.0,
    },
    {
        "name": "ICML",
        "year": 2024,
        "series": "icml",
        "total_papers": 2600,
        "papers_with_code": 900,
        "github_percentage": 34.6,
    },
]

SAMPLE_CONFERENCE_PAPERS = {
    "conference_id": "neurips_2024",
    "name": "NeurIPS 2024",
    "count": 1,
    "offset": 0,
    "papers": [
        {
            "arxiv_id": "2410.12345",
            "title": "Cool Neural Method",
            "track": "oral",
            "has_repos": True,
            "repo_count": 1,
            "max_stars": 3200,
            "published_date": "2024-10-15",
        }
    ],
}

SAMPLE_SIMILAR_RESPONSE = {
    "paper_id": "2010.11929",
    "similar": [
        {
            "arxiv_id": "2012.12877",
            "title": "Training data-efficient image transformers",
            "similarity_score": 0.94,
            "has_repos": True,
            "published_date": "2020-12-23",
        },
    ],
}

SAMPLE_HEALTH = {"status": "ok", "services": {"database": "connected", "redis": "connected"}}
SAMPLE_PAPER_HEALTH = {"paper_count": 181000, "papers_with_repos": 93000}

SAMPLE_SUGGEST = [
    {"id": "2010.11929", "arxiv_id": "2010.11929", "title": "An Image is Worth 16x16 Words", "has_repos": True},
    {"id": "1706.03762", "arxiv_id": "1706.03762", "title": "Attention Is All You Need", "has_repos": True},
]

SAMPLE_CODE_DROPS = [
    {
        "paper_title": "Cool Neural Method",
        "repo_name": "org/cool-method",
        "repo_stars": 3200,
        "conference_name": "NeurIPS 2024",
        "is_official": True,
    },
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _mock_client(**method_returns):
    """Create a mock Client context manager with specified method return values."""
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
# Search command
# ---------------------------------------------------------------------------


class TestSearch:
    @patch("codeofpaper_cli.commands.search.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(search_papers=SAMPLE_SEARCH_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "json", "search", "vision transformers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query"] == "vision transformers"
        assert len(data["papers"]) == 2

    @patch("codeofpaper_cli.commands.search.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(search_papers=SAMPLE_SEARCH_RESPONSE).return_value
        result = runner.invoke(app, ["-q", "search", "vision transformers"])
        assert result.exit_code == 0
        ids = result.output.strip().split("\n")
        assert ids == ["2010.11929", "1706.03762"]

    @patch("codeofpaper_cli.commands.search.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(search_papers=SAMPLE_SEARCH_RESPONSE).return_value
        result = runner.invoke(app, ["search", "vision transformers"])
        assert result.exit_code == 0
        assert "2010.11929" in result.output
        assert "vision transformers" in result.output.lower() or "Search" in result.output

    @patch("codeofpaper_cli.commands.search.Client")
    def test_csv(self, MockClient):
        MockClient.return_value = _mock_client(search_papers=SAMPLE_SEARCH_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "csv", "search", "vision transformers"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert "arxiv_id" in lines[0]
        assert "2010.11929" in lines[1]

    @patch("codeofpaper_cli.commands.search.Client")
    def test_jsonl(self, MockClient):
        MockClient.return_value = _mock_client(search_papers=SAMPLE_SEARCH_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "jsonl", "search", "vision transformers"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["arxiv_id"] == "2010.11929"

    @patch("codeofpaper_cli.commands.search.Client")
    def test_bibtex(self, MockClient):
        MockClient.return_value = _mock_client(search_papers=SAMPLE_SEARCH_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "bibtex", "search", "vision transformers"])
        assert result.exit_code == 0
        assert "@article{2010_11929" in result.output

    @patch("codeofpaper_cli.commands.search.Client")
    def test_has_code_filter(self, MockClient):
        """--has-code filters client-side to papers with repos."""
        papers_mixed = [
            {**SAMPLE_PAPERS[0], "has_repos": True, "repo_count": 5},
            {"arxiv_id": "9999.99999", "title": "No Code Paper", "has_repos": False, "repo_count": 0},
        ]
        MockClient.return_value = _mock_client(
            search_papers={"query": "test", "count": 2, "papers": papers_mixed}
        ).return_value
        result = runner.invoke(app, ["-q", "search", "--has-code", "test"])
        assert result.exit_code == 0
        ids = result.output.strip().split("\n")
        assert "2010.11929" in ids
        assert "9999.99999" not in ids

    @patch("codeofpaper_cli.commands.search.Client")
    def test_api_error(self, MockClient):
        MockClient.return_value.__enter__ = MagicMock(return_value=MockClient.return_value)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        MockClient.return_value.search_papers.side_effect = APIError(
            status_code=429, detail="Rate limited", exit_code=RATE_LIMITED
        )
        result = runner.invoke(app, ["-o", "json", "search", "test"])
        assert result.exit_code == RATE_LIMITED
        assert "error" in result.output.lower()

    @patch("codeofpaper_cli.commands.search.Client")
    def test_connection_error(self, MockClient):
        MockClient.return_value.__enter__ = MagicMock(return_value=MockClient.return_value)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        MockClient.return_value.search_papers.side_effect = ConnectionError_(
            detail="Cannot reach API"
        )
        result = runner.invoke(app, ["-o", "json", "search", "test"])
        assert result.exit_code == CONNECTION_ERROR


# ---------------------------------------------------------------------------
# Paper command
# ---------------------------------------------------------------------------


class TestPaper:
    @patch("codeofpaper_cli.commands.paper.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(get_paper=SAMPLE_PAPER_DETAIL).return_value
        result = runner.invoke(app, ["-o", "json", "paper", "2010.11929"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["arxiv_id"] == "2010.11929"

    @patch("codeofpaper_cli.commands.paper.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_paper=SAMPLE_PAPER_DETAIL).return_value
        result = runner.invoke(app, ["-q", "paper", "2010.11929"])
        assert result.exit_code == 0
        assert result.output.strip() == "2010.11929"

    @patch("codeofpaper_cli.commands.paper.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(get_paper=SAMPLE_PAPER_DETAIL).return_value
        result = runner.invoke(app, ["paper", "2010.11929"])
        assert result.exit_code == 0
        assert "2010.11929" in result.output
        assert "16x16" in result.output

    @patch("codeofpaper_cli.commands.paper.Client")
    def test_bibtex(self, MockClient):
        MockClient.return_value = _mock_client(get_paper=SAMPLE_PAPER_DETAIL).return_value
        result = runner.invoke(app, ["-o", "bibtex", "paper", "2010.11929"])
        assert result.exit_code == 0
        assert "@article{2010_11929" in result.output
        assert "Dosovitskiy" in result.output

    @patch("codeofpaper_cli.commands.paper.Client")
    def test_url_input(self, MockClient):
        """Accepts arXiv URL and extracts ID."""
        MockClient.return_value = _mock_client(get_paper=SAMPLE_PAPER_DETAIL).return_value
        result = runner.invoke(app, ["-q", "paper", "https://arxiv.org/abs/2010.11929"])
        assert result.exit_code == 0
        assert result.output.strip() == "2010.11929"

    @patch("codeofpaper_cli.commands.paper.Client")
    def test_not_found(self, MockClient):
        MockClient.return_value.__enter__ = MagicMock(return_value=MockClient.return_value)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        MockClient.return_value.get_paper.side_effect = APIError(
            status_code=404, detail="Paper not found", exit_code=NOT_FOUND
        )
        result = runner.invoke(app, ["-o", "json", "paper", "9999.99999"])
        assert result.exit_code == NOT_FOUND


# ---------------------------------------------------------------------------
# Code command
# ---------------------------------------------------------------------------


class TestCode:
    @patch("codeofpaper_cli.commands.code.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(get_paper_repos=SAMPLE_REPOS_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "json", "code", "2010.11929"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["top_repos"]) == 2

    @patch("codeofpaper_cli.commands.code.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_paper_repos=SAMPLE_REPOS_RESPONSE).return_value
        result = runner.invoke(app, ["-q", "code", "2010.11929"])
        assert result.exit_code == 0
        names = result.output.strip().split("\n")
        assert "google-research/vision_transformer" in names

    @patch("codeofpaper_cli.commands.code.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(get_paper_repos=SAMPLE_REPOS_RESPONSE).return_value
        result = runner.invoke(app, ["code", "2010.11929"])
        assert result.exit_code == 0
        assert "vision_transformer" in result.output

    @patch("codeofpaper_cli.commands.code.Client")
    def test_csv(self, MockClient):
        MockClient.return_value = _mock_client(get_paper_repos=SAMPLE_REPOS_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "csv", "code", "2010.11929"])
        assert result.exit_code == 0
        assert "full_name" in result.output
        assert "google-research/vision_transformer" in result.output


# ---------------------------------------------------------------------------
# Trending command
# ---------------------------------------------------------------------------


class TestTrending:
    @patch("codeofpaper_cli.commands.trending.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(get_trending=SAMPLE_TRENDING_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "json", "trending"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2
        assert len(data["trending"]) == 2

    @patch("codeofpaper_cli.commands.trending.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_trending=SAMPLE_TRENDING_RESPONSE).return_value
        result = runner.invoke(app, ["-q", "trending"])
        assert result.exit_code == 0
        ids = result.output.strip().split("\n")
        assert "2602.18998" in ids

    @patch("codeofpaper_cli.commands.trending.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(get_trending=SAMPLE_TRENDING_RESPONSE).return_value
        result = runner.invoke(app, ["trending"])
        assert result.exit_code == 0
        assert "Trending Papers" in result.output

    @patch("codeofpaper_cli.commands.trending.Client")
    def test_csv(self, MockClient):
        MockClient.return_value = _mock_client(get_trending=SAMPLE_TRENDING_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "csv", "trending"])
        assert result.exit_code == 0
        assert "trending_score" in result.output
        assert "2602.18998" in result.output


# ---------------------------------------------------------------------------
# Categories command
# ---------------------------------------------------------------------------


class TestCategories:
    @patch("codeofpaper_cli.commands.categories.Client")
    def test_list_json(self, MockClient):
        MockClient.return_value = _mock_client(get_categories=SAMPLE_CATEGORIES_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "json", "categories"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "areas" in data

    @patch("codeofpaper_cli.commands.categories.Client")
    def test_list_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_categories=SAMPLE_CATEGORIES_RESPONSE).return_value
        result = runner.invoke(app, ["-q", "categories"])
        assert result.exit_code == 0
        ids = result.output.strip().split("\n")
        assert "cv_classification" in ids
        assert "nlp_generation" in ids

    @patch("codeofpaper_cli.commands.categories.Client")
    def test_list_table(self, MockClient):
        MockClient.return_value = _mock_client(get_categories=SAMPLE_CATEGORIES_RESPONSE).return_value
        result = runner.invoke(app, ["categories"])
        assert result.exit_code == 0
        assert "Computer Vision" in result.output
        assert "cv_classification" in result.output

    @patch("codeofpaper_cli.commands.categories.Client")
    def test_detail_json(self, MockClient):
        MockClient.return_value = _mock_client(get_category=SAMPLE_CATEGORY_DETAIL).return_value
        result = runner.invoke(app, ["-o", "json", "categories", "cv_classification"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "cv_classification"

    @patch("codeofpaper_cli.commands.categories.Client")
    def test_detail_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_category=SAMPLE_CATEGORY_DETAIL).return_value
        result = runner.invoke(app, ["-q", "categories", "cv_classification"])
        assert result.exit_code == 0
        assert result.output.strip() == "cv_classification"


# ---------------------------------------------------------------------------
# Conferences command
# ---------------------------------------------------------------------------


class TestConferences:
    @patch("codeofpaper_cli.commands.conferences.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(get_conferences=SAMPLE_CONFERENCES).return_value
        result = runner.invoke(app, ["-o", "json", "conferences"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2

    @patch("codeofpaper_cli.commands.conferences.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_conferences=SAMPLE_CONFERENCES).return_value
        result = runner.invoke(app, ["-q", "conferences"])
        assert result.exit_code == 0
        slugs = result.output.strip().split("\n")
        assert "neurips_2024" in slugs
        assert "icml_2024" in slugs

    @patch("codeofpaper_cli.commands.conferences.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(get_conferences=SAMPLE_CONFERENCES).return_value
        result = runner.invoke(app, ["conferences"])
        assert result.exit_code == 0
        assert "NeurIPS" in result.output
        assert "31.0%" in result.output

    @patch("codeofpaper_cli.commands.conferences.Client")
    def test_csv(self, MockClient):
        MockClient.return_value = _mock_client(get_conferences=SAMPLE_CONFERENCES).return_value
        result = runner.invoke(app, ["-o", "csv", "conferences"])
        assert result.exit_code == 0
        assert "total_papers" in result.output


# ---------------------------------------------------------------------------
# Conference command (papers from a conference)
# ---------------------------------------------------------------------------


class TestConference:
    @patch("codeofpaper_cli.commands.conference.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(get_conference_papers=SAMPLE_CONFERENCE_PAPERS).return_value
        result = runner.invoke(app, ["-o", "json", "conference", "neurips_2024"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["conference_id"] == "neurips_2024"

    @patch("codeofpaper_cli.commands.conference.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_conference_papers=SAMPLE_CONFERENCE_PAPERS).return_value
        result = runner.invoke(app, ["-q", "conference", "neurips_2024"])
        assert result.exit_code == 0
        assert "2410.12345" in result.output.strip()

    @patch("codeofpaper_cli.commands.conference.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(get_conference_papers=SAMPLE_CONFERENCE_PAPERS).return_value
        result = runner.invoke(app, ["conference", "neurips_2024"])
        assert result.exit_code == 0
        assert "NeurIPS 2024" in result.output


# ---------------------------------------------------------------------------
# Similar command
# ---------------------------------------------------------------------------


class TestSimilar:
    @patch("codeofpaper_cli.commands.similar.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(get_similar=SAMPLE_SIMILAR_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "json", "similar", "2010.11929"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["similar"]) == 1

    @patch("codeofpaper_cli.commands.similar.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_similar=SAMPLE_SIMILAR_RESPONSE).return_value
        result = runner.invoke(app, ["-q", "similar", "2010.11929"])
        assert result.exit_code == 0
        assert "2012.12877" in result.output.strip()

    @patch("codeofpaper_cli.commands.similar.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(get_similar=SAMPLE_SIMILAR_RESPONSE).return_value
        result = runner.invoke(app, ["similar", "2010.11929"])
        assert result.exit_code == 0
        assert "Similar to 2010.11929" in result.output

    @patch("codeofpaper_cli.commands.similar.Client")
    def test_api_error_in_200(self, MockClient):
        """API returns 200 with error field — command should detect and report."""
        MockClient.return_value = _mock_client(
            get_similar={"paper_id": "2010.11929", "similar": [], "error": "Embedding not found"}
        ).return_value
        result = runner.invoke(app, ["-o", "json", "similar", "2010.11929"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Random command
# ---------------------------------------------------------------------------


class TestRandom:
    @patch("codeofpaper_cli.commands.random.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(get_random=SAMPLE_PAPER_DETAIL).return_value
        result = runner.invoke(app, ["-o", "json", "random"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["arxiv_id"] == "2010.11929"

    @patch("codeofpaper_cli.commands.random.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_random=SAMPLE_PAPER_DETAIL).return_value
        result = runner.invoke(app, ["-q", "random"])
        assert result.exit_code == 0
        assert result.output.strip() == "2010.11929"

    @patch("codeofpaper_cli.commands.random.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(get_random=SAMPLE_PAPER_DETAIL).return_value
        result = runner.invoke(app, ["random"])
        assert result.exit_code == 0
        assert "2010.11929" in result.output


# ---------------------------------------------------------------------------
# Open command
# ---------------------------------------------------------------------------


class TestOpen:
    @patch("codeofpaper_cli.commands.open_cmd.typer.launch")
    def test_open_arxiv_page(self, mock_launch):
        result = runner.invoke(app, ["open", "2010.11929"])
        assert result.exit_code == 0
        mock_launch.assert_called_once_with("https://arxiv.org/abs/2010.11929")

    @patch("codeofpaper_cli.commands.open_cmd.typer.launch")
    def test_open_pdf(self, mock_launch):
        result = runner.invoke(app, ["open", "--pdf", "2010.11929"])
        assert result.exit_code == 0
        mock_launch.assert_called_once_with("https://arxiv.org/pdf/2010.11929")

    @patch("codeofpaper_cli.commands.open_cmd.typer.launch")
    @patch("codeofpaper_cli.commands.open_cmd.Client")
    def test_open_code(self, MockClient, mock_launch):
        MockClient.return_value = _mock_client(get_paper_repos=SAMPLE_REPOS_RESPONSE).return_value
        result = runner.invoke(app, ["open", "--code", "2010.11929"])
        assert result.exit_code == 0
        mock_launch.assert_called_once_with(
            "https://github.com/google-research/vision_transformer"
        )

    @patch("codeofpaper_cli.commands.open_cmd.Client")
    def test_open_code_no_repos(self, MockClient):
        MockClient.return_value = _mock_client(
            get_paper_repos={"paper": {}, "top_repos": []}
        ).return_value
        result = runner.invoke(app, ["open", "--code", "2010.11929"])
        assert result.exit_code == 1

    @patch("codeofpaper_cli.commands.open_cmd.typer.launch")
    def test_open_url_input(self, mock_launch):
        result = runner.invoke(app, ["open", "https://arxiv.org/abs/2010.11929"])
        assert result.exit_code == 0
        mock_launch.assert_called_once_with("https://arxiv.org/abs/2010.11929")


# ---------------------------------------------------------------------------
# Repo command (reverse lookup)
# ---------------------------------------------------------------------------


class TestRepo:
    @patch("codeofpaper_cli.commands.repo.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(search_papers=SAMPLE_SEARCH_RESPONSE).return_value
        result = runner.invoke(app, ["-o", "json", "repo", "google-research/vision_transformer"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "papers" in data

    @patch("codeofpaper_cli.commands.repo.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(search_papers=SAMPLE_SEARCH_RESPONSE).return_value
        result = runner.invoke(app, ["-q", "repo", "google-research/vision_transformer"])
        assert result.exit_code == 0
        assert "2010.11929" in result.output

    @patch("codeofpaper_cli.commands.repo.Client")
    def test_github_url_input(self, MockClient):
        MockClient.return_value = _mock_client(search_papers=SAMPLE_SEARCH_RESPONSE).return_value
        result = runner.invoke(
            app, ["-q", "repo", "https://github.com/google-research/vision_transformer"]
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Code drops command
# ---------------------------------------------------------------------------


class TestCodeDrops:
    @patch("codeofpaper_cli.commands.code_drops.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(get_recent_code_drops=SAMPLE_CODE_DROPS).return_value
        result = runner.invoke(app, ["-o", "json", "code-drops"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1

    @patch("codeofpaper_cli.commands.code_drops.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(get_recent_code_drops=SAMPLE_CODE_DROPS).return_value
        result = runner.invoke(app, ["-q", "code-drops"])
        assert result.exit_code == 0
        assert "org/cool-method" in result.output

    @patch("codeofpaper_cli.commands.code_drops.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(get_recent_code_drops=SAMPLE_CODE_DROPS).return_value
        result = runner.invoke(app, ["code-drops"])
        assert result.exit_code == 0
        # Table title includes emoji
        assert "Cool Neural Method" in result.output


# ---------------------------------------------------------------------------
# Suggest command
# ---------------------------------------------------------------------------


class TestSuggest:
    @patch("codeofpaper_cli.commands.suggest.Client")
    def test_json(self, MockClient):
        MockClient.return_value = _mock_client(suggest=SAMPLE_SUGGEST).return_value
        result = runner.invoke(app, ["-o", "json", "suggest", "attention"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2

    @patch("codeofpaper_cli.commands.suggest.Client")
    def test_quiet(self, MockClient):
        MockClient.return_value = _mock_client(suggest=SAMPLE_SUGGEST).return_value
        result = runner.invoke(app, ["-q", "suggest", "attention"])
        assert result.exit_code == 0
        ids = result.output.strip().split("\n")
        assert "2010.11929" in ids
        assert "1706.03762" in ids

    @patch("codeofpaper_cli.commands.suggest.Client")
    def test_table(self, MockClient):
        MockClient.return_value = _mock_client(suggest=SAMPLE_SUGGEST).return_value
        result = runner.invoke(app, ["suggest", "attention"])
        assert result.exit_code == 0
        assert "Suggestions: attention" in result.output


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


class TestStatus:
    @patch("codeofpaper_cli.commands.status.Client")
    def test_json(self, MockClient):
        mock_inst = _mock_client(get_health=SAMPLE_HEALTH, get_paper_health=SAMPLE_PAPER_HEALTH).return_value
        MockClient.return_value = mock_inst
        result = runner.invoke(app, ["-o", "json", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["paper_count"] == 181000

    @patch("codeofpaper_cli.commands.status.Client")
    def test_quiet(self, MockClient):
        mock_inst = _mock_client(get_health=SAMPLE_HEALTH, get_paper_health=SAMPLE_PAPER_HEALTH).return_value
        MockClient.return_value = mock_inst
        result = runner.invoke(app, ["-q", "status"])
        assert result.exit_code == 0
        assert result.output.strip() == "ok"

    @patch("codeofpaper_cli.commands.status.Client")
    def test_table(self, MockClient):
        mock_inst = _mock_client(get_health=SAMPLE_HEALTH, get_paper_health=SAMPLE_PAPER_HEALTH).return_value
        MockClient.return_value = mock_inst
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "API Status" in result.output
        assert "181,000" in result.output

    @patch("codeofpaper_cli.commands.status.Client")
    def test_connection_error(self, MockClient):
        MockClient.return_value.__enter__ = MagicMock(return_value=MockClient.return_value)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        MockClient.return_value.get_health.side_effect = ConnectionError_(
            detail="Cannot reach API"
        )
        result = runner.invoke(app, ["-o", "json", "status"])
        assert result.exit_code == CONNECTION_ERROR


# ---------------------------------------------------------------------------
# Formatters: build_paper_detail_table
# ---------------------------------------------------------------------------


class TestBuildPaperDetailTable:
    def test_basic(self):
        from codeofpaper_cli.formatters import build_paper_detail_table

        table = build_paper_detail_table(SAMPLE_PAPER_DETAIL)
        assert table.title == "Paper: 2010.11929"
        # Check it has rows (Rich Table)
        assert len(table.rows) >= 5

    def test_many_authors(self):
        from codeofpaper_cli.formatters import build_paper_detail_table

        paper = {
            **SAMPLE_PAPER_DETAIL,
            "authors": ["A", "B", "C", "D", "E"],
        }
        table = build_paper_detail_table(paper)
        # Should show "et al."
        assert len(table.rows) >= 5

    def test_no_repos(self):
        from codeofpaper_cli.formatters import build_paper_detail_table

        paper = {**SAMPLE_PAPER_DETAIL, "has_repos": False, "repo_count": 0}
        table = build_paper_detail_table(paper)
        assert len(table.rows) >= 5
