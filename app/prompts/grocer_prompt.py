"""Grocer agent prompts.

Only used when the user mentioned a dish name but no explicit ingredients.
The Grocer Agent calls the LLM once to get a clean ingredient list, then
passes those to the pricing service — no LLM involvement in pricing itself.
"""

GROCER_SYSTEM_PROMPT = """\
You are a grocery planning assistant.

Given a dish name, return a clean shopping list of ingredient names
suitable for searching in a grocery store (no quantities, no prep notes).

Respond with ONLY valid JSON — no explanation, no markdown, no extra text:
{
  "ingredients": ["ingredient1", "ingredient2", ...]
}
"""

# {dish_name} is filled in by the Grocer Agent before calling llm_client.
GROCER_HUMAN_PROMPT = "Dish: {dish_name}"
