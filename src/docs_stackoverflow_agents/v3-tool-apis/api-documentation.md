# Codex Tool APIs

This FastAPI server provides endpoints for scraping and retrieving documentation pages as well as searching Stack Overflow.

## Setup

### Environment Variables

The following services are used:

- **Firecrawl**: Used for finding all URLs connected to a base documentation URL
- **Gemini AI**: Generates titles and summaries for documentation content
- **Supabase**: Database for storing and retrieving documentation
- **ScrapingBee**: Powers the Stack Overflow search functionality

Your `.env` file should include the environment variables below:

```
FIRECRAWL_API_KEY=your_firecrawl_api_key
GEMINI_API_KEY=your_gemini_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SCRAPINGBEE_API_KEY=your_scrapingbee_api_key
```

### Running the Application

```bash
python api.py
```

This will start the FastAPI application on `http://0.0.0.0:8000`.

## API Endpoints

### Scrape Documentation

**URL:** `/scrape`  
**Method:** `POST`  
**Description:** Scrapes documentation from a given base URL, processes it, and stores it in the database.

**Parameters:**
- `url` (required): Base URL to scrape documentation from

**Response:**
```json
{
  "total_urls_found": 42,
  "total_urls_scraped": 39
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/scrape?url=https://docs.pydantic.dev/latest/"
```

### Get Documentation Pages

**URL:** `/documentation-pages`  
**Method:** `GET`  
**Description:** Retrieves a list of all documentation pages (URLs, titles, and summaries) stored in the database, with optional filtering.

**Parameters:**
- `must_include` (optional): List of strings that must be present in the URLs. If provided, only URLs containing at least one of these strings will be returned.

**Response:**
```json
[
  {
    "url": "https://docs.pydantic.dev/latest/",
    "title": "Pydantic Documentation",
    "summary": "Data validation and settings management using Python type hints"
  },
  {
    "url": "https://docs.supabase.com/",
    "title": "Supabase Documentation",
    "summary": "The open source Firebase alternative"
  }
]
```

**Example:**
```bash
curl "http://localhost:8000/documentation-urls?must_include=supabase&must_include=auth"
```

### Get Documentation Content

**URL:** `/documentation`  
**Method:** `GET`  
**Description:** Retrieves the full content of a specific documentation page.

**Parameters:**
- `url` (required): URL of the documentation page to retrieve

**Response:**
```
# Getting Started

This guide will help you get started with our product...
```

**Example:**
```bash
curl "http://localhost:8000/documentation?url=http://docs.fireworks.ai/tools-sdks/openai-compatibility"
```

### Search Stack Overflow

**URL:** `/search-stackoverflow`  
**Method:** `GET`  
**Description:** Searches Stack Overflow for a given query and returns the top answers.

**Parameters:**
- `query` (required): Search query for Stack Overflow

**Response:**
Markdown-formatted string containing Stack Overflow results.

**Example:**
```bash
curl "http://localhost:8000/search-stackoverflow?query=how%20to%20load%20external%20images%20in%20nextjs"
```

## Core Components

### Web Scraping

The web scraping functionality (`web_scraping.py`) follows these steps:

1. Uses Firecrawl to find all URLs connected to a base documentation URL
2. Scrapes each URL concurrently (with a concurrency limit of 30)
3. Processes the HTML into text and chunks it into manageable pieces
4. Generates a title and summary for each chunk using Gemini AI
5. Stores the processed chunks in Supabase

### Documentation Management

The documentation management functionality (`documentation.py`) provides:

1. Retrieval of all documentation URLs, with optional filtering
2. Retrieval of full documentation page content, including:
   - Sorting chunks by index
   - Formatting with the page title
   - Joining chunks with proper spacing

### Stack Overflow Integration

The Stack Overflow integration (`stackoverflow.py`) provides:

1. Search functionality using ScrapingBee to query Google for relevant Stack Overflow pages
2. Extraction of questions and top answers from each page
3. Formatting results in a readable Markdown format

## Configuration

### Database Schema

The Supabase database uses a `documentation` table with the following structure:

- `title`: Document title
- `summary`: Document summary
- `content`: Document content
- `url`: URL of the document
- `base_url`: Base URL of the documentation
- `chunk_index`: Index of the chunk within the document
- `created_at`: Timestamp of when the document was created
