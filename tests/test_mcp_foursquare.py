"""Unit tests for the Foursquare MCP provider.

We mock aiohttp so these run without network and without burning the
free-tier quota. The goal is to lock in the request shape (auth header,
category filter, price-tier mapping) and the response normalization
(canonical fields the food agent depends on).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.services.mcp_providers import foursquare


# ----------------------------------------------------------- helpers


class _FakeResponse:
    """Minimal stand-in for aiohttp.ClientResponse."""

    def __init__(self, *, status: int = 200, payload: Any = None, text: str = ""):
        self.status = status
        self._payload = payload
        self._text = text

    async def json(self) -> Any:
        return self._payload

    async def text(self) -> str:
        return self._text or str(self._payload)

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


class _FakeSession:
    """Stands in for aiohttp.ClientSession; records the last call."""

    def __init__(self, response: _FakeResponse):
        self._response = response
        self.last_url: str | None = None
        self.last_params: dict | None = None
        self.last_headers: dict | None = None

    def get(self, url: str, params: dict | None = None, headers: dict | None = None):
        self.last_url = url
        self.last_params = params
        self.last_headers = headers
        return self._response

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


def _patch_session(session: _FakeSession):
    """Patch aiohttp.ClientSession in the foursquare module."""
    return patch.object(
        foursquare.aiohttp,
        "ClientSession",
        return_value=session,
    )


# ----------------------------------------------------------- tests


class TestSearchRequest:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "")
        results = await foursquare.search_restaurants(query="thai")
        assert results == []

    @pytest.mark.asyncio
    async def test_request_uses_bearer_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "fsq3-test-key")
        session = _FakeSession(_FakeResponse(payload={"results": []}))
        with _patch_session(session):
            await foursquare.search_restaurants(query="thai", near="Lagos")
        assert session.last_headers is not None
        assert session.last_headers["Authorization"] == "Bearer fsq3-test-key"

    @pytest.mark.asyncio
    async def test_query_combines_user_input_with_cuisine_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "k")
        session = _FakeSession(_FakeResponse(payload={"results": []}))
        with _patch_session(session):
            await foursquare.search_restaurants(query="dinner", cuisine="thai")
        assert "dinner" in session.last_params["query"]
        assert "thai" in session.last_params["query"]

    @pytest.mark.asyncio
    async def test_dining_category_filter_applied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "k")
        session = _FakeSession(_FakeResponse(payload={"results": []}))
        with _patch_session(session):
            await foursquare.search_restaurants(query="x")
        assert session.last_params["categories"] == "13000"

    @pytest.mark.asyncio
    async def test_price_range_maps_to_tier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "k")
        session = _FakeSession(_FakeResponse(payload={"results": []}))
        with _patch_session(session):
            await foursquare.search_restaurants(query="x", price_range="premium")
        assert session.last_params["min_price"] == 3
        assert session.last_params["max_price"] == 3

    @pytest.mark.asyncio
    async def test_ll_takes_precedence_over_near(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "k")
        session = _FakeSession(_FakeResponse(payload={"results": []}))
        with _patch_session(session):
            await foursquare.search_restaurants(
                query="x", near="Tokyo", ll="35.6762,139.6503"
            )
        assert session.last_params.get("ll") == "35.6762,139.6503"
        assert "near" not in session.last_params

    @pytest.mark.asyncio
    async def test_limit_is_capped_at_50(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "k")
        session = _FakeSession(_FakeResponse(payload={"results": []}))
        with _patch_session(session):
            await foursquare.search_restaurants(query="x", limit=999)
        assert session.last_params["limit"] == 50


class TestSearchResponseNormalization:
    @pytest.mark.asyncio
    async def test_normalizes_to_canonical_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "k")
        payload = {
            "results": [
                {
                    "fsq_id": "abc123",
                    "name": "Bangkok Express",
                    "categories": [{"id": 13294, "name": "Thai Restaurant"}],
                    "location": {
                        "formatted_address": "1 Test St, Lagos",
                        "latitude": 6.5,
                        "longitude": 3.4,
                    },
                    "price": 2,
                    "rating": 8.7,
                }
            ]
        }
        session = _FakeSession(_FakeResponse(payload=payload))
        with _patch_session(session):
            results = await foursquare.search_restaurants(query="thai")

        assert len(results) == 1
        item = results[0]
        # Canonical fields downstream code expects:
        assert item["name"] == "Bangkok Express"
        assert item["restaurant"] == "Bangkok Express"
        assert "thai" in item["cuisine"].lower()
        assert item["ingredients"] == []
        assert item["price_range"] == "mid-range"
        assert item["estimated_price"] == 22.0
        # Provider extras passed through:
        assert item["fsq_id"] == "abc123"
        assert item["address"].startswith("1 Test St")
        assert item["rating"] == 8.7

    @pytest.mark.asyncio
    async def test_missing_optional_fields_handled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Foursquare can omit price / rating / categories — must not crash."""
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "k")
        payload = {"results": [{"fsq_id": "x", "name": "Mystery Place"}]}
        session = _FakeSession(_FakeResponse(payload=payload))
        with _patch_session(session):
            results = await foursquare.search_restaurants(query="x")
        assert results[0]["name"] == "Mystery Place"
        # No price → price_range should be None.
        assert results[0]["price_range"] is None

    @pytest.mark.asyncio
    async def test_non_200_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "k")
        session = _FakeSession(_FakeResponse(status=403, text="forbidden"))
        with _patch_session(session):
            results = await foursquare.search_restaurants(query="x")
        assert results == []

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(foursquare.settings, "FOURSQUARE_API_KEY", "k")

        class _BrokenSession:
            def get(self, *a, **kw):
                raise RuntimeError("DNS exploded")

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

        with patch.object(
            foursquare.aiohttp, "ClientSession", return_value=_BrokenSession()
        ):
            results = await foursquare.search_restaurants(query="x")
        assert results == []


class TestPlaceOrder:
    @pytest.mark.asyncio
    async def test_returns_synthetic_provider_id(self) -> None:
        resp = await foursquare.place_order(
            {"user_id": "u-1", "dish_name": "X", "restaurant": "Y"}
        )
        assert resp["provider"] == "foursquare"
        assert resp["provider_order_id"].startswith("fsq-mock-")
        assert resp["status"] == "pending_payment"
        # Note flagging that real ordering isn't a Foursquare capability.
        assert "discovery" in resp["note"].lower()


class TestSettingsValidation:
    def test_foursquare_provider_without_key_refuses_boot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.app.core.config import Settings

        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("MCP_PROVIDER", "foursquare")
        monkeypatch.delenv("FOURSQUARE_API_KEY", raising=False)

        with pytest.raises(Exception) as exc:
            Settings()
        assert "FOURSQUARE_API_KEY" in str(exc.value)

    def test_unknown_provider_refused_at_boot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.app.core.config import Settings

        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("MCP_PROVIDER", "yelp")

        with pytest.raises(Exception) as exc:
            Settings()
        assert "MCP_PROVIDER" in str(exc.value)
        assert "yelp" in str(exc.value)


class TestServiceDispatch:
    """Confirm MCPService dispatches to the right provider module."""

    @pytest.mark.asyncio
    async def test_dispatch_to_foursquare_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.app.services import mcp_service as svc_mod

        monkeypatch.setattr(svc_mod.settings, "MCP_PROVIDER", "foursquare")
        called = AsyncMock(return_value=[{"name": "fsq result"}])
        monkeypatch.setattr(
            svc_mod.foursquare_provider, "search_restaurants", called
        )

        results = await svc_mod.mcp_service.search_restaurants(query="thai")
        called.assert_awaited_once()
        assert results == [{"name": "fsq result"}]

    @pytest.mark.asyncio
    async def test_dispatch_to_mock_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.app.services import mcp_service as svc_mod

        monkeypatch.setattr(svc_mod.settings, "MCP_PROVIDER", "mock")
        results = await svc_mod.mcp_service.search_restaurants(query="thai")
        # Mock catalog has Thai dishes.
        assert any("thai" in r.get("cuisine", "") for r in results)
