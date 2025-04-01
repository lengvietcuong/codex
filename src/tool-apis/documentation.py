import logging
import supabase


logger = logging.getLogger(__name__)


async def get_documentation_pages(
    supabase_client: supabase.AsyncClient, must_include: list[str] | None = None
) -> list[dict]:
    """
    Retrieve a list of documentation pages with their URLs, titles, and summaries from the database.

    Args:
        supabase_client (supabase.AsyncClient): The Supabase client instance.
        must_include (list[str] | None): Optional list of substrings. If provided, only pages containing at least one of these substrings in their URL will be returned. Defaults to None.

    Returns:
        list[dict]: A list of documentation pages with their URLs, titles, and summaries.
    """
    logger.info("Listing documentation pages with titles and summaries")

    # Select URLs, titles, and summaries and sort by chunk index
    result = (
        await supabase_client.from_("documentation")
        .select("url, title, summary, chunk_index")
        .order("chunk_index")
        .execute()
    )

    # Ensure unique URLs and check for required keywords
    pages = []
    urls_seen = set()
    for page in result.data:
        url = page["url"]

        if url in urls_seen:
            continue
        url_lower = url.lower()
        if must_include and not any(
            keyword.lower() in url_lower for keyword in must_include
        ):
            continue

        pages.append(
            {
                "url": url,
                "title": page["title"],
                "summary": page["summary"],
            }
        )
        urls_seen.add(url)

    logger.info(f"Found {len(pages)} documentation pages")
    pages.sort(key=lambda x: x["url"])
    return pages


async def get_documentation(url: str, supabase_client: supabase.AsyncClient) -> str:
    """
    Retrieve the full content of a specific documentation page.

    Args:
        url (str): The exact URL of the page to retrieve.
        supabase_client (supabase.AsyncClient): The Supabase client instance.

    Returns:
        str: The complete page content in Markdown format.

    Raises:
        Exception: If no content is found.
    """
    logger.info(f"Retrieving page content for URL: {url}")

    # Retrieve the content from the database
    result = (
        await supabase_client.from_("documentation")
        .select("title, content, chunk_index")
        .eq("url", url)
        .order("chunk_index")
        .execute()
    )
    if not result.data:
        raise Exception(f"No content found for URL: {url}")

    # Parse and format the content
    page_title = result.data[0]["title"]
    formatted_content = [f"# {page_title}\n"]
    for chunk in result.data:
        formatted_content.append(chunk["content"])
    formatted_content = "\n\n".join(formatted_content)

    logger.info(
        f"Page content for {url} retrieved successfully ({len(formatted_content)} characters)"
    )
    return formatted_content
