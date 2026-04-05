"""Grocer agent schema.

Defines the structured output returned by the Grocer Agent after
fetching prices and assembling a shopping cart.
"""

from typing import Dict, List

from pydantic import BaseModel


class GroceryItem(BaseModel):
    """A single ingredient with its price and source store."""

    name: str
    price: float
    store: str


class GrocerOutput(BaseModel):
    """Full shopping cart response from the Grocer Agent."""

    # One item per ingredient, always sourced from the cheapest store found.
    items: List[GroceryItem]

    # Sum of all item prices, rounded to 2 decimal places.
    total_cost: float

    # Items grouped by store name — computed in Python, not by the LLM.
    store_breakdown: Dict[str, List[GroceryItem]]
