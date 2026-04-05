"""Intent schema.

Represents the structured output of the Intent Agent.
`Literal` on `intent` ensures only valid routing targets are accepted —
Pydantic will raise a ValidationError if the LLM returns anything else.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel

# The two valid routing targets in the system.
IntentLabel = Literal["chef_agent", "grocer_agent"]


class IntentOutput(BaseModel):
    """Validated output from the Intent Agent."""

    # Which specialist agent should handle this query.
    intent: IntentLabel

    # The dish being discussed, if identifiable from the query.
    dish_name: Optional[str] = None

    # Specific ingredients mentioned by the user, if any.
    ingredients: Optional[List[str]] = None
