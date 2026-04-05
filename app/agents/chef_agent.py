"""Chef agent — generates a full recipe from a classified intent."""

from app.prompts.chef_prompt import CHEF_HUMAN_PROMPT, CHEF_SYSTEM_PROMPT
from app.schemas.chef import ChefOutput
from app.schemas.intent import IntentOutput
from app.services.llm_client import invoke_structured


async def generate_recipe(intent: IntentOutput) -> ChefOutput:
    """Generate a recipe for the dish described in the given intent.

    Args:
        intent: Validated IntentOutput from the intent agent.

    Returns:
        ChefOutput with dish_name, ingredients, steps, tips, and video_links.
    """
    dish_name = intent.dish_name or "the requested dish"
    ingredients = ", ".join(intent.ingredients) if intent.ingredients else "not specified"

    return await invoke_structured(
        system_prompt=CHEF_SYSTEM_PROMPT,
        human_prompt=CHEF_HUMAN_PROMPT,
        output_schema=ChefOutput,
        dish_name=dish_name,
        ingredients=ingredients,
    )
