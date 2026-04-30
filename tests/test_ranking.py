"""Tests for the store ranking agent — unit, service, integration, and LLM-call-count coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.grocer import GroceryItem
from app.schemas.ranking import StoreRank, StoreRankingOutput
from app.schemas.response import QueryResponse

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Two common ingredients with known prices at every store
_INGREDIENTS = ["chicken", "pasta"]

# Full price matrix that mirrors the real mock catalogue
_MOCK_STORE_PRICES = {
    "Walmart": [
        GroceryItem(name="chicken", price=5.99, store="Walmart"),
        GroceryItem(name="pasta",   price=1.49, store="Walmart"),
    ],
    "Whole Foods": [
        GroceryItem(name="chicken", price=8.99, store="Whole Foods"),
        GroceryItem(name="pasta",   price=2.99, store="Whole Foods"),
    ],
    "Trader Joe's": [
        GroceryItem(name="chicken", price=6.99, store="Trader Joe's"),
        GroceryItem(name="pasta",   price=1.99, store="Trader Joe's"),
    ],
}

# Expected totals (subtotal + delivery fee):
#   Walmart      5.99+1.49+0.00  = 7.48   |  120 min
#   Whole Foods  8.99+2.99+9.95  = 21.93  |   45 min
#   Trader Joe's 6.99+1.99+3.99  = 12.97  |  240 min

RANKING_RESPONSE = QueryResponse(
    intent="ranking_agent",
    data=StoreRankingOutput(
        stores=[
            StoreRank(name="Walmart",      total_cost=7.48,  delivery_time_mins=120, score=0.923),
            StoreRank(name="Trader Joe's", total_cost=12.97, delivery_time_mins=240, score=0.496),
            StoreRank(name="Whole Foods",  total_cost=21.93, delivery_time_mins=45,  score=0.200),
        ],
        best_store="Walmart",
    ),
)


def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. Unit — _get_preferences (rule-based keyword extraction)
# ---------------------------------------------------------------------------

def test_get_preferences_single_price_keyword():
    from app.agents.ranking_agent import _get_preferences
    assert _get_preferences("which store is cheapest for pasta") == (0.8, 0.2)


def test_get_preferences_single_delivery_keyword():
    from app.agents.ranking_agent import _get_preferences
    assert _get_preferences("I need pasta ingredients fast") == (0.2, 0.8)


def test_get_preferences_budget_keyword():
    from app.agents.ranking_agent import _get_preferences
    assert _get_preferences("budget option for groceries") == (0.8, 0.2)


def test_get_preferences_urgent_keyword():
    from app.agents.ranking_agent import _get_preferences
    assert _get_preferences("I need this tonight, which store?") == (0.2, 0.8)


def test_get_preferences_conflicting_keywords_returns_balanced():
    from app.agents.ranking_agent import _get_preferences
    # Both price AND delivery signals → balanced
    assert _get_preferences("cheapest and fastest store") == (0.5, 0.5)


def test_get_preferences_ambiguous_returns_none():
    from app.agents.ranking_agent import _get_preferences
    # No keywords → caller must fall back to LLM
    assert _get_preferences("which store should I use for lasagna?") is None


def test_get_preferences_empty_string_returns_none():
    from app.agents.ranking_agent import _get_preferences
    assert _get_preferences("") is None


# ---------------------------------------------------------------------------
# 2. Unit — _normalize (min-max normalization)
# ---------------------------------------------------------------------------

def test_normalize_standard_values():
    from app.agents.ranking_agent import _normalize
    result = _normalize([0.0, 5.0, 10.0])
    assert result == [0.0, 0.5, 1.0]


def test_normalize_uniform_values_returns_half():
    from app.agents.ranking_agent import _normalize
    result = _normalize([7.0, 7.0, 7.0])
    assert result == [0.5, 0.5, 0.5]


def test_normalize_two_values():
    from app.agents.ranking_agent import _normalize
    result = _normalize([2.0, 8.0])
    assert result == [0.0, 1.0]


def test_normalize_single_value():
    from app.agents.ranking_agent import _normalize
    result = _normalize([42.0])
    assert result == [0.5]


# ---------------------------------------------------------------------------
# 3. Unit — get_store_delivery (pricing service)
# ---------------------------------------------------------------------------

def test_get_store_delivery_walmart():
    from app.services.pricing_service import get_store_delivery
    time, fee = get_store_delivery("Walmart")
    assert time == 120
    assert fee == 0.0


def test_get_store_delivery_whole_foods():
    from app.services.pricing_service import get_store_delivery
    time, fee = get_store_delivery("Whole Foods")
    assert time == 45
    assert fee == 9.95


def test_get_store_delivery_trader_joes():
    from app.services.pricing_service import get_store_delivery
    time, fee = get_store_delivery("Trader Joe's")
    assert time == 240
    assert fee == 3.99


# ---------------------------------------------------------------------------
# 4. Async unit — fetch_all_store_prices (pricing service)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_all_store_prices_returns_all_stores():
    from app.services.pricing_service import _STORES, fetch_all_store_prices
    result = await fetch_all_store_prices(["chicken"])
    assert set(result.keys()) == set(_STORES)


@pytest.mark.asyncio
async def test_fetch_all_store_prices_known_ingredient_found_at_all_stores():
    from app.services.pricing_service import fetch_all_store_prices
    result = await fetch_all_store_prices(["chicken"])
    for store, items in result.items():
        assert len(items) == 1
        assert items[0] is not None, f"chicken should be stocked at {store}"
        assert items[0].price > 0


@pytest.mark.asyncio
async def test_fetch_all_store_prices_unknown_ingredient_returns_none():
    from app.services.pricing_service import fetch_all_store_prices
    result = await fetch_all_store_prices(["unobtainium"])
    for store, items in result.items():
        assert items[0] is None, f"unobtainium should not be stocked at {store}"


@pytest.mark.asyncio
async def test_fetch_all_store_prices_list_length_matches_ingredients():
    from app.services.pricing_service import fetch_all_store_prices
    ingredients = ["chicken", "pasta", "tomato"]
    result = await fetch_all_store_prices(ingredients)
    for store, items in result.items():
        assert len(items) == len(ingredients)


# ---------------------------------------------------------------------------
# 5. Async unit — rank_stores scoring correctness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rank_stores_budget_preference_walmart_wins():
    """Price-heavy weighting (0.8/0.2) — Walmart (cheapest, free delivery) should rank first."""
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS):
        result = await rank_stores(intent, "cheapest store for chicken and pasta")

    assert result.best_store == "Walmart"
    assert result.stores[0].name == "Walmart"


@pytest.mark.asyncio
async def test_rank_stores_fast_preference_whole_foods_wins():
    """Delivery-heavy weighting (0.2/0.8) — Whole Foods (45 min express) should rank first."""
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS):
        result = await rank_stores(intent, "I need chicken and pasta fast tonight")

    assert result.best_store == "Whole Foods"
    assert result.stores[0].name == "Whole Foods"


@pytest.mark.asyncio
async def test_rank_stores_scores_are_sorted_descending():
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS):
        result = await rank_stores(intent, "cheapest store")

    scores = [s.score for s in result.stores]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_rank_stores_returns_all_three_stores():
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS):
        result = await rank_stores(intent, "cheapest store")

    assert len(result.stores) == 3
    store_names = {s.name for s in result.stores}
    assert store_names == {"Walmart", "Whole Foods", "Trader Joe's"}


@pytest.mark.asyncio
async def test_rank_stores_best_store_matches_first_entry():
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS):
        result = await rank_stores(intent, "cheapest store")

    assert result.best_store == result.stores[0].name


@pytest.mark.asyncio
async def test_rank_stores_total_cost_includes_delivery_fee():
    """Whole Foods has a $9.95 delivery fee — verify it's included in total_cost."""
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS):
        result = await rank_stores(intent, "cheapest store")

    wf = next(s for s in result.stores if s.name == "Whole Foods")
    # 8.99 + 2.99 + 9.95 delivery fee = 21.93
    assert abs(wf.total_cost - 21.93) < 0.01


@pytest.mark.asyncio
async def test_rank_stores_walmart_has_zero_delivery_fee():
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS):
        result = await rank_stores(intent, "cheapest store")

    walmart = next(s for s in result.stores if s.name == "Walmart")
    # 5.99 + 1.49 + 0.00 fee = 7.48
    assert abs(walmart.total_cost - 7.48) < 0.01


# ---------------------------------------------------------------------------
# 6. LLM call-count tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_llm_call_when_price_keyword_present():
    """Rule-based match → invoke_structured should NOT be called for preferences."""
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS), \
         patch("app.agents.ranking_agent.invoke_structured", new_callable=AsyncMock) as mock_llm:
        await rank_stores(intent, "cheapest store for pasta")

    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_no_llm_call_when_delivery_keyword_present():
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS), \
         patch("app.agents.ranking_agent.invoke_structured", new_callable=AsyncMock) as mock_llm:
        await rank_stores(intent, "I need this fast")

    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_llm_called_once_when_query_is_ambiguous():
    """Ambiguous query → exactly one invoke_structured call for preference extraction."""
    from app.agents.ranking_agent import rank_stores
    from app.schemas.intent import IntentOutput
    from app.agents.ranking_agent import _PreferenceOutput

    intent = IntentOutput(intent="ranking_agent", ingredients=_INGREDIENTS)
    mock_pref = _PreferenceOutput(price_weight=0.5, delivery_weight=0.5)

    with patch("app.agents.ranking_agent.fetch_all_store_prices", new_callable=AsyncMock, return_value=_MOCK_STORE_PRICES), \
         patch("app.agents.ranking_agent._resolve_ingredients", new_callable=AsyncMock, return_value=_INGREDIENTS), \
         patch("app.agents.ranking_agent.invoke_structured", new_callable=AsyncMock, return_value=mock_pref) as mock_llm:
        await rank_stores(intent, "best store for lasagna ingredients")

    assert mock_llm.call_count == 1


# ---------------------------------------------------------------------------
# 7. Integration — route-level tests (mock handle_query)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ranking_path_returns_200():
    with patch("app.api.routes.handle_query", new_callable=AsyncMock, return_value=RANKING_RESPONSE):
        async with make_client() as client:
            response = await client.post("/query", json={"query": "Which store is cheapest for pasta?"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ranking_path_intent_label():
    with patch("app.api.routes.handle_query", new_callable=AsyncMock, return_value=RANKING_RESPONSE):
        async with make_client() as client:
            response = await client.post("/query", json={"query": "Which store is cheapest for pasta?"})
    assert response.json()["intent"] == "ranking_agent"


@pytest.mark.asyncio
async def test_ranking_response_contains_stores_list():
    with patch("app.api.routes.handle_query", new_callable=AsyncMock, return_value=RANKING_RESPONSE):
        async with make_client() as client:
            response = await client.post("/query", json={"query": "Which store is cheapest for pasta?"})
    data = response.json()["data"]
    assert isinstance(data["stores"], list)
    assert len(data["stores"]) == 3


@pytest.mark.asyncio
async def test_ranking_response_stores_have_required_fields():
    with patch("app.api.routes.handle_query", new_callable=AsyncMock, return_value=RANKING_RESPONSE):
        async with make_client() as client:
            response = await client.post("/query", json={"query": "Which store is cheapest for pasta?"})
    for store in response.json()["data"]["stores"]:
        assert "name" in store
        assert "total_cost" in store
        assert "delivery_time_mins" in store
        assert "score" in store


@pytest.mark.asyncio
async def test_ranking_response_scores_are_sorted_descending():
    with patch("app.api.routes.handle_query", new_callable=AsyncMock, return_value=RANKING_RESPONSE):
        async with make_client() as client:
            response = await client.post("/query", json={"query": "Which store is cheapest for pasta?"})
    scores = [s["score"] for s in response.json()["data"]["stores"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_ranking_response_best_store_matches_first_entry():
    with patch("app.api.routes.handle_query", new_callable=AsyncMock, return_value=RANKING_RESPONSE):
        async with make_client() as client:
            response = await client.post("/query", json={"query": "Which store is cheapest for pasta?"})
    data = response.json()["data"]
    assert data["best_store"] == data["stores"][0]["name"]


@pytest.mark.asyncio
async def test_ranking_scores_are_between_zero_and_one():
    with patch("app.api.routes.handle_query", new_callable=AsyncMock, return_value=RANKING_RESPONSE):
        async with make_client() as client:
            response = await client.post("/query", json={"query": "Which store is cheapest for pasta?"})
    for store in response.json()["data"]["stores"]:
        assert 0.0 <= store["score"] <= 1.0
