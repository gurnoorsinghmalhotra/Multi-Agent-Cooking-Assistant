"""Tests for POST /query — covers chef path, grocer path, and input validation."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.chef import ChefOutput
from app.schemas.grocer import GrocerOutput, GroceryItem
from app.schemas.response import QueryResponse

# --- Fixtures ---

CHEF_RESPONSE = QueryResponse(
    intent="chef_agent",
    data=ChefOutput(
        dish_name="Pav Bhaji",
        ingredients=["4 pav buns", "2 cups mixed vegetables", "2 tbsp butter"],
        steps=["Boil and mash vegetables.", "Cook with spices.", "Serve with buttered pav."],
        tips=["Use a heavy pan for best results."],
        video_links=[],
    ),
)

GROCER_RESPONSE = QueryResponse(
    intent="grocer_agent",
    data=GrocerOutput(
        items=[
            GroceryItem(name="pasta", price=1.49, store="Walmart"),
            GroceryItem(name="tomato", price=0.89, store="Walmart"),
        ],
        total_cost=2.38,
        store_breakdown={"Walmart": [
            GroceryItem(name="pasta", price=1.49, store="Walmart"),
            GroceryItem(name="tomato", price=0.89, store="Walmart"),
        ]},
    ),
)


# --- Helpers ---

def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- Tests ---

@pytest.mark.asyncio
async def test_chef_path_returns_recipe():
    with patch(
        "app.api.routes.handle_query",
        new_callable=AsyncMock,
        return_value=CHEF_RESPONSE,
    ):
        async with make_client() as client:
            response = await client.post("/query", json={"query": "I want to cook Pav Bhaji"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "chef_agent"
    assert body["data"]["dish_name"] == "Pav Bhaji"
    assert isinstance(body["data"]["steps"], list)
    assert body["data"]["video_links"] == []


@pytest.mark.asyncio
async def test_grocer_path_returns_cart():
    with patch(
        "app.api.routes.handle_query",
        new_callable=AsyncMock,
        return_value=GROCER_RESPONSE,
    ):
        async with make_client() as client:
            response = await client.post("/query", json={"query": "Get me ingredients for pasta"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "grocer_agent"
    assert body["data"]["total_cost"] == 2.38
    assert "Walmart" in body["data"]["store_breakdown"]


@pytest.mark.asyncio
async def test_empty_query_rejected():
    async with make_client() as client:
        response = await client.post("/query", json={"query": "   "})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_query_field_rejected():
    async with make_client() as client:
        response = await client.post("/query", json={})

    assert response.status_code == 422
