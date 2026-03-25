"""HTTP client wrapper for the Code of Paper API.

Wraps httpx with:
- hishel disk cache (30-minute TTL)
- Configurable base URL, timeouts, retries
- Error → exit code mapping
- Defensive response parsing (.get() with defaults)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import hishel
import httpx
import platformdirs

from codeofpaper_cli import __version__
from codeofpaper_cli.exit_codes import CONNECTION_ERROR, GENERAL_ERROR, exit_code_from_status

# Cache storage in platform-appropriate directory
_CACHE_DIR = Path(platformdirs.user_cache_dir("codeofpaper")) / "http"

USER_AGENT = f"codeofpaper-cli/{__version__}"
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 1
CACHE_TTL = 1800  # 30 minutes


@dataclass
class APIError(Exception):
    """Raised when an API request fails."""

    status_code: int
    detail: str
    exit_code: int

    def __str__(self) -> str:
        return self.detail


@dataclass
class ConnectionError_(Exception):
    """Raised when the API is unreachable."""

    detail: str
    exit_code: int = field(default=CONNECTION_ERROR)

    def __str__(self) -> str:
        return self.detail


def _build_cache_transport(base_transport: httpx.HTTPTransport) -> hishel.CacheTransport:
    """Build a hishel disk cache transport wrapping the base transport."""
    storage = hishel.FileStorage(base_path=_CACHE_DIR, ttl=CACHE_TTL)
    controller = hishel.Controller(
        cacheable_methods=["GET"],
        cacheable_status_codes=[200],
        allow_heuristics=False,
        allow_stale=False,
    )
    return hishel.CacheTransport(
        transport=base_transport,
        storage=storage,
        controller=controller,
    )


class Client:
    """HTTP client for the Code of Paper API.

    Usage:
        client = Client(base_url="https://api.codeofpaper.com")
        data = client.get("/papers/search", params={"query": "transformers"})
        client.close()

    Or as a context manager:
        with Client() as client:
            data = client.get("/papers/search", params={"query": "transformers"})
    """

    def __init__(
        self,
        base_url: str = "https://api.codeofpaper.com",
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        use_cache: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        base_transport = httpx.HTTPTransport(retries=max_retries)

        transport = _build_cache_transport(base_transport) if use_cache else base_transport

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list:
        """Make a GET request and return the parsed JSON response.

        Raises:
            APIError: on 4xx/5xx responses
            ConnectionError_: on network/timeout errors
        """
        try:
            response = self._client.get(path, params=_clean_params(params))
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ConnectionError_(detail=f"Cannot reach API at {self.base_url}: {exc}")
        except httpx.HTTPError as exc:
            raise ConnectionError_(detail=f"HTTP error: {exc}")

        if response.status_code >= 400:
            detail = _extract_error_detail(response)
            raise APIError(
                status_code=response.status_code,
                detail=detail,
                exit_code=exit_code_from_status(response.status_code),
            )

        try:
            return response.json()
        except Exception:
            raise APIError(
                status_code=response.status_code,
                detail="Invalid JSON response from API",
                exit_code=GENERAL_ERROR,
            )

    # --- Convenience methods for specific endpoints ---

    def search_papers(
        self, query: str, limit: int = 10, offset: int = 0, sort_by: str = "relevant"
    ) -> dict[str, Any]:
        return self.get(
            "/papers/search",
            params={"query": query, "limit": limit, "offset": offset, "sort_by": sort_by},
        )

    def get_paper(self, paper_id: str) -> dict[str, Any]:
        return self.get(f"/papers/{paper_id}")

    def get_paper_repos(self, paper_id: str, limit: int = 10) -> dict[str, Any]:
        return self.get(f"/papers/{paper_id}/repos", params={"limit": limit})

    def get_similar(self, paper_id: str, limit: int = 6) -> dict[str, Any]:
        return self.get(f"/papers/{paper_id}/similar", params={"limit": limit})

    def get_random(self, quality: str = "high") -> dict[str, Any]:
        return self.get("/papers/random", params={"quality": quality})

    def suggest(self, query: str, limit: int = 6) -> list:
        return self.get("/papers/suggest", params={"q": query, "limit": limit})

    def get_trending(
        self,
        sort: str = "hot",
        has_code: bool = True,
        limit: int = 20,
        offset: int = 0,
        category: str | None = None,
        days: int | None = None,
    ) -> dict[str, Any]:
        return self.get(
            "/trending/",
            params={
                "sort": sort,
                "has_code": has_code,
                "limit": limit,
                "offset": offset,
                "category": category,
                "days": days,
            },
        )

    def get_categories(self) -> dict[str, Any]:
        return self.get("/categories/")

    def get_category(self, category_id: str) -> dict[str, Any]:
        return self.get(f"/categories/{category_id}")

    def get_conferences(self) -> list:
        return self.get("/conferences")

    def get_conference(self, conference_id: str) -> dict[str, Any]:
        return self.get(f"/conferences/{conference_id}")

    def get_conference_papers(
        self,
        conference_id: str,
        has_code: bool | None = None,
        track: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self.get(
            f"/papers/conference/{conference_id}",
            params={
                "has_code": has_code,
                "track": track,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_recent_code_drops(self, limit: int = 8, days: int = 30) -> list:
        return self.get(
            "/conferences/recent-code-drops", params={"limit": limit, "days": days}
        )

    def get_health(self) -> dict[str, Any]:
        return self.get("/health")

    def get_paper_health(self) -> dict[str, Any]:
        return self.get("/papers/health")


def _clean_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Remove None values from params dict so httpx doesn't send them."""
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}


def _extract_error_detail(response: httpx.Response) -> str:
    """Extract a human-readable error message from an API error response."""
    try:
        data = response.json()
        # FastAPI uses "detail" for HTTPException
        if isinstance(data, dict):
            return str(data.get("detail", data.get("message", f"HTTP {response.status_code}")))
        return str(data)
    except Exception:
        return f"HTTP {response.status_code}"
