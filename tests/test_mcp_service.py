"""Unit tests for the mock MCP / external food adapter."""

from __future__ import annotations

import pytest

from src.app.services.mcp_service import MCPService


@pytest.fixture
def service() -> MCPService:
    return MCPService()


class TestSearch:
    @pytest.mark.asyncio
    async def test_default_search_returns_results(self, service: MCPService) -> None:
        results = await service.search_restaurants(query="thai")
        assert len(results) >= 1
        # Each result has the canonical fields.
        for r in results:
            assert "name" in r
            assert "ingredients" in r
            assert "cuisine" in r

    @pytest.mark.asyncio
    async def test_cuisine_filter(self, service: MCPService) -> None:
        results = await service.search_restaurants(query="", cuisine="italian")
        assert len(results) >= 1
        assert all(r["cuisine"] == "italian" for r in results)

    @pytest.mark.asyncio
    async def test_price_range_filter(self, service: MCPService) -> None:
        results = await service.search_restaurants(query="", price_range="budget")
        assert len(results) >= 1
        assert all(r.get("price_range") == "budget" for r in results)

    @pytest.mark.asyncio
    async def test_limit_caps_results(self, service: MCPService) -> None:
        results = await service.search_restaurants(query="", limit=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_token_match_in_query(self, service: MCPService) -> None:
        results = await service.search_restaurants(query="vegan")
        assert len(results) >= 1
        # At least one returned dish should mention vegan in name or description.
        assert any(
            "vegan" in (r.get("name", "") + " " + r.get("description", "")).lower()
            for r in results
        )


class TestPlaceOrder:
    @pytest.mark.asyncio
    async def test_returns_provider_id_and_status(self, service: MCPService) -> None:
        resp = await service.place_order(
            {"user_id": "u-1", "dish_name": "Pad Thai", "restaurant": "X"}
        )
        assert resp["status"] == "pending_payment"
        assert resp["provider_order_id"]
        assert resp["provider"] == "mock"


class TestMenu:
    @pytest.mark.asyncio
    async def test_get_menu_for_known_restaurant(self, service: MCPService) -> None:
        menu = await service.get_menu_data("Bangkok Street Kitchen")
        assert menu
        assert menu["restaurant"] == "Bangkok Street Kitchen"
        assert "dishes" in menu
        assert len(menu["dishes"]) >= 1

    @pytest.mark.asyncio
    async def test_get_menu_for_unknown_returns_empty(self, service: MCPService) -> None:
        menu = await service.get_menu_data("Definitely Not A Restaurant")
        assert menu == {}
