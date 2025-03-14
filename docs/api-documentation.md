# Claude Agent API Documentation

## Overview

This API provides a chat interface powered by Claude, which assists developers with reading documentation and debugging. It uses FastAPI to provide a streaming response endpoint that allows real-time interaction with Claude's AI capabilities.

## Setup Requirements

### Environment Variables

The following environment variables must be set:

- `ANTHROPIC_API_KEY`: API key for Anthropic's services
- `SUPABASE_URL`: URL for the Supabase instance
- `SUPABASE_KEY`: API key for Supabase

### Dependencies

- fastapi
- pydantic
- anthropic
- supabase
- uvicorn
- python-dotenv

## API Endpoints

### POST /chat

Stream a conversation with Claude, enabling real-time responses including tool usage for documentation searching and Stack Overflow queries.

#### Request Format

```json
{
  "messages": [
    {
      "role": "user",
      "content": "How does FastAPI handle request validation?"
    }
  ]
}
```

The `messages` field should follow the Anthropic Messages API format, with each message having:
- `role`: Either "user" or "assistant"
- `content`: The message content, which can be a string or a structured content array

#### Response

The endpoint returns a Server-Sent Events (SSE) stream with `text/event-stream` content type. Each event in the stream is JSON formatted with the following possible types:

1. **Text Chunk**
   ```json
   {
     "type": "text_chunk",
     "content": "FastAPI handles request validation through..."
   }
   ```

2. **Tool Call**
   ```json
   {
     "type": "tool_call",
     "name": "list_documentation_pages",
     "input": {"must_include": ["validation"]}
   }
   ```

3. **Tool Result**
   ```json
   {
     "type": "tool_result",
     "name": "list_documentation_pages",
     "result": "[\"https://fastapi.tiangolo.com/tutorial/request-validation/\", ...]"
   }
   ```

4. **Complete**
   ```json
   {
     "type": "complete",
     "content": "Full response text..."
   }
   ```

5. **Error**
   ```json
   {
     "type": "error",
     "content": "Error message..."
   }
   ```

#### Error Responses

- **500 Internal Server Error**: Returned if there's an exception during processing

## Available Tools

The Claude Agent has access to the following tools:

### list_documentation_pages

Retrieves a list of all available documentation pages.

**Input Schema**:
```json
{
  "must_include": ["optional", "filter", "terms"]
}
```

The `must_include` parameter is optional and filters URLs to only include those containing at least one of the provided terms.

### get_page_content

Retrieves the full content of a specific documentation page.

**Input Schema**:
```json
{
  "url": "https://example.com/docs/page"
}
```

The `url` parameter is required and must be an exact URL from the documentation pages list.

### search_stackoverflow

Retrieves Stack Overflow discussions relevant to a search query.

**Input Schema**:
```json
{
  "query": "How to fix SQLAlchemy relationship error?"
}
```

The `query` parameter is required and should be a natural language search query.

## Implementation Details

### Application Lifecycle

The API uses FastAPI's lifespan feature to:
1. Initialize the Supabase client on startup
2. Create and configure the Claude agent with necessary dependencies
3. Clean up resources on shutdown (if needed)

### Streaming Responses

Responses are streamed using FastAPI's `StreamingResponse` with Server-Sent Events format. This allows for real-time updates as Claude processes requests and uses tools.

### Error Handling

- Environment variable errors are caught during initialization
- Errors during chat processing are caught and returned as HTTP 500 responses with details

## Running the API

To run the API locally:

```bash
python api.py
```

This will start the server on `0.0.0.0:8000`. You can then make requests to `http://localhost:8000/chat`.

For production deployment, consider using Gunicorn as the ASGI server:

```bash
gunicorn api:app -k uvicorn.workers.UvicornWorker -w 4
```

## Example Usage

Using curl:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "How do I validate request bodies in FastAPI?"}]}'
```

Using JavaScript fetch with streaming:

```javascript
async function chatWithClaude() {
  const response = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: [
        {
          role: 'user',
          content: 'How do I validate request bodies in FastAPI?'
        }
      ]
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const events = chunk.split('\n\n');
    
    for (const event of events) {
      if (event.startsWith('data: ')) {
        const data = JSON.parse(event.slice(6));
        handleEvent(data);
      }
    }
  }
}

function handleEvent(data) {
  switch (data.type) {
    case 'text_chunk':
      console.log('Received text:', data.content);
      break;
    case 'tool_call':
      console.log('Tool called:', data.name, data.input);
      break;
    case 'tool_result':
      console.log('Tool result:', data.name, data.result);
      break;
    case 'complete':
      console.log('Response complete:', data.content);
      break;
    case 'error':
      console.error('Error:', data.content);
      break;
  }
}
```
