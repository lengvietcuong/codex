# Codex
## What is it?

Codex is an AI programming agent that has access to an up-to-date knowledge base containing documentation of various tools (libraries, APIs, frameworks, etc.).

## What problem does it solve?

Developers often need to look up documentation for tools they are using, and some are quite long and complex, making it time-consuming and frustrating process.

Current AI tools (like ChatGPT, DeepSeek, Claude, etc.) often lack accurate information about programming tools, especially newer or frequently updated ones. This leads to incorrect or outdated code. Even web search doesn’t fully solve this issue, as it may only provide general information without complete documentation.

## How does it works?

1.	The user selects the tools they are working with (e.g., Next.js, Supabase, Groq).
2.	The program collects all URLs of documentation pages for those tools.  
3.	For each URL, it fetches the HTML document, extracts the text content, converts to Markdown format, then stores in a database.
4.	When a user asks a question, an LLM first looks through all the URLs to see which ones are most relevant.
5.	The full text content for the top chosen URLs is then retrieved from the database and provided to the LLM to provide an answer.

## Tech stack

- Firecrawl – Finds all URLs of a website.
- Supabase – Stores documentation content and vector embeddings.
- PydanticAI – AI agent framework.
- Groq – Platform for running open-source LLMs.
- Fireworks.ai – Also a platform for running LLMs, but used here for creating embeddings.