"""Grocer agent — builds a priced shopping cart from a classified intent."""

from typing import List

from pydantic import BaseModel

from app.prompts.grocer_prompt import GROCER_HUMAN_PROMPT, GROCER_SYSTEM_PROMPT
from app.schemas.grocer import GrocerOutput, GroceryItem
from app.schemas.intent import IntentOutput
from app.services.llm_client import invoke_structured
from app.services.pricing_service import fetch_prices


class _IngredientList(BaseModel):
    """Internal schema for extracting ingredients from the LLM when none were provided."""
    ingredients: List[str]


async def build_cart(intent: IntentOutput) -> GrocerOutput:
    """Build a priced grocery cart from a classified intent.

    Uses ingredients from the intent if available; otherwise calls the LLM
    once to extract them from the dish name. Then fetches prices concurrently
    and assembles the final cart in Python.

    Args:
        intent: Validated IntentOutput from the intent agent.

    Returns:
        GrocerOutput with items, total_cost, and store_breakdown.
    """
    ingredient_names = await _resolve_ingredients(intent)

    # I/O-bound: concurrent price lookups across all stores.
    items = await fetch_prices(ingredient_names)

    # Local logic: compute totals and group by store.
    total_cost = round(sum(item.price for item in items), 2)
    store_breakdown = _group_by_store(items)

    return GrocerOutput(items=items, total_cost=total_cost, store_breakdown=store_breakdown)


async def _resolve_ingredients(intent: IntentOutput) -> List[str]:
    """Return ingredients from intent if present, otherwise ask the LLM.

    The extra LLM call only happens when the user's query named a dish
    but didn't list any ingredients (e.g. "get me groceries for pasta").
    """
    if intent.ingredients:
        return intent.ingredients

    if intent.dish_name:
        result = await invoke_structured(
            system_prompt=GROCER_SYSTEM_PROMPT,
            human_prompt=GROCER_HUMAN_PROMPT,
            output_schema=_IngredientList,
            dish_name=intent.dish_name,
        )
        return result.ingredients

    return ["groceries"]  # last-resort fallback


def _group_by_store(items: list[GroceryItem]) -> dict[str, list[GroceryItem]]:
    """Group a flat list of GroceryItems by store name."""
    breakdown: dict[str, list[GroceryItem]] = {}
    for item in items:
        breakdown.setdefault(item.store, []).append(item)
    return breakdown
