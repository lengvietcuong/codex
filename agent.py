from __future__ import annotations

import logging
from dataclasses import dataclass
import os
from typing import List

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel
import supabase


logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"

SYSTEM_PROMPT = """You are an expert question-answer chatbot, specifically designed to assist developers with programming documentation (e.g. libraries, frameworks, APIs, etc.), which you are given tools to search for. Start off by listing all the available URLs of documentation pages. Then, select the top 3 most relevant ones to search further (do not search outside the given URLs). In your responses, always provide as much detail as possible, and include examples if available. Finally, explicitly state if you cannot find any relevant information."""


@dataclass
class Dependencies:
    supabase_client: supabase.Client
    fireworks_client: AsyncOpenAI


load_dotenv()
groq_model = GroqModel("llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY_1"))
codex_agent = Agent(
    groq_model,
    system_prompt=SYSTEM_PROMPT,
    deps_type=Dependencies,
    retries=2,
    model_settings={"temperature": 0.1},
)


@codex_agent.tool
async def list_documentation(
    context: RunContext[Dependencies],
) -> List[str]:
    """
    Retrieve a list of all available documentation pages.

    Returns:
        List[str]: List of URLs for all documentation pages.
    """
    logger.info("Listing all documentation pages")
    result = context.deps.supabase_client.from_("documentation").select("url").execute()
    urls = sorted({document["url"] for document in result.data})
    logger.info("Found %d documentation pages", len(urls))
    return urls


@codex_agent.tool
async def get_page_content(context: RunContext[Dependencies], url: str) -> str:
    """
    Retrieve the full content of a specific documentation page.

    Args:
        context: The context including the Supabase client.
        url: The exact URL of the page to retrieve.

    Returns:
        str: The complete page content.
    """
    logger.info("Retrieving page content for URL: %s", url)
    result = (
        context.deps.supabase_client.from_("documentation")
        .select("title, content, chunk_index")
        .eq("url", url)
        .order("chunk_index")
        .execute()
    )
    if not result.data:
        logger.warning("No content found for URL: %s", url)
        return f"No content found for URL: {url}"

    page_title = result.data[0]["title"].split(" - ")[0]
    formatted_content = [f"# {page_title}\n"]
    for chunk in result.data:
        formatted_content.append(chunk["content"])

    logger.info("Page content for URL: %s retrieved successfully", url)
    return "\n\n".join(formatted_content)
