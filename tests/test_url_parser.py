"""Tests for URL parsing utilities."""


from codeofpaper_cli.url_parser import (
    extract_arxiv_id,
    extract_github_repo,
    is_arxiv_url,
    is_github_url,
)


class TestExtractArxivId:
    # --- Bare IDs (pass through) ---

    def test_new_format_5digit(self):
        assert extract_arxiv_id("2010.11929") == "2010.11929"

    def test_new_format_4digit(self):
        assert extract_arxiv_id("0704.0001") == "0704.0001"

    def test_new_format_with_version(self):
        assert extract_arxiv_id("2010.11929v2") == "2010.11929"

    def test_old_format(self):
        assert extract_arxiv_id("hep-th/9901001") == "hep-th/9901001"

    def test_old_format_with_version(self):
        assert extract_arxiv_id("hep-th/9901001v3") == "hep-th/9901001"

    # --- arXiv URLs ---

    def test_abs_url(self):
        assert extract_arxiv_id("https://arxiv.org/abs/2010.11929") == "2010.11929"

    def test_abs_url_with_version(self):
        assert extract_arxiv_id("https://arxiv.org/abs/2010.11929v2") == "2010.11929"

    def test_pdf_url(self):
        assert extract_arxiv_id("https://arxiv.org/pdf/2010.11929") == "2010.11929"

    def test_pdf_url_with_version(self):
        assert extract_arxiv_id("https://arxiv.org/pdf/2010.11929v1") == "2010.11929"

    def test_html_url(self):
        assert extract_arxiv_id("https://arxiv.org/html/2010.11929") == "2010.11929"

    def test_old_format_url(self):
        assert extract_arxiv_id("https://arxiv.org/abs/hep-th/9901001") == "hep-th/9901001"

    def test_http_url(self):
        assert extract_arxiv_id("http://arxiv.org/abs/2010.11929") == "2010.11929"

    # --- Edge cases ---

    def test_whitespace_stripped(self):
        assert extract_arxiv_id("  2010.11929  ") == "2010.11929"

    def test_openreview_id_passthrough(self):
        """Non-arXiv IDs should pass through unchanged."""
        assert extract_arxiv_id("or_iEeiZlTbts") == "or_iEeiZlTbts"

    def test_random_string_passthrough(self):
        assert extract_arxiv_id("some-random-string") == "some-random-string"


class TestExtractGithubRepo:
    # --- Bare owner/repo (pass through) ---

    def test_simple_repo(self):
        assert extract_github_repo("google-research/vision_transformer") == "google-research/vision_transformer"

    def test_dotted_repo(self):
        assert extract_github_repo("owner/my.repo") == "owner/my.repo"

    # --- GitHub URLs ---

    def test_https_url(self):
        assert extract_github_repo("https://github.com/google-research/vision_transformer") == "google-research/vision_transformer"

    def test_http_url(self):
        assert extract_github_repo("http://github.com/owner/repo") == "owner/repo"

    def test_url_with_path(self):
        assert extract_github_repo("https://github.com/owner/repo/tree/main/src") == "owner/repo"

    def test_url_with_git_suffix(self):
        assert extract_github_repo("https://github.com/owner/repo.git") == "owner/repo"

    def test_url_with_issues(self):
        assert extract_github_repo("https://github.com/owner/repo/issues/42") == "owner/repo"

    # --- Edge cases ---

    def test_whitespace_stripped(self):
        assert extract_github_repo("  owner/repo  ") == "owner/repo"

    def test_random_string_passthrough(self):
        assert extract_github_repo("not-a-repo") == "not-a-repo"


class TestIsArxivUrl:
    def test_true_for_arxiv_url(self):
        assert is_arxiv_url("https://arxiv.org/abs/2010.11929") is True

    def test_false_for_bare_id(self):
        assert is_arxiv_url("2010.11929") is False

    def test_false_for_github(self):
        assert is_arxiv_url("https://github.com/owner/repo") is False


class TestIsGithubUrl:
    def test_true_for_github_url(self):
        assert is_github_url("https://github.com/owner/repo") is True

    def test_false_for_bare_repo(self):
        assert is_github_url("owner/repo") is False

    def test_false_for_arxiv(self):
        assert is_github_url("https://arxiv.org/abs/2010.11929") is False
