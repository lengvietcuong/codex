from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import os
import logging
import supabase
from contextlib import asynccontextmanager

from agent import ClaudeAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize Supabase client
def init_supabase():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

    return supabase.create_client(supabase_url, supabase_key)


# FastAPI startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize on startup
    app.state.supabase_client = init_supabase()
    app.state.claude_agent = ClaudeAgent()
    app.state.claude_agent.initialize_dependencies(app.state.supabase_client)
    yield
    # Clean up on shutdown
    # No specific cleanup needed


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]


@app.post("/chat")
async def chat(request: ChatRequest):
    """Stream a conversation with Claude."""
    try:

        async def generate_response():
            async for event in app.state.claude_agent.chat_stream(request.messages):
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(generate_response(), media_type="text/event-stream")
    except Exception as e:
        logger.exception("Error in chat endpoint")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
