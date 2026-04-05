"""Orchestrator — coordinates intent classification and agent routing."""

from app.agents.chef_agent import generate_recipe
from app.agents.grocer_agent import build_cart
from app.agents.intent_agent import classify_intent
from app.schemas.request import QueryRequest
from app.schemas.response import QueryResponse


async def handle_query(request: QueryRequest) -> QueryResponse:
    """Run the full pipeline: classify intent, route to the right agent, return response.

    Args:
        request: Validated user query.

    Returns:
        QueryResponse with intent label and structured agent output.
    """
    intent = await classify_intent(request.query)

    if intent.intent == "chef_agent":
        data = await generate_recipe(intent)
    else:
        data = await build_cart(intent)

    return QueryResponse(intent=intent.intent, data=data)
