"""Intent agent — classifies user queries and extracts cooking entities."""

from app.prompts.intent_prompt import INTENT_HUMAN_PROMPT, INTENT_SYSTEM_PROMPT
from app.schemas.intent import IntentOutput
from app.services.llm_client import invoke_structured


async def classify_intent(query: str) -> IntentOutput:
    """Classify a user query into an intent and extract dish/ingredient entities.

    Args:
        query: Raw user input string.

    Returns:
        IntentOutput with intent, dish_name, and ingredients.
    """
    return await invoke_structured(
        system_prompt=INTENT_SYSTEM_PROMPT,
        human_prompt=INTENT_HUMAN_PROMPT,
        output_schema=IntentOutput,
        query=query,
    )
