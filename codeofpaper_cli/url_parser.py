"""URL parsing utilities for arXiv and GitHub URLs.

Accepts full URLs anywhere an ID is expected:
    - arXiv: https://arxiv.org/abs/2010.11929 → "2010.11929"
    - arXiv PDF: https://arxiv.org/pdf/2010.11929v2 → "2010.11929"
    - GitHub: https://github.com/owner/repo → "owner/repo"
"""

from __future__ import annotations

import re

# arXiv ID patterns:
#   New format (2007+): YYMM.NNNNN (with optional vN version suffix)
#   Old format (pre-2007): category/YYMMNNN (e.g. hep-th/9901001)
_ARXIV_URL_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf|html)/(?:(\d{4}\.\d{4,5})(?:v\d+)?|([a-z-]+/\d{7})(?:v\d+)?)"
)
_ARXIV_NEW_ID_RE = re.compile(r"^(\d{4}\.\d{4,5})(?:v\d+)?$")
_ARXIV_OLD_ID_RE = re.compile(r"^([a-z-]+/\d{7})(?:v\d+)?$")

# GitHub URL pattern: https://github.com/owner/repo[/...]
_GITHUB_URL_RE = re.compile(
    r"github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"
)
_GITHUB_REPO_RE = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")


def extract_arxiv_id(input_str: str) -> str:
    """Extract an arXiv ID from a URL or return the input if already an ID.

    Args:
        input_str: An arXiv URL or bare arXiv ID.

    Returns:
        The bare arXiv ID (e.g. "2010.11929").

    Examples:
        >>> extract_arxiv_id("2010.11929")
        '2010.11929'
        >>> extract_arxiv_id("https://arxiv.org/abs/2010.11929")
        '2010.11929'
        >>> extract_arxiv_id("https://arxiv.org/pdf/2010.11929v2")
        '2010.11929'
    """
    input_str = input_str.strip()

    # Check if it's already a bare ID
    match = _ARXIV_NEW_ID_RE.match(input_str)
    if match:
        return match.group(1)
    match = _ARXIV_OLD_ID_RE.match(input_str)
    if match:
        return match.group(1)

    # Try to extract from URL
    match = _ARXIV_URL_RE.search(input_str)
    if match:
        return match.group(1) or match.group(2)

    # Return as-is (might be an OpenReview ID like "or_iEeiZlTbts")
    return input_str


def extract_github_repo(input_str: str) -> str:
    """Extract owner/repo from a GitHub URL or return the input if already in that format.

    Args:
        input_str: A GitHub URL or "owner/repo" string.

    Returns:
        The "owner/repo" string.

    Examples:
        >>> extract_github_repo("google-research/vision_transformer")
        'google-research/vision_transformer'
        >>> extract_github_repo("https://github.com/google-research/vision_transformer")
        'google-research/vision_transformer'
        >>> extract_github_repo("https://github.com/owner/repo/tree/main/src")
        'owner/repo'
    """
    input_str = input_str.strip()

    # Check if already owner/repo format
    if _GITHUB_REPO_RE.match(input_str):
        return input_str

    # Try to extract from URL
    match = _GITHUB_URL_RE.search(input_str)
    if match:
        repo = match.group(1)
        # Strip trailing .git
        if repo.endswith(".git"):
            repo = repo[:-4]
        return repo

    # Return as-is
    return input_str


def is_arxiv_url(input_str: str) -> bool:
    """Check if the input looks like an arXiv URL."""
    return "arxiv.org/" in input_str


def is_github_url(input_str: str) -> bool:
    """Check if the input looks like a GitHub URL."""
    return "github.com/" in input_str
