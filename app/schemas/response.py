"""Response schemas.

Defines the final API response envelope. `intent` uses the same
Literal type as IntentOutput so callers always know exactly which
routing decision was made and what shape `data` holds.
"""

from typing import Literal, Union

from pydantic import BaseModel

from app.schemas.chef import ChefOutput
from app.schemas.grocer import GrocerOutput
from app.schemas.ranking import StoreRankingOutput


class QueryResponse(BaseModel):
    """Top-level response returned by POST /query."""

    # Which agent handled this query — echoed back so clients can branch on it.
    intent: Literal["chef_agent", "grocer_agent", "ranking_agent"]

    # Structured payload — recipe, grocery cart, or store ranking.
    data: Union[ChefOutput, GrocerOutput, StoreRankingOutput]
