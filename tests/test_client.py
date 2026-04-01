"""Tests for the HTTP client."""

import json
import ssl

import httpx
import pytest

from codeofpaper_cli.client import APIError, Client, ConnectionError_, _clean_params, _extract_error_detail
from codeofpaper_cli.exit_codes import AUTH_ERROR, CONNECTION_ERROR, GENERAL_ERROR, NOT_FOUND, RATE_LIMITED


class TestCleanParams:
    def test_removes_none_values(self):
        assert _clean_params({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}

    def test_returns_none_for_none_input(self):
        assert _clean_params(None) is None

    def test_empty_dict(self):
        assert _clean_params({}) == {}

    def test_all_none_values(self):
        assert _clean_params({"a": None, "b": None}) == {}

    def test_keeps_falsy_non_none(self):
        assert _clean_params({"a": 0, "b": False, "c": ""}) == {"a": 0, "b": False, "c": ""}


class TestExtractErrorDetail:
    def test_fastapi_detail(self):
        response = httpx.Response(404, json={"detail": "Paper not found"})
        assert _extract_error_detail(response) == "Paper not found"

    def test_message_field(self):
        response = httpx.Response(500, json={"message": "Internal error"})
        assert _extract_error_detail(response) == "Internal error"

    def test_fallback_to_status_code(self):
        response = httpx.Response(503, json={"something": "else"})
        assert _extract_error_detail(response) == "HTTP 503"

    def test_non_json_response(self):
        response = httpx.Response(502, text="Bad Gateway")
        assert _extract_error_detail(response) == "HTTP 502"

    def test_non_dict_json(self):
        response = httpx.Response(400, json="just a string")
        assert _extract_error_detail(response) == "just a string"


class TestClient:
    """Tests using httpx mock transport."""

    def _make_client(self, handler, **kwargs):
        """Create a client with a mock transport for testing."""
        transport = httpx.MockTransport(handler)
        client = Client.__new__(Client)
        client.base_url = kwargs.get("base_url", "https://api.codeofpaper.com")
        client.api_key = kwargs.get("api_key", None)
        client._client = httpx.Client(
            base_url=client.base_url,
            transport=transport,
            headers={"Accept": "application/json"},
        )
        return client

    def test_get_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"})

        client = self._make_client(handler)
        result = client.get("/health")
        assert result == {"status": "ok"}
        client.close()

    def test_get_returns_list(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[{"id": "1"}, {"id": "2"}])

        client = self._make_client(handler)
        result = client.get("/conferences")
        assert isinstance(result, list)
        assert len(result) == 2
        client.close()

    def test_get_404_raises_api_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "Paper not found"})

        client = self._make_client(handler)
        with pytest.raises(APIError) as exc_info:
            client.get("/papers/9999.99999")
        assert exc_info.value.status_code == 404
        assert exc_info.value.exit_code == NOT_FOUND
        assert "not found" in str(exc_info.value).lower()
        client.close()

    def test_get_429_raises_rate_limited(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"detail": "Rate limit exceeded"})

        client = self._make_client(handler)
        with pytest.raises(APIError) as exc_info:
            client.get("/papers/search")
        assert exc_info.value.exit_code == RATE_LIMITED
        client.close()

    def test_get_401_raises_auth_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "Not authenticated"})

        client = self._make_client(handler)
        with pytest.raises(APIError) as exc_info:
            client.get("/papers/search")
        assert exc_info.value.exit_code == AUTH_ERROR
        client.close()

    def test_get_500_raises_general_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "Internal error"})

        client = self._make_client(handler)
        with pytest.raises(APIError) as exc_info:
            client.get("/papers/search")
        assert exc_info.value.exit_code == GENERAL_ERROR
        client.close()

    def test_connection_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client = self._make_client(handler)
        with pytest.raises(ConnectionError_) as exc_info:
            client.get("/health")
        assert exc_info.value.exit_code == CONNECTION_ERROR
        client.close()

    def test_timeout_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Read timed out")

        client = self._make_client(handler)
        with pytest.raises(ConnectionError_) as exc_info:
            client.get("/health")
        assert exc_info.value.exit_code == CONNECTION_ERROR
        client.close()

    def test_invalid_json_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not json", headers={"content-type": "text/plain"})

        client = self._make_client(handler)
        with pytest.raises(APIError) as exc_info:
            client.get("/health")
        assert "Invalid JSON" in str(exc_info.value)
        client.close()

    def test_params_sent_correctly(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["query"] == "transformers"
            assert request.url.params["limit"] == "10"
            assert "offset" not in request.url.params  # None values stripped
            return httpx.Response(200, json={"query": "transformers", "count": 0, "papers": []})

        client = self._make_client(handler)
        result = client.get("/papers/search", params={"query": "transformers", "limit": 10, "offset": None})
        assert result["query"] == "transformers"
        client.close()

    def test_context_manager(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"})

        client = self._make_client(handler)
        with client as c:
            result = c.get("/health")
        assert result == {"status": "ok"}


class TestConvenienceMethods:
    """Test that convenience methods call the right endpoints with right params."""

    def _tracking_client(self):
        """Create a client that records request details."""
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append({"path": request.url.path, "params": dict(request.url.params)})
            return httpx.Response(200, json={})

        client = Client.__new__(Client)
        client.base_url = "https://api.codeofpaper.com"
        client.api_key = None
        client._client = httpx.Client(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
            headers={"Accept": "application/json"},
        )
        return client, calls

    def test_search_papers(self):
        client, calls = self._tracking_client()
        client.search_papers("transformers", limit=5, sort_by="recent")
        assert calls[0]["path"] == "/papers/search"
        assert calls[0]["params"]["query"] == "transformers"
        assert calls[0]["params"]["sort_by"] == "recent"
        assert calls[0]["params"]["limit"] == "5"
        client.close()

    def test_get_paper(self):
        client, calls = self._tracking_client()
        client.get_paper("2010.11929")
        assert calls[0]["path"] == "/papers/2010.11929"
        client.close()

    def test_get_paper_repos(self):
        client, calls = self._tracking_client()
        client.get_paper_repos("2010.11929", limit=5)
        assert calls[0]["path"] == "/papers/2010.11929/repos"
        assert calls[0]["params"]["limit"] == "5"
        client.close()

    def test_get_similar(self):
        client, calls = self._tracking_client()
        client.get_similar("2010.11929", limit=3)
        assert calls[0]["path"] == "/papers/2010.11929/similar"
        assert calls[0]["params"]["limit"] == "3"
        client.close()

    def test_get_random(self):
        client, calls = self._tracking_client()
        client.get_random(quality="medium")
        assert calls[0]["path"] == "/papers/random"
        assert calls[0]["params"]["quality"] == "medium"
        client.close()

    def test_suggest(self):
        client, calls = self._tracking_client()
        client.suggest("attention", limit=4)
        assert calls[0]["path"] == "/papers/suggest"
        assert calls[0]["params"]["q"] == "attention"
        client.close()

    def test_get_trending(self):
        client, calls = self._tracking_client()
        client.get_trending(sort="top", has_code=True, category="cs.CV", days=30)
        assert calls[0]["path"] == "/trending/"
        assert calls[0]["params"]["sort"] == "top"
        assert calls[0]["params"]["category"] == "cs.CV"
        assert calls[0]["params"]["days"] == "30"
        client.close()

    def test_get_trending_none_params_stripped(self):
        client, calls = self._tracking_client()
        client.get_trending()
        assert "category" not in calls[0]["params"]
        assert "days" not in calls[0]["params"]
        client.close()

    def test_get_categories(self):
        client, calls = self._tracking_client()
        client.get_categories()
        assert calls[0]["path"] == "/categories/"
        client.close()

    def test_get_category(self):
        client, calls = self._tracking_client()
        client.get_category("cv_classification")
        assert calls[0]["path"] == "/categories/cv_classification"
        client.close()

    def test_get_conferences(self):
        client, calls = self._tracking_client()
        client.get_conferences()
        assert calls[0]["path"] == "/conferences"
        client.close()

    def test_get_conference(self):
        client, calls = self._tracking_client()
        client.get_conference("neurips_2024")
        assert calls[0]["path"] == "/conferences/neurips_2024"
        client.close()

    def test_get_conference_papers(self):
        client, calls = self._tracking_client()
        client.get_conference_papers("neurips_2024", has_code=True, track="oral")
        assert calls[0]["path"] == "/papers/conference/neurips_2024"
        assert calls[0]["params"]["has_code"] == "true"
        assert calls[0]["params"]["track"] == "oral"
        client.close()

    def test_get_recent_code_drops(self):
        client, calls = self._tracking_client()
        client.get_recent_code_drops(limit=5, days=14)
        assert calls[0]["path"] == "/conferences/recent-code-drops"
        assert calls[0]["params"]["limit"] == "5"
        assert calls[0]["params"]["days"] == "14"
        client.close()

    def test_get_health(self):
        client, calls = self._tracking_client()
        client.get_health()
        assert calls[0]["path"] == "/health"
        client.close()


class TestCABundle:
    """Tests for custom CA bundle (TLS certificate) support."""

    def test_default_verify_is_true(self):
        """Without ca_bundle, httpx.Client should use default verification."""
        client = Client(use_cache=False)
        # httpx stores verify as an ssl.SSLContext; default is truthy
        assert client._client._transport._pool._ssl_context is not None
        client.close()

    def test_ca_bundle_creates_ssl_context(self, tmp_path):
        """When ca_bundle is set, Client should build an ssl.SSLContext from it."""
        # Use a real (self-signed) cert generated in-memory via Python stdlib
        import certifi

        # Use certifi's real CA bundle as a valid PEM file for testing
        ca_file = certifi.where()
        client = Client(ca_bundle=ca_file, use_cache=False)
        ctx = client._client._transport._pool._ssl_context
        assert isinstance(ctx, ssl.SSLContext)
        client.close()

    def test_ca_bundle_none_uses_default(self):
        """Explicitly passing None should behave like no ca_bundle."""
        client = Client(ca_bundle=None, use_cache=False)
        client.close()

    def test_ca_bundle_invalid_path_raises(self):
        """A non-existent CA bundle path should raise an error at Client creation."""
        with pytest.raises(OSError):
            Client(ca_bundle="/nonexistent/path/ca.pem", use_cache=False)
