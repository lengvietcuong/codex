from __future__ import annotations
import asyncio
import aiohttp
import json
import logging
import os
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Any

import anthropic
from dotenv import load_dotenv
import supabase

from stackoverflow import get_stackoverflow_urls, extract_posts
from html_processing import get_html

# Setup logging
logger = logging.getLogger(__name__)

# System prompt for the agent
SYSTEM_PROMPT = """You are a chatbot that assists developers with reading documentation and debugging, which you are given tools for. If a user's question is on coding documentation, start off by listing all the available URLs of documentation pages. Then, select the top most relevant ones to dive into (typically 1 or 2 is enough, and fewer is better), and respond based on the contents of those pages. If you are asked to debug an issue, use Stack Overflow. In your responses, always provide as much detail as possible, and include examples if available. Finally, explicitly state if you cannot find any relevant information."""


@dataclass
class Dependencies:
    supabase_client: supabase.Client


class ClaudeAgent:
    def __init__(self, model="claude-3-7-sonnet-20250219"):
        """Initialize Claude agent with API client and tools."""
        load_dotenv()
        self.client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.tools = [
            {
                "name": "list_documentation_pages",
                "description": "Retrieve a list of all available documentation pages.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "must_include": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of substrings. If provided, only URLs containing at least one of these substrings will be returned.",
                        }
                    },
                    "required": [],
                },
            },
            {
                "name": "get_page_content",
                "description": "Retrieve the full content of a specific documentation page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The exact URL of the page to retrieve.",
                        }
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "search_stackoverflow",
                "description": "Retrieve Stack Overflow discussions relevant to the search query.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query in natural language.",
                        }
                    },
                    "required": ["query"],
                },
            },
        ]
        self.deps = None

    def initialize_dependencies(self, supabase_client):
        """Initialize dependencies required for tool execution."""
        self.deps = Dependencies(supabase_client=supabase_client)

    async def chat_stream(
        self, messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream a conversation with Claude, yielding responses as they arrive."""
        if not self.deps:
            raise ValueError(
                "Dependencies not initialized. Call initialize_dependencies first."
            )

        try:
            while True:
                # Stream the response from Claude
                async with self.client.messages.stream(
                    model=self.model,
                    max_tokens=2000,
                    temperature=0.1,
                    system=SYSTEM_PROMPT,
                    tools=self.tools,
                    messages=messages,
                ) as stream:
                    # Stream response text chunks
                    current_content = []
                    async for chunk in stream.text_stream:
                        current_content.append(chunk)
                        yield {"type": "text_chunk", "content": chunk}

                    # Get the final message with all content blocks
                    final_message = await stream.get_final_message()

                    # If Claude doesn't need to use tools, we're done
                    if final_message.stop_reason != "tool_use":
                        yield {"type": "complete", "content": "".join(current_content)}
                        break

                    # Handle tool calls
                    tool_calls = []
                    for block in final_message.content:
                        if block.type == "tool_use":
                            tool_calls.append(block)

                    # Process each tool call and append results to messages
                    for tool_call in tool_calls:
                        tool_name = tool_call.name
                        tool_input = tool_call.input
                        tool_id = tool_call.id

                        yield {
                            "type": "tool_call",
                            "name": tool_name,
                            "input": tool_input,
                        }

                        # Execute the tool
                        result = await self._execute_tool(tool_name, tool_input)

                        yield {
                            "type": "tool_result",
                            "name": tool_name,
                            "result": result,
                        }

                        # Add the tool result to the message history
                        messages.append(
                            {"role": "assistant", "content": final_message.content}
                        )

                        messages.append(
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_id,
                                        "content": result,
                                    }
                                ],
                            }
                        )

        except Exception as e:
            logger.exception("Error in conversation with Claude: %s", str(e))
            yield {"type": "error", "content": str(e)}

    async def _execute_tool(self, tool_name, tool_input):
        """Execute the appropriate tool based on the tool name."""
        try:
            if tool_name == "list_documentation_pages":
                must_include = tool_input.get("must_include", [])
                return await self._list_documentation_pages(must_include)
            elif tool_name == "get_page_content":
                return await self._get_page_content(tool_input["url"])
            elif tool_name == "search_stackoverflow":
                return await self._search_stackoverflow(tool_input["query"])
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            logger.exception("Error executing tool %s: %s", tool_name, str(e))
            return f"Error executing {tool_name}: {str(e)}"

    async def _list_documentation_pages(self, must_include=None):
        """
        Implementation of list_documentation_pages tool.

        Args:
            must_include: Optional list of substrings. If provided, only URLs containing
                         at least one of these substrings will be returned.
        """
        logger.info("Listing documentation pages")
        result = (
            self.deps.supabase_client.from_("documentation").select("url").execute()
        )
        urls = sorted({document["url"] for document in result.data})

        # Filter URLs if must_include is provided
        if must_include and len(must_include) > 0:
            logger.info(f"Filtering URLs for terms: {must_include}")
            filtered_urls = []
            for url in urls:
                url_lower = url.lower()
                if any(term.lower() in url_lower for term in must_include):
                    filtered_urls.append(url)
            urls = filtered_urls

        logger.info("Found %d documentation pages", len(urls))
        return json.dumps(urls)

    async def _get_page_content(self, url):
        """Implementation of get_page_content tool."""
        logger.info("Retrieving page content for URL: %s", url)
        result = (
            self.deps.supabase_client.from_("documentation")
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

    async def _search_stackoverflow(self, query):
        """Implementation of search_stackoverflow tool."""
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
