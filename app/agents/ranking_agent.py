"""Ranking agent — scores and ranks stores by price + delivery time."""

from typing import List, Optional, Tuple

from pydantic import BaseModel

from app.agents.grocer_agent import _resolve_ingredients
from app.prompts.ranking_prompt import PREFERENCE_HUMAN_PROMPT, PREFERENCE_SYSTEM_PROMPT
from app.schemas.intent import IntentOutput
from app.schemas.ranking import StoreRank, StoreRankingOutput
from app.services.llm_client import invoke_structured
from app.services.pricing_service import _STORES, fetch_all_store_prices, get_store_delivery

_PRICE_KEYWORDS = {"cheap", "cheapest", "lowest", "budget", "affordable", "save", "inexpensive"}
_DELIVERY_KEYWORDS = {"fast", "fastest", "quick", "urgent", "now", "tonight", "asap", "immediately"}


class _PreferenceOutput(BaseModel):
    price_weight: float
    delivery_weight: float


def _get_preferences(query: str) -> Optional[Tuple[float, float]]:
    """Rule-based extraction of (price_weight, delivery_weight).

    Returns None when the query is ambiguous — caller falls back to LLM.
    """
    tokens = {t.strip(".,!?;:'\"") for t in query.lower().split()}
    has_price = bool(tokens & _PRICE_KEYWORDS)
    has_delivery = bool(tokens & _DELIVERY_KEYWORDS)

    if has_price and not has_delivery:
        return (0.8, 0.2)
    if has_delivery and not has_price:
        return (0.2, 0.8)
    if has_price and has_delivery:
        return (0.5, 0.5)  # conflicting signals — balanced
    return None  # ambiguous → LLM fallback

# Normalization helper: scales a list of values to [0, 1], where higher is better.
def _normalize(values: List[float]) -> List[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values) 
    return [(v - lo) / (hi - lo) for v in values]


async def rank_stores(intent: IntentOutput, query: str) -> StoreRankingOutput:
    """Rank all stores for the given ingredients using price + delivery scoring.

    Args:
        intent: Classified intent with optional ingredients/dish_name.
        query:  Raw user query string, used for preference extraction.

    Returns:
        StoreRankingOutput with stores sorted best-first and a best_store field.
    """
    # 1. Resolve ingredients (reuse grocer agent logic)
    ingredient_names: List[str] = await _resolve_ingredients(intent)

    # 2. Determine preference weights — rule-based first, one LLM call if ambiguous
    weights = _get_preferences(query)
    if weights is None:
        pref = await invoke_structured(
            system_prompt=PREFERENCE_SYSTEM_PROMPT,
            human_prompt=PREFERENCE_HUMAN_PROMPT,
            output_schema=_PreferenceOutput,
            query=query,
        )
        total = pref.price_weight + pref.delivery_weight or 1.0
        w_price = round(pref.price_weight / total, 4)
        w_delivery = round(pref.delivery_weight / total, 4)
    else:
        w_price, w_delivery = weights

    # 3. Fetch full price matrix concurrently
    store_price_map = await fetch_all_store_prices(ingredient_names)

    # 4. Compute per-store totals
    costs: List[float] = []
    times: List[int] = []
    store_items: List[List] = []

    for store in _STORES:
        raw = store_price_map[store]
        available = [item for item in raw if item is not None]
        subtotal = sum(item.price for item in available)
        delivery_time, delivery_fee = get_store_delivery(store)
        costs.append(round(subtotal + delivery_fee, 2))
        times.append(delivery_time)
        store_items.append(available)

    # 5. Normalize and invert (lower cost/time = higher score)
    price_scores = [1.0 - v for v in _normalize(costs)]
    delivery_scores = [1.0 - v for v in _normalize(times)]

    # 6. Compute composite scores, sort, return
    ranked: List[StoreRank] = []
    for i, store in enumerate(_STORES):
        score = round(w_price * price_scores[i] + w_delivery * delivery_scores[i], 4)
        ranked.append(StoreRank(
            name=store,
            total_cost=costs[i],
            delivery_time_mins=times[i],
            score=score,
            items=store_items[i],
        ))

    ranked.sort(key=lambda s: s.score, reverse=True)
    return StoreRankingOutput(stores=ranked, best_store=ranked[0].name, ingredients=ingredient_names)
