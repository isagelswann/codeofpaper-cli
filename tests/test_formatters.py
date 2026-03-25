"""Tests for output formatters."""

import json

import pytest

from codeofpaper_cli.formatters import (
    _format_bibtex_author,
    _format_bibtex_authors,
    _format_stars,
    _truncate,
    build_category_table,
    build_code_drops_table,
    build_conference_table,
    build_paper_table,
    build_repo_table,
    format_bibtex,
    format_bibtex_entry,
    format_csv,
    format_json,
    format_jsonl,
    format_quiet,
    print_error,
)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


class TestFormatJson:
    def test_dict(self):
        result = format_json({"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_list(self):
        result = format_json([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_pretty_printed(self):
        result = format_json({"a": 1})
        assert "\n" in result  # pretty-printed has newlines

    def test_unicode_preserved(self):
        result = format_json({"name": "Müller"})
        assert "Müller" in result


# ---------------------------------------------------------------------------
# JSONL
# ---------------------------------------------------------------------------


class TestFormatJsonl:
    def test_basic(self):
        items = [{"id": "1"}, {"id": "2"}]
        result = format_jsonl(items)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"id": "1"}
        assert json.loads(lines[1]) == {"id": "2"}

    def test_empty(self):
        assert format_jsonl([]) == ""

    def test_single_item(self):
        result = format_jsonl([{"x": 1}])
        assert json.loads(result) == {"x": 1}


# ---------------------------------------------------------------------------
# Quiet
# ---------------------------------------------------------------------------


class TestFormatQuiet:
    def test_arxiv_ids(self):
        items = [{"arxiv_id": "2010.11929"}, {"arxiv_id": "2103.14030"}]
        result = format_quiet(items)
        assert result == "2010.11929\n2103.14030"

    def test_fallback_to_id(self):
        items = [{"id": "abc123"}]
        result = format_quiet(items)
        assert result == "abc123"

    def test_custom_id_key(self):
        items = [{"full_name": "owner/repo"}]
        result = format_quiet(items, id_key="full_name")
        assert result == "owner/repo"

    def test_empty(self):
        assert format_quiet([]) == ""

    def test_skips_empty_ids(self):
        items = [{"arxiv_id": "2010.11929"}, {"id": ""}, {"arxiv_id": "2103.14030"}]
        result = format_quiet(items)
        assert result == "2010.11929\n2103.14030"


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


class TestFormatCsv:
    def test_basic(self):
        items = [
            {"arxiv_id": "2010.11929", "title": "ViT", "year": 2020},
            {"arxiv_id": "2103.14030", "title": "Swin", "year": 2021},
        ]
        result = format_csv(items)
        lines = result.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "arxiv_id" in lines[0]
        assert "2010.11929" in lines[1]

    def test_custom_columns(self):
        items = [{"a": 1, "b": 2, "c": 3}]
        result = format_csv(items, columns=["a", "c"])
        lines = [l.rstrip("\r") for l in result.strip().split("\n")]
        assert "a,c" == lines[0]
        assert "1,3" == lines[1]

    def test_empty(self):
        assert format_csv([]) == ""

    def test_missing_columns(self):
        items = [{"a": 1}]
        result = format_csv(items, columns=["a", "b"])
        lines = result.strip().split("\n")
        assert lines[1] == "1,"


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------


class TestBibtexAuthorFormatting:
    def test_two_word_name(self):
        assert _format_bibtex_author("Albert Einstein") == "Einstein, Albert"

    def test_three_word_name(self):
        assert _format_bibtex_author("John von Neumann") == "Neumann, John von"

    def test_single_word(self):
        assert _format_bibtex_author("Madonna") == "Madonna"

    def test_empty_string(self):
        assert _format_bibtex_author("") == ""

    def test_whitespace(self):
        assert _format_bibtex_author("  Alan Turing  ") == "Turing, Alan"

    def test_hyphenated_last_name(self):
        assert _format_bibtex_author("Jean-Pierre Serre") == "Serre, Jean-Pierre"

    def test_multiple_authors(self):
        result = _format_bibtex_authors(["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"])
        assert result == "Vaswani, Ashish and Shazeer, Noam and Parmar, Niki"

    def test_empty_list(self):
        assert _format_bibtex_authors([]) == ""


class TestFormatBibtex:
    def test_basic_entry(self):
        paper = {
            "arxiv_id": "1706.03762",
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani", "Noam Shazeer"],
            "published_date": "2017-06-12",
            "url": "https://arxiv.org/abs/1706.03762",
        }
        result = format_bibtex_entry(paper)
        assert "@article{1706_03762," in result
        assert "Attention Is All You Need" in result
        assert "Vaswani, Ashish and Shazeer, Noam" in result
        assert "2017" in result
        assert "eprint" in result

    def test_missing_fields(self):
        paper = {"arxiv_id": "2010.11929", "title": "ViT"}
        result = format_bibtex_entry(paper)
        assert "@article{2010_11929," in result
        assert "author" not in result  # no authors → no author field

    def test_multiple_entries(self):
        papers = [
            {"arxiv_id": "1706.03762", "title": "Attention"},
            {"arxiv_id": "2010.11929", "title": "ViT"},
        ]
        result = format_bibtex(papers)
        assert result.count("@article{") == 2
        assert "\n\n" in result  # entries separated by blank line

    def test_old_format_id(self):
        paper = {"arxiv_id": "hep-th/9901001", "title": "Test"}
        result = format_bibtex_entry(paper)
        assert "@article{hep-th_9901001," in result

    def test_summary_truncation(self):
        paper = {
            "arxiv_id": "test",
            "title": "Test",
            "summary": "x" * 600,
        }
        result = format_bibtex_entry(paper)
        assert "abstract" in result
        assert "..." in result  # truncated


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_truncate_short(self):
        assert _truncate("short", 10) == "short"

    def test_truncate_long(self):
        result = _truncate("a very long string here", 10)
        assert len(result) <= 10
        assert result.endswith("...")

    def test_truncate_empty(self):
        assert _truncate("", 10) == ""

    def test_truncate_none(self):
        assert _truncate(None, 10) == ""

    def test_format_stars_thousands(self):
        assert _format_stars(9842) == "9.8k"

    def test_format_stars_exact_thousand(self):
        assert _format_stars(1000) == "1.0k"

    def test_format_stars_small(self):
        assert _format_stars(500) == "500"

    def test_format_stars_zero(self):
        assert _format_stars(0) == ""

    def test_format_stars_none(self):
        assert _format_stars(None) == ""


# ---------------------------------------------------------------------------
# Rich tables (smoke tests — verify they build without error)
# ---------------------------------------------------------------------------


class TestTableBuilders:
    def test_paper_table_basic(self):
        papers = [
            {
                "arxiv_id": "2010.11929",
                "title": "ViT: An Image is Worth 16x16 Words",
                "published_date": "2020-10-22",
                "repo_count": 47,
                "has_repos": True,
            }
        ]
        table = build_paper_table(papers, title="Search Results")
        assert table.title == "Search Results"
        assert table.row_count == 1

    def test_paper_table_with_score_and_rank(self):
        papers = [
            {
                "arxiv_id": "2010.11929",
                "title": "ViT",
                "similarity": 0.94,
                "published_date": "2020-10-22",
            }
        ]
        table = build_paper_table(papers, show_score=True, score_key="similarity", show_rank=True)
        assert table.row_count == 1

    def test_paper_table_empty(self):
        table = build_paper_table([])
        assert table.row_count == 0

    def test_repo_table(self):
        repos = [
            {
                "full_name": "google-research/vision_transformer",
                "stars": 9842,
                "forks": 1203,
                "score": 0.95,
                "is_official": True,
            }
        ]
        table = build_repo_table(repos, title="Repos")
        assert table.row_count == 1

    def test_category_table(self):
        areas = [
            {
                "name": "Computer Vision",
                "categories": [
                    {"id": "cv_classification", "name": "Image Classification", "paper_count": 3707},
                    {"id": "cv_detection", "name": "Object Detection", "paper_count": 2313},
                ],
            }
        ]
        table = build_category_table(areas)
        assert table.row_count == 2

    def test_conference_table(self):
        confs = [
            {
                "name": "NeurIPS",
                "year": 2024,
                "total_papers": 4035,
                "papers_with_code": 1250,
                "github_percentage": 31.0,
            }
        ]
        table = build_conference_table(confs)
        assert table.row_count == 1

    def test_code_drops_table(self):
        drops = [
            {
                "paper_title": "HunyuanPortrait",
                "repo_name": "user/repo",
                "repo_stars": 284,
                "conference_name": "CVPR 2025",
                "is_official": True,
            }
        ]
        table = build_code_drops_table(drops)
        assert table.row_count == 1


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------


class TestPrintError:
    def test_json_format(self, capsys):
        print_error("Not found", "json")
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"error": "Not found"}

    def test_jsonl_format(self, capsys):
        print_error("Rate limited", "jsonl")
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"error": "Rate limited"}

    def test_quiet_format(self, capsys):
        print_error("Some error", "quiet")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_table_format(self, capsys):
        print_error("Connection failed", "table")
        captured = capsys.readouterr()
        # Rich prints to stderr
        assert "Connection failed" in captured.err
