# Codex
## What is it?

Codex is an AI programming agent that has access to an up-to-date knowledge base containing documentation of various tools (libraries, APIs, frameworks, etc.) as well as the ability to search Stack Overflow for debugging assistance.

## What problem does it solve?

### 1. Developer Struggles

Developers typically need to manually dig through lengthy documentation and countless Stack Overflow discussions to use tools properly, which is a time-consuming and frustrating process.

### 2. Aren't AIs Good Enough?

Current AI tools (like ChatGPT, DeepSeek, Claude, etc.) often lack accurate information about programming tools, especially newer or frequently updated ones. This leads to incorrect or outdated code. Even turning on web search doesn’t fully solve this issue, as a single search may not be enough for complex queries.

### 3. Codex to the Rescue

With access to complete documentations of tools and the ability to search Stack Overflow (where actual developers provide solutions to real-world issues), Codex can competently assist developers in reading documentation and debugging, saving them precious time and effort.

## How does it work?

### 1. Documentation

1.	The user selects the tools they are working with (e.g., Next.js, Supabase, Groq).
2.	The program collects all URLs of documentation pages for those tools.  
3.	For each URL, it fetches the HTML document, extracts the text content, converts to Markdown format, then stores in a database.
4.	When a user asks a question, an LLM first looks through all the URLs to see which ones are most relevant.
5.	The full text content for the top chosen URLs is then retrieved from the database and provided to the LLM to provide an answer.

### 2. Stack Overflow

1. The user asks a question.
2. The program performs a Google Search and selects relevant results from Stack Overflow.
3. For each Stack Overflow page, the program fetches the HTML document, extracts the text content of top answers, and converts to Markdown format.
4. The LLM then reads through the answers and to provide a response.

## Tech stack

- **Anthropic**: The platform that provides API access to Claude 3.7 Sonnet (the LLM used for the agent).
- **Firecrawl**: SaaS platform for web scraping, here used to find all URLs of a website.
- **Supabase**: PostreSQL database Stores used to store contents of documentation pages.
- **ScrapingBee**: Google Search API, used to find relevant Stack Overflow discussions for a given query.
- **Next.js**: Full-stack web application framework used to build the user interface (coming soon!).