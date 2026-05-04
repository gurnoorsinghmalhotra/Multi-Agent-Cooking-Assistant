"""Ranking agent output schemas."""

from typing import List

from pydantic import BaseModel

from app.schemas.grocer import GroceryItem


class StoreRank(BaseModel):
    name: str
    total_cost: float
    delivery_time_mins: int
    score: float
    items: List[GroceryItem]


class StoreRankingOutput(BaseModel):
    stores: List[StoreRank]
    best_store: StoreRank
    ingredients: List[str]
