"""Ranking agent output schemas."""

from typing import List

from pydantic import BaseModel


class StoreRank(BaseModel):
    name: str
    total_cost: float
    delivery_time_mins: int
    score: float


class StoreRankingOutput(BaseModel):
    stores: List[StoreRank]
    best_store: str
