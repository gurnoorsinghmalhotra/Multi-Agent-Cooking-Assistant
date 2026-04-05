"""LLM client — the only file that imports from langchain or openai.
All agents call invoke_structured(); nothing touches the LLM directly.
"""

from typing import Type, TypeVar

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

_llm = ChatOpenAI(
    model=settings.openai_model,
    api_key=settings.openai_api_key,
    temperature=0,
)


async def invoke_structured(
    system_prompt: str,
    human_prompt: str,
    output_schema: Type[T],
    **prompt_vars,
) -> T:
    """Call the LLM and return a validated Pydantic model.

    Args:
        system_prompt: System message string.
        human_prompt:  Human message template with {variable} placeholders.
        output_schema: Pydantic model class to parse the response into.
        **prompt_vars: Values for the placeholders in human_prompt.

    Returns:
        A validated instance of output_schema.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    chain = prompt | _llm.with_structured_output(output_schema)
    return await chain.ainvoke(prompt_vars) 
# example output: ChefOutput(dish_name='Spaghetti Carbonara', ingredients=['spaghetti', 'eggs', 'pancetta', 'parmesan cheese', 'black pepper'], steps=['Boil spaghetti until al dente.', 'Cook pancetta until crispy.', 'Whisk eggs and parmesan together.', 'Combine spaghetti, pancetta, and egg mixture.', 'Season with black pepper and serve.'], tips=['Use fresh eggs for a creamier sauce.', 'Reserve some pasta water to adjust the sauce consistency if needed.'], video_links=['https://www.youtube.com/watch?v=3AAdKl1UYZs'])
