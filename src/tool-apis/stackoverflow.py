import asyncio
import logging
import os

import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from html_processing import get_html, get_page_text


WEB_SEARCH_TIME_OUT_SECONDS = 5
WEB_SEARCH_URL_LIMIT = 3
POST_LIMIT_PER_PAGE = 3

SCRAPINGBEE_BASE_URL = "https://app.scrapingbee.com/api/v1/store/google"
POST_HTML_TAG = "div"
POST_CSS_CLASS = "s-prose js-post-body"

logger = logging.getLogger(__name__)

load_dotenv()
SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY")

async def search_stackoverflow(query: str) -> str:
    """
    Search Stack Overflow for a given query, look through the top 3 threads, and extract the top 3 answers from each.

    Args:
        query (str): The search query in natural language.

    Returns:
        str: A Markdown-formatted string containing Stack Overflow results.

    Raises:
        Exception: If no results are found.
    """
    logger.info(f"Starting StackOverflow search for: '{query}'")
    # Create one aiohttp session to be shared across all requests.
    async with aiohttp.ClientSession() as session:
        urls = await get_stackoverflow_urls(query, session)
        logger.info(f"Found {len(urls)} Stack Overflow URLs")
        if not urls:
            raise Exception("No relevant Stack Overflow discussions found")

        # Fetch the HTML for each URL concurrently.
        logger.info("Fetching HTML content for Stack Overflow pages")
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
                for index, answer in enumerate(answer_contents, 1):
                    result += f"**Answer {index}**:\n{answer}\n\n"
                formatted_results.append(result)
            except Exception as error:
                logger.error(f"Failed to process {urls[i]}: {str(error)}")
        
        if not formatted_results:
            raise Exception("No Stack Overflow results found")

        return "\n\n---\n\n".join(formatted_results)


async def get_stackoverflow_urls(
    query: str, session: aiohttp.ClientSession
) -> list[str]:
    """
    Perform a Google search for URLs to relevant Stack Overflow pages.

    Args:
        query (str): The search query in natural language.
        session (aiohttp.ClientSession): An aiohttp session.

    Returns:
        list[str]: List of URLs to Stack Overflow pages.
    """
    # Limit search to Stack Overflow using the site: operator.
    search_query = f"{query} site:stackoverflow.com"
    params = {
        "api_key": SCRAPINGBEE_API_KEY,
        "search": search_query,
        "nb_results": WEB_SEARCH_URL_LIMIT,
    }

    async with session.get(
        SCRAPINGBEE_BASE_URL, params=params, timeout=WEB_SEARCH_TIME_OUT_SECONDS
    ) as response:
        if response.status != 200:
            logger.error("ScrapingBee API request failed")
            response.raise_for_status()

        search_results = await response.json()
        urls = []
        # Extract URLs from organic search results.
        for result in search_results["organic_results"]:
            if "url" in result:
                urls.append(result["url"])
        urls = urls[:WEB_SEARCH_URL_LIMIT]
        return urls


def extract_posts(html: str) -> tuple[str, list[str]]:
    """
    Extract the first 3 posts from the HTML document of a Stack Overflow page.

    Args:
        html (str): The HTML document of the StackOverflow page.

    Returns:
        tuple[str, list[str]]: (question_markdown, list_of_answer_markdowns)
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find all divs with the specific class
    post_divs = soup.find_all(
        POST_HTML_TAG, class_=POST_CSS_CLASS, limit=POST_LIMIT_PER_PAGE
    )

    # First div is the question
    question_html = str(post_divs[0])
    question_markdown = get_page_text(question_html)

    # Remaining divs are answers
    answer_markdowns = []
    for i in range(1, len(post_divs)):
        answer_html = str(post_divs[i])
        answer_markdown = get_page_text(answer_html)
        answer_markdowns.append(answer_markdown)

    return question_markdown, answer_markdowns
