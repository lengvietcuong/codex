import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import TypedDict

import aiohttp
import supabase
from firecrawl import FirecrawlApp
from google import genai as gemini
from google.genai import types
from tqdm.asyncio import tqdm_asyncio

from html_processing import get_html, get_page_text


SCRAPE_TIMEOUT_SECONDS = 15
MIN_CHUNK_SIZE = 1_000
MAX_CHUNK_SIZE = 5_000
DELIMITERS = ("```", "\n\n", ". ")
CONCURRENCY_LIMIT = 30

SUMMARIZATION_MODEL = "gemini-2.0-flash-lite"
SUMMARIZATION_SYSTEM_PROMPT = """Your task is to generate a title and summary for the content of a web page. Here are the requirements:
- Be concise but informative, especially for the title.
- Respond in JSON format (i.e. an object with 'title' and 'summary' fields).
- If the page shows an error indicating that the content failed to load properly (e.g. 404 Not Found), return 'ERROR' for the title and leave the summary blank."""

logger = logging.getLogger(__name__)


class ProcessedChunk(TypedDict):
    title: str
    summary: str
    content: str
    url: str
    base_url: str
    chunk_index: int
    created_at: str


async def scrape(
    base_url: str,
    firecrawl_client: FirecrawlApp,
    gemini_client: gemini.Client,
    supabase_client: supabase.AsyncClient,
) -> dict[str, int]:
    """
    Find all URLs for a given base URL, scrape each page, and ingest the processed data into the database.

    Args:
        base_url (str): The base URL of the documentation webpage.
        firecrawl_client (FirecrawlApp): The Firecrawl client instance.
        gemini_client (gemini.Client): The Gemini client instance.
        supabase_client (supabase.AsyncClient): The Supabase client instance.

    Returns:
        dict[str, int]: A dictionary containing 'total_urls_found' and 'total_urls_scraped'
    """
    logger.info(f"Finding URLs for {base_url}")
    urls = firecrawl_client.map_url(base_url)["links"]
    total_urls_found = len(urls)
    logger.info(f"Found {total_urls_found} URLs to scrape")

    total_urls_scraped = 0
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    async with aiohttp.ClientSession() as session:
        tasks = (
            asyncio.wait_for(
                scrape_url_and_ingest(
                    url, base_url, session, semaphore, gemini_client, supabase_client
                ),
                timeout=SCRAPE_TIMEOUT_SECONDS,
            )
            for url in urls
        )
        for task in tqdm_asyncio.as_completed(
            tasks, total=total_urls_found, desc="Processing"
        ):
            try:
                result = await task
                if result:
                    total_urls_scraped += 1
            except asyncio.TimeoutError:
                logger.error(f"Scraping or ingesting timed out")
            except Exception as error:
                logger.error(f"Error scraping or ingesting: {error}")

    logging.info(f"Successfully processed {total_urls_scraped} pages")
    return {
        "total_urls_found": total_urls_found,
        "total_urls_scraped": total_urls_scraped,
    }


def chunk_text(text: str) -> list[str]:
    """
    Split a piece of text into chunks, respecting code blocks, paragraphs, and sentences.

    Args:
        text (str): The full text to be split.

    Returns:
        list[str]: A list of text chunks.
    """
    chunks: list[str] = []
    start_index = 0
    text_length = len(text)

    while start_index < text_length:
        end_index = start_index + MAX_CHUNK_SIZE
        chunk = text[start_index:end_index].strip()

        if end_index >= text_length:
            chunks.append(chunk)
            return chunks

        # Look for a suitable delimiter to break the text
        for delimiter in DELIMITERS:
            delimiter_index = chunk.rfind(delimiter)
            if delimiter_index != -1 and delimiter_index >= MIN_CHUNK_SIZE:
                end_index = start_index + delimiter_index + len(delimiter)
                break

        chunk = text[start_index:end_index].strip()
        chunks.append(chunk)
        start_index = end_index

    return chunks


async def get_chunk_title_and_summary(
    text: str, url: str, gemini_client: gemini.Client
) -> dict[str, str]:
    """
    Generate a title and summary for a chunk of text.

    Args:
        text (str): The chunk of text to summarize.
        url (str): The URL of the webpage where the text is from.
        gemini_client (gemini.Client): The Gemini client instance.

    Returns:
        Dict[str, str]: A dictionary with 'title' and 'summary' fields.
    """
    response = await gemini_client.aio.models.generate_content(
        model=SUMMARIZATION_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SUMMARIZATION_SYSTEM_PROMPT,
            temperature=0.3,
        ),
        contents=f"URL: {url}\nContent:\n{text}",
    )
    return json.loads(response.text)


async def ingest_chunk(
    text: str,
    url: str,
    base_url: str,
    chunk_index: int,
    gemini_client: gemini.Client,
    supabase_client: supabase.AsyncClient,
) -> bool:
    """
    Process a chunk of text by generating its title and summary, then insert it into the database.

    Args:
        text (str): The chunk of text to process.
        url (str): The actual URL of the webpage where the text is from.
        base_url (str): The base URL of the documentation webpage.
        chunk_index (int): The index of the chunk within the document.
        gemini_client (gemini.Client): The Gemini client instance.
        supabase_client (supabase.AsyncClient): The Supabase client instance.

    Returns:
        bool: Whether the chunk was processed and inserted successfully.
    """
    try:
        title_summary_result = await get_chunk_title_and_summary(
            text, url, gemini_client
        )
    except Exception as error:
        logger.error(
            f"Error generating title or summary of chunk for {url}: {error}",
            exc_info=True,
        )
        return False

    title = title_summary_result["title"]
    summary = title_summary_result["summary"]
    if "ERROR" in title or not title or not summary:
        return False

    processed_chunk: ProcessedChunk = {
        "title": title,
        "summary": summary,
        "content": text,
        "url": url,
        "base_url": base_url,
        "chunk_index": chunk_index,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await supabase_client.table("documentation").insert(processed_chunk).execute()
    except Exception as error:
        logger.error(
            f"Error inserting chunk into database for {url}: {error}",
            exc_info=True,
        )
        return False
    return True


async def scrape_url_and_ingest(
    url: str,
    base_url: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    gemini_client: gemini.Client,
    supabase_client: supabase.AsyncClient,
) -> bool:
    """
    Fetch a webpage's HTML, convert it to Markdown, process the document, and ingest it into the database.

    Args:
        url (str): The actual URL of the webpage where the text is from.
        base_url (str): The base URL of the documentation webpage.
        session (aiohttp.ClientSession): A shared aiohttp session for HTTP requests.
        semaphore (asyncio.Semaphore): Semaphore to limit concurrent operations.
        gemini_client (gemini.Client): The Gemini client instance.
        supabase_client (supabase.AsyncClient): The Supabase client instance.

    Returns:
        bool: Whether the scraping and ingestion processes were successful.
    """
    async with semaphore:
        try:
            html_content = await get_html(url, session)
        except Exception as error:
            logger.error(f"Error fetching HTML for {url}: {error}", exc_info=True)
            return False

    markdown_text = get_page_text(html_content)
    chunks = chunk_text(markdown_text)
    tasks = (
        ingest_chunk(chunk, url, base_url, chunk_index, gemini_client, supabase_client)
        for chunk_index, chunk in enumerate(chunks)
    )
    await asyncio.gather(*tasks, return_exceptions=True)
    return True
