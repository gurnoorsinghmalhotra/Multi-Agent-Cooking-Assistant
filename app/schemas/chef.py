"""Chef agent schema.

Defines the structured output returned by the Chef Agent after
generating a recipe from a user's cooking query.
"""

from typing import List

from pydantic import BaseModel


class ChefOutput(BaseModel):
    """Full recipe response from the Chef Agent."""

    dish_name: str

    # Ingredients with quantities, e.g. "2 cups flour".
    ingredients: List[str]

    # Numbered, actionable cooking steps.
    steps: List[str]

    # Practical cooking advice (technique tips, substitutions, etc.).
    tips: List[str]

    # YouTube/tutorial links. Always [] for MVP — real integration is out of scope.
    video_links: List[str]
