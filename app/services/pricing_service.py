"""Pricing service — mock concurrent store price lookups.

I/O-bound work (simulated network calls per store) lives here.
Local computation (picking cheapest, building fallbacks) is plain Python.
"""

import asyncio
import random
from typing import Optional

from app.schemas.grocer import GroceryItem

# Mock store catalogue: store → ingredient → base price (USD).
# In production these would be real HTTP calls to store APIs.
_STORE_PRICES: dict[str, dict[str, float]] = {
    "Walmart": {
        "chicken": 5.99, "pasta": 1.49, "tomato": 0.89, "garlic": 0.79,
        "onion": 0.59, "olive oil": 4.99, "butter": 3.49, "flour": 2.29,
        "eggs": 3.99, "milk": 2.79, "cheese": 4.49, "salt": 0.99,
        "pepper": 1.49, "basil": 1.99, "rice": 2.49, "potato": 1.29,
        "pav": 1.99, "bhaji": 0.99, "cumin": 1.29, "coriander": 0.99,
    },
    "Whole Foods": {
        "chicken": 8.99, "pasta": 2.99, "tomato": 1.49, "garlic": 1.29,
        "onion": 0.99, "olive oil": 8.99, "butter": 5.99, "flour": 3.99,
        "eggs": 6.49, "milk": 4.29, "cheese": 7.99, "salt": 1.99,
        "pepper": 2.99, "basil": 3.49, "rice": 4.99, "potato": 2.49,
        "pav": 3.49, "bhaji": 1.99, "cumin": 2.49, "coriander": 1.99,
    },
    "Trader Joe's": {
        "chicken": 6.99, "pasta": 1.99, "tomato": 1.09, "garlic": 0.99,
        "onion": 0.79, "olive oil": 5.99, "butter": 3.99, "flour": 2.79,
        "eggs": 4.49, "milk": 3.49, "cheese": 5.49, "salt": 1.29,
        "pepper": 1.99, "basil": 2.49, "rice": 3.49, "potato": 1.79,
        "pav": 2.49, "bhaji": 1.49, "cumin": 1.79, "coriander": 1.49,
    },
}

_STORES = list(_STORE_PRICES.keys())

# Mocked delivery data per store: fixed base time + flat fee.
_STORE_DELIVERY: dict[str, dict] = {
    "Walmart":      {"delivery_time_mins": 120, "delivery_fee": 0.00},
    "Whole Foods":  {"delivery_time_mins": 45,  "delivery_fee": 9.95},
    "Trader Joe's": {"delivery_time_mins": 240, "delivery_fee": 3.99},
}


def get_store_delivery(store: str) -> tuple[int, float]:
    """Return (delivery_time_mins, delivery_fee) for a store."""
    info = _STORE_DELIVERY[store]
    return info["delivery_time_mins"], info["delivery_fee"]


# --- I/O-bound: simulates a network request to a single store ---

async def _fetch_from_store(ingredient: str, store: str) -> Optional[GroceryItem]:
    """Look up one ingredient at one store. Simulates network latency."""
    await asyncio.sleep(random.uniform(0.05, 0.15))  # mock I/O wait

    normalized = ingredient.lower().strip()
    for key, price in _STORE_PRICES[store].items():
        if key in normalized or normalized in key:
            return GroceryItem(name=ingredient, price=price, store=store)

    return None  # ingredient not stocked at this store

# --- Entry point called by grocer_agent ---

async def fetch_prices(ingredients: list[str]) -> list[GroceryItem]:
    """Fetch the cheapest available price for each ingredient across all stores.

    All (ingredient x store) lookups run concurrently via asyncio.gather.
    After they complete, cheapest-store selection is plain synchronous logic.

    Args:
        ingredients: List of ingredient name strings.

    Returns:
        One GroceryItem per ingredient, sourced from the cheapest store found.
        Falls back to a $2.99 placeholder if the ingredient isn't in any store.
    """
    n_stores = len(_STORES)

    # I/O-bound: fire all lookups at once instead of waiting for each in sequence.
    tasks = [
        _fetch_from_store(ingredient, store)
        for ingredient in ingredients
        for store in _STORES
    ]
    all_results = await asyncio.gather(*tasks)

    # Local logic: group results back per ingredient, pick cheapest.
    best_items: list[GroceryItem] = []
    for i, ingredient in enumerate(ingredients):
        store_results = all_results[i * n_stores : (i + 1) * n_stores]
        found = [r for r in store_results if r is not None]

        if found:
            best_items.append(min(found, key=lambda item: item.price))
        else:
            best_items.append(GroceryItem(name=ingredient, price=2.99, store="Generic Store"))

    return best_items # example output: [GroceryItem(name='chicken', price=5.99, store='Walmart'), GroceryItem(name='pasta', price=1.49, store='Walmart'), ...]


async def fetch_all_store_prices(
    ingredients: list[str],
) -> dict[str, list[Optional[GroceryItem]]]:
    """Return the full price matrix: store → list of items (None if not stocked).

    Reuses _fetch_from_store concurrently — same pattern as fetch_prices but
    organised by store instead of picking cheapest.
    """
    n_stores = len(_STORES)
    tasks = [
        _fetch_from_store(ingredient, store)
        for ingredient in ingredients
        for store in _STORES
    ]
    all_results = await asyncio.gather(*tasks)

    store_map: dict[str, list[Optional[GroceryItem]]] = {s: [] for s in _STORES}
    for i, ingredient in enumerate(ingredients):
        store_results = all_results[i * n_stores : (i + 1) * n_stores]
        for j, store in enumerate(_STORES):
            store_map[store].append(store_results[j])
    return store_map
