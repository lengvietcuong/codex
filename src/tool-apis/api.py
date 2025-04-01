from fastapi import FastAPI, Query
from pydantic import HttpUrl
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from firecrawl import FirecrawlApp
from google import genai as gemini
import supabase

from documentation import (
    get_documentation_urls as _get_documentation_urls,
    get_documentation as _get_documentation,
)
from stackoverflow import search_stackoverflow as _search_stackoverflow
from web_scraping import scrape as _scrape


# Global client objects
firecrawl_client = None
gemini_client = None
supabase_client = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup: initialize clients
    global gemini_client, firecrawl_client, supabase_client

    load_dotenv()
    firecrawl_client = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
    gemini_client = gemini.Client(api_key=os.getenv("GEMINI_API_KEY"))
    supabase_client = await supabase.create_async_client(
        os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    )

    yield
    # Shutdown: cleanup code would go here if needed


app = FastAPI(lifespan=lifespan)


@app.post("/scrape", response_model=dict[str, int])
async def scrape(
    url: HttpUrl = Query(..., description="Base URL to scrape documentation from")
):
    """
    Scrape documentation from a given URL.

    Args:
        url: Base URL to scrape documentation from

    Returns:
        JSON with count of URLs found and successfully scraped
    """
    return await _scrape(str(url), firecrawl_client, gemini_client, supabase_client)


@app.get("/documentation-urls", response_model=list[str])
async def get_documentation_urls(must_include: list[str] = Query(None)):
    """
    Get all documentation URLs, optionally filtered by terms that must be included in the URL.

    Args:
        must_include: Optional list of strings that must be present in the URLs

    Returns:
        List of documentation URLs
    """
    return await _get_documentation_urls(supabase_client, must_include)


@app.get("/documentation", response_model=str)
async def get_documentation(
    url: HttpUrl = Query(..., description="URL of the documentation page to retrieve")
):
    """
    Get the content of a specific documentation page.

    Args:
        url: URL of the documentation page to retrieve

    Returns:
        The content of the documentation page
    """
    return await _get_documentation(str(url), supabase_client)


@app.get("/search-stackoverflow", response_model=str)
async def search_stackoverflow(
    query: str = Query(..., description="Search query for Stack Overflow")
):
    """
    Search Stack Overflow for a given query and return top answers.

    Args:
        query: The search query in natural language

    Returns:
        Markdown-formatted string containing Stack Overflow results
    """
    return await _search_stackoverflow(query)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
