import logging
import supabase


logger = logging.getLogger(__name__)


async def get_documentation_urls(
    supabase_client: supabase.AsyncClient, must_include: list[str] | None = None
) -> list[str]:
    """
    Retrieve a list of documentation URLs from the database.

    Args:
        supabase_client (supabase.AsyncClient): The Supabase client instance.
        must_include (list[str] | None): Optional list of substrings. If provided, only URLs containing at least one of these substrings will be returned. Defaults to None.

    Returns:
        list[str]: A list of documentation URLs.
    """
    logger.info("Listing documentation pages")
    result = await supabase_client.from_("documentation").select("url").execute()
    urls = sorted({document["url"] for document in result.data})
    if not must_include:
        return urls

    # Filter URLs if must_include is provided
    logger.info(f"Filtering URLs for keywords: {must_include}")
    filtered_urls = []
    for url in urls:
        url_lower = url.lower()
        if any(keyword.lower() in url_lower for keyword in must_include):
            filtered_urls.append(url)
    logger.info(f"Found {len(filtered_urls)} documentation pages")
    return filtered_urls


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
