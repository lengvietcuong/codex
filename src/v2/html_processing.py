import aiohttp
import subprocess


HTML_TIMEOUT_SECONDS = 5


async def get_html(url: str, session: aiohttp.ClientSession | None = None) -> str:
    """Fetch the raw HTML content of a web page.

    Args:
        url (str): The URL of the web page to fetch HTML from.
        session (aiohttp.ClientSession, optional): An existing aiohttp ClientSession to use.
            If None (default), a new session will be created.

    Returns:
        str: The raw HTML content of the web page.
    """

    async def _get_html():
        async with session.get(url, timeout=HTML_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                response.raise_for_status()
            return await response.text()

    if session is not None:  # Use the provided session
        return await _get_html()
    async with aiohttp.ClientSession() as session:  # Create a new session
        return await _get_html()


def get_page_text(html: str) -> str:
    """Convert a web page's HTML content to Markdown format.

    Args:
        html (str): The HTML content to convert to Markdown.

    Returns:
        str: The Markdown content converted from HTML.
    """
    process = subprocess.Popen(
        ["html2markdown"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    markdown, _ = process.communicate(html)
    return markdown.strip()
