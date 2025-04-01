from __future__ import annotations
import asyncio
import aiohttp
from dataclasses import dataclass
import logging
import os

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.mistral import MistralModel
import supabase

from stackoverflow import get_stackoverflow_urls, extract_posts
from html_processing import get_html


SYSTEM_PROMPT = """You are an expert question-answer chatbot, specifically designed to assist developers with reading documentation and debugging, which you are given tools for (use them first without telling the user, then respond). If a user's question is on coding documentation, start off by listing all the available URLs of documentation pages. Then, select the top 3 most relevant ones to dive into, and respond based on the contents of those pages. If you are asked to debug an issue, use Stack Overflow. In your responses, always provide as much detail as possible, and include examples if available. Finally, explicitly state if you cannot find any relevant information."""


@dataclass
class Dependencies:
    supabase_client: supabase.Client


load_dotenv()
model = MistralModel("mistral-large-latest", api_key=os.getenv("MISTRAL_API_KEY"))
codex_agent = Agent(
    model,
    system_prompt=SYSTEM_PROMPT,
    deps_type=Dependencies,
    model_settings={"temperature": 0.1},
)


logger = logging.getLogger(__name__)


@codex_agent.tool
async def list_documentation(context: RunContext[Dependencies]) -> list[str]:
    """
    Retrieve a list of all available documentation pages.

    Args:
        context: The runtime context.

    Returns:
        list[str]: List of URLs for all documentation pages.
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
        context: The runtime context.
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


@codex_agent.tool
async def search_stackoverflow(context: RunContext[Dependencies], query: str) -> str:
    """
    Retrieve Stack Overflow discussions relevant to the search query.

    Args:
        context: The runtime context.
        query (str): The search query in natural language.

    Returns:
        str: A formatted string containing Stack Overflow questions and answers.
    """
    logger.info(f"Starting search for: '{query}'")
    # Create one aiohttp session to be shared across all requests.
    async with aiohttp.ClientSession() as session:
        urls = await get_stackoverflow_urls(query, session)
        logger.info(f"Found {len(urls)} Stack Overflow URLs")
        if not urls:
            return "No relevant Stack Overflow discussions found."

        # Fetch the HTML for each URL concurrently.
        tasks = (get_html(url, session) for url in urls)
        htmls = await asyncio.gather(*tasks, return_exceptions=True)

        # Process each successfully fetched HTML page.
        formatted_results = []
        for i, html in enumerate(htmls):
            if isinstance(html, Exception):
                logger.error(f"Failed to fetch {urls[i]}: {str(html)}")
                continue  # Skip pages that couldn't be scraped.

            try:
                question_content, answer_contents = extract_posts(html)
                result = f"## {urls[i]}\n\n### Question:\n{question_content}\n\n### Answers:\n"
                for idx, answer in enumerate(answer_contents, 1):
                    result += f"**Answer {idx}**:\n{answer}\n\n"
                formatted_results.append(result)
            except Exception:
                logger.exception(f"Failed to process {urls[i]}")

        if not formatted_results:
            return "Could not process any Stack Overflow discussions."

        return "\n\n---\n\n".join(formatted_results)
