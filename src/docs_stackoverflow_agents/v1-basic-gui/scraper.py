import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from itertools import cycle
from time import perf_counter
from typing import Dict, List, TypedDict

import aiohttp
import supabase
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from groq import AsyncGroq
from openai import AsyncOpenAI
from tqdm.asyncio import tqdm_asyncio

from html_processing import get_html, get_page_text


logger = logging.getLogger(__name__)


TIMEOUT_SECONDS = 15
MIN_CHUNK_SIZE = 1_000
MAX_CHUNK_SIZE = 5_000
DELIMITERS = ("```", "\n\n", ". ")

SUMMARIZATION_SYSTEM_PROMPT = """Your task is to generate a title and summary for the content of a web page. Here are the requirements:
- Be concise but informative, especially for the title.
- Respond in JSON format (i.e. an object with 'title' and 'summary' fields).
- If the page shows an error indicating that the content failed to load properly (e.g. 404 Not Found), return 'ERROR' for the title and leave the summary blank."""
GROQ_MODELS = (
    "llama3-8b-8192",
    "llama3-70b-8192",
    "llama-3.1-8b-instant",
    "llama-3.2-3b-preview",
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
    "llama-3.3-70b-specdec",
    "llama-3.3-70b-versatile",
    "gemma2-9b-it",
    "qwen-2.5-32b",
    "mixtral-8x7b-32768",
)

FIREWORKS_AI_BASE_URL = "https://api.fireworks.ai/inference/v1"
EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"

CONCURRENCY_LIMIT = 100


class ProcessedChunk(TypedDict):
    title: str
    summary: str
    content: str
    url: str
    base_url: str
    chunk_index: int
    embedding: List[float]
    created_at: str


def chunk_text(text: str) -> List[str]:
    """
    Split a piece of text into chunks, respecting code blocks, paragraphs, and sentences.

    Args:
        text (str): The full text to be split.

    Returns:
        List[str]: A list of text chunks.
    """
    chunks: List[str] = []
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
    text: str, url: str, groq_client: AsyncGroq, groq_model: str
) -> Dict[str, str]:
    """
    Generate a title and summary for a chunk of text.

    Args:
        text (str): The chunk of text to summarize.
        url (str): The URL of the webpage where the text is from.
        groq_client (AsyncGroq): An Groq client instance.
        groq_model (str): The name of the Groq model to use.

    Returns:
        Dict[str, str]: A dictionary with 'title' and 'summary' fields.
    """
    response = await groq_client.chat.completions.create(
        model=groq_model,
        messages=[
            {"role": "system", "content": SUMMARIZATION_SYSTEM_PROMPT},
            {"role": "user", "content": f"URL: {url}\nContent:\n{text}"},
        ],
        response_format={"type": "json_object"},
    )
    response_text = response.choices[0].message.content
    return json.loads(response_text)


async def get_embedding(text: str, fireworks_client: AsyncOpenAI) -> List[float]:
    """
    Generate an embedding vector for the given text.

    Args:
        text (str): The text to embed.
        fireworks_client (AsyncOpenAI): A Fireworks AI client instance.

    Returns:
        List[float]: The embedding vector.
    """
    response = await fireworks_client.embeddings.create(
        model=EMBEDDING_MODEL, input=text
    )
    embedding = response.data[0].embedding
    return embedding


async def ingest_chunk(
    text: str,
    url: str,
    base_url: str,
    chunk_index: int,
    groq_client: AsyncGroq,
    groq_model: str,
    fireworks_client: AsyncOpenAI,
    supabase_client: supabase.AsyncClient,
) -> bool:
    """
    Process a chunk of text by generating its title, summary, and embedding, then insert it into the database.

    Args:
        text (str): The chunk of text to process.
        url (str): The actual URL of the webpage where the text is from.
        base_url (str): The base URL of the documentation webpage.
        chunk_index (int): The index of the chunk within the document.
        groq_client (AsyncGroq): A Groq client instance.
        groq_model (str): The name of the Groq model to use.
        fireworks_client (AsyncOpenAI): A Fireworks AI client instance.
        supabase_client (supabase.AsyncClient): A Supabase client instance.

    Returns:
        bool: Whether the chunk was processed and inserted successfully.
    """
    try:
        # Generate (title, summary) and embedding concurrently
        title_summary_result, embedding_result = await asyncio.gather(
            get_chunk_title_and_summary(text, url, groq_client, groq_model),
            get_embedding(text, fireworks_client),
        )
    except Exception as error:
        logger.error(
            f"Error generating title, summary, or embedding for chunk for {url}: {error}",
            exc_info=True,
        )
        return False

    title = title_summary_result["title"]
    summary = title_summary_result["summary"]
    if "ERROR" not in title or not title or not summary:
        return False

    processed_chunk: ProcessedChunk = {
        "title": title,
        "summary": summary,
        "content": text,
        "url": url,
        "base_url": base_url,
        "chunk_index": chunk_index,
        "embedding": embedding_result,
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
    aiohttp_session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    groq_client: AsyncGroq,
    groq_model: str,
    fireworks_client: AsyncOpenAI,
    supabase_client: supabase.AsyncClient,
) -> bool:
    """
    Fetch a webpage's HTML, convert it to Markdown, process the document, and ingest it into the database.

    Args:
        url (str): The actual URL of the webpage where the text is from.
        base_url (str): The base URL of the documentation webpage.
        aiohttp_session (aiohttp.ClientSession): A shared aiohttp session for HTTP requests.
        semaphore (asyncio.Semaphore): Semaphore to limit concurrent operations.
        groq_client (AsyncGroq): A Groq client instance.
        groq_model (str): The name of the Groq model to use.
        fireworks_client (AsyncOpenAI): A Fireworks AI client instance.
        supabase_client (supabase.AsyncClient): A Supabase client instance.

    Returns:
        bool: Whether the scraping and ingestion processes were successful.
    """
    async with semaphore:
        try:
            html_content = await get_html(aiohttp_session, url)
        except Exception as error:
            logger.error(f"Error fetching HTML for {url}: {error}", exc_info=True)
            return False

    markdown_text = get_page_text(html_content)
    chunks = chunk_text(markdown_text)
    tasks = (
        ingest_chunk(
            chunk,
            url,
            base_url,
            index,
            groq_client,
            groq_model,
            fireworks_client,
            supabase_client,
        )
        for index, chunk in enumerate(chunks)
    )
    await asyncio.gather(*tasks, return_exceptions=True)
    return True


async def scrape_documentation(
    base_url: str,
    aiohttp_session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    firecrawl_client: FirecrawlApp,
    groq_clients: List[AsyncGroq],
    fireworks_client: AsyncOpenAI,
    supabase_client: supabase.AsyncClient,
) -> int:
    """
    Find all URLs for a given base URL, scrape each page, and ingest the processed data into the database.

    Args:
        base_url (str): The base URL of the documentation webpage.
        aiohttp_session (aiohttp.ClientSession): Shared aiohttp session.
        semaphore (asyncio.Semaphore): Semaphore to limit concurrent operations.
        firecrawl_client (FirecrawlApp): Firecrawl client instance.
        groq_clients (List[AsyncGroq]): List of Groq client instances.
        fireworks_client (AsyncOpenAI): Fireworks AI client instance.
        supabase_client (supabase.AsyncClient): Supabase client instance.

    Returns:
        int: The number of successfully processed pages.
    """
    logger.info(f"Finding URLs for {base_url}")
    urls = firecrawl_client.map_url(base_url)["links"]
    logger.info(f"Found {len(urls)} URLs to scrape")

    groq_cycle = cycle(
        (groq_client, groq_model)
        for groq_client in groq_clients
        for groq_model in GROQ_MODELS
    )
    tasks = (
        asyncio.wait_for(
            scrape_url_and_ingest(
                url,
                base_url,
                aiohttp_session,
                semaphore,
                groq_client,
                groq_model,
                fireworks_client,
                supabase_client,
            ),
            timeout=TIMEOUT_SECONDS,
        )
        for url, (groq_client, groq_model) in zip(urls, groq_cycle)
    )
    success_count = 0
    for task in tqdm_asyncio.as_completed(tasks, total=len(urls), desc="Processing"):
        try:
            result = await task
            if result:
                success_count += 1
        except asyncio.TimeoutError:
            logger.error(f"Scraping or ingesting timed out")
        except Exception as error:
            logger.error(f"Error scraping or ingesting: {error}")

    logging.info(f"Successfully processed {success_count} pages")
    return success_count


async def main():
    # Initialize clients
    load_dotenv()
    groq_api_key_count = int(os.getenv("GROQ_API_KEY_COUNT"))
    groq_clients = [
        AsyncGroq(api_key=os.getenv(f"GROQ_API_KEY_{i}"))
        for i in range(1, groq_api_key_count + 1)
    ]
    fireworks_client = AsyncOpenAI(
        api_key=os.getenv("FIREWORKS_API_KEY"), base_url=FIREWORKS_AI_BASE_URL
    )
    supabase_client = await supabase.acreate_client(
        os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    )
    firecrawl_client = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

    # Take user input
    base_url = input("Enter base URL: ")

    # Scrape and ingest documentation concurrently
    start_time = perf_counter()
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    async with aiohttp.ClientSession() as aiohttp_session:
        await scrape_documentation(
            base_url,
            aiohttp_session,
            semaphore,
            firecrawl_client,
            groq_clients,
            fireworks_client,
            supabase_client,
        )
    end_time = perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f"Time taken: {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
