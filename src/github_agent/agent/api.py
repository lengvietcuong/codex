import asyncio
from fastapi import FastAPI, Request, Header
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
from typing import Optional
from typing import Dict, AsyncGenerator, List
from contextlib import asynccontextmanager
from code_agent import CodeAssistant, DataLogger
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Store active connections and their corresponding assistants
active_assistants: Dict[str, 'StreamingCodeAssistant'] = {}
# Track ongoing requests to prevent duplicates
ongoing_requests: Dict[str, float] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create cleanup task
    cleanup_task = asyncio.create_task(cleanup_inactive_sessions())
    yield
    # Shutdown: cancel the cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="GitHub Code Assistant API", lifespan=lifespan)

# Configure CORS to allow browser clients to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.post("/stream")
async def stream_response(
    request: Request,
    x_request_id: Optional[str] = Header(None)
) -> StreamingResponse:
    """Stream the agent's response to a query"""
    request_id = x_request_id or f"req_{int(time.time() * 1000)}"
    print(f"[{request_id}] Received stream request")
    
    # Parse the request body
    data = await request.json()
    session_id = data.get("session_id")
    query = data.get("query")
    context = data.get("context", {})
    
    if not session_id or not query:
        print(f"[{request_id}] Missing session_id or query")
        return StreamingResponse(
            content=stream_error("Missing session_id or query"), 
            media_type="text/event-stream"
        )
    
    # Check if we already have this exact request in progress
    request_key = f"{session_id}:{query}"
    if request_key in ongoing_requests:
        time_diff = time.time() - ongoing_requests[request_key]
        if time_diff < 10.0:  # If the same request was made in the last 10 seconds
            print(f"[{request_id}] Duplicate request detected: {request_key} ({time_diff:.2f}s ago)")
            return StreamingResponse(
                content=stream_error("Duplicate request detected"), 
                media_type="text/event-stream"
            )
    
    # Track this request
    ongoing_requests[request_key] = time.time()
    
    try:
        # Get or create an assistant for this session
        if session_id not in active_assistants:
            print(f"[{request_id}] Creating new assistant for session {session_id}")
            active_assistants[session_id] = StreamingCodeAssistant(session_id)
        
        assistant = active_assistants[session_id]
        
        # Update the assistant with context info if provided
        if context:
            print(f"[{request_id}] Updating context with: {context}")
            assistant.update_context(context)
        
        # Register a cleanup function
        async def remove_ongoing_request():
            await asyncio.sleep(30)  # After 30 seconds, allow the same request again
            if request_key in ongoing_requests:
                del ongoing_requests[request_key]
                print(f"[{request_id}] Removed {request_key} from ongoing requests")
        
        asyncio.create_task(remove_ongoing_request())
        
        # Process the query
        print(f"[{request_id}] Processing query: {query[:50]}...")
        return StreamingResponse(
            content=assistant.process_query_streaming(query, request_id),
            media_type="text/event-stream"
        )
    except Exception as e:
        print(f"[{request_id}] Error processing request: {str(e)}")
        if request_key in ongoing_requests:
            del ongoing_requests[request_key]
        return StreamingResponse(
            content=stream_error(f"Internal server error: {str(e)}"), 
            media_type="text/event-stream"
        )

@app.get("/file/{session_id}/{repo_name:path}/{file_path:path}")
async def get_file_content(session_id: str, repo_name: str, file_path: str):
    """Get file content directly with improved error handling"""
    print(f"Received file request: session={session_id}, repo={repo_name}, path={file_path}")
    
    if session_id not in active_assistants:
        return {"error": "Invalid session"}
    
    # Fix potential URL encoding issues in repo_name and file_path
    import urllib.parse
    repo_name = urllib.parse.unquote(repo_name)
    file_path = urllib.parse.unquote(file_path)
    
    assistant = active_assistants[session_id]
    try:
        raw_response = assistant.execute_action({
            "action": "read_file",
            "parameters": {
                "repo_name": repo_name,
                "file_path": file_path
            }
        })
        
        response_data = json.loads(raw_response)
        
        # If there's an error message in the response, return it properly
        if "error" in response_data:
            print(f"Error reading file: {response_data['error']}")
            return {"error": response_data["error"]}
            
        # Update context with current file if successful
        if "file_path" in response_data:
            current_files = assistant.context.get("current_files", [])
            if response_data["file_path"] not in current_files:
                current_files.append(response_data["file_path"])
                assistant.update_context({"current_files": current_files})
        
        return response_data
    except Exception as e:
        print(f"Exception reading file: {str(e)}")
        return {"error": f"Failed to read file: {str(e)}"}

@app.post("/set_current_repo")
async def set_current_repo(request: Request):
    """Set the current repository for a session"""
    data = await request.json()
    session_id = data.get("session_id")
    repo_name = data.get("repo_name")
    
    if not session_id or not repo_name:
        return {"error": "Missing session_id or repo_name"}
    
    if session_id not in active_assistants:
        active_assistants[session_id] = StreamingCodeAssistant(session_id)
    
    assistant = active_assistants[session_id]
    assistant.update_context({"current_repo": repo_name})
    
    # Also perform list_directory on the repo root to get its contents
    raw_response = assistant.execute_action({
        "action": "list_directory",
        "parameters": {
            "repo_name": repo_name,
            "path": ""
        }
    })
    
    return json.loads(raw_response)

async def stream_error(message: str) -> AsyncGenerator[str, None]:
    """Stream an error message in SSE format"""
    yield f"data: {json.dumps({'content': f'🚨 Error: {message}', 'action_type': 'error'})}\n\n"
    
class StreamingCodeAssistant(CodeAssistant):
    """Extended version of CodeAssistant that supports HTTP streaming responses."""
    
    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self.agent_steps: List[str] = []
        self.context = {
            "current_repo": None,
            "current_files": []
        }
        # Initialize a session-specific data logger
        self.data_logger = DataLogger(log_dir=f"logs/{session_id}")
        
    def update_context(self, context_data: Dict):
        """Update the context with new information"""
        self.context.update(context_data)
        # Update short-term memory with context information
        if "current_repo" in context_data and context_data["current_repo"]:
            self.short_term_memory.memory.append(f"Currently viewing repository: {context_data['current_repo']}")
        if "current_files" in context_data and context_data["current_files"]:
            self.short_term_memory.memory.append(f"Currently viewing files: {', '.join(context_data['current_files'])}")
        
    async def format_sse_message(self, content: str, action_type: str = "", data: Optional[Dict] = None) -> str:
        """Format a message as a Server-Sent Event with action type"""
        message = {
            'content': content,
            'action_type': action_type or 'self_solve'
        }
        
        # Include any additional data if provided
        if data:
            message.update(data)
            
        return f"data: {json.dumps(message)}\n\n"
        
    async def process_query_streaming(self, query: str, request_id: str = "") -> AsyncGenerator[str, None]:
        """Process a query and stream the response back to the client as Server-Sent Events"""
        self.short_term_memory.is_done = False
        self.short_term_memory.goal = query
        self.agent_steps = []  # Reset steps for new query
        
        log_prefix = f"[{request_id}] " if request_id else ""

        # Start a new conversation log with this user query
        self.data_logger.start_conversation(query)

        # Start with setting the goal
        print(f"{log_prefix}Setting goal: {query[:50]}...")
        yield await self.format_sse_message(f"🎯 Understanding your request: {self.short_term_memory.goal}", "thinking")

        while not self.short_term_memory.is_done:
            # Get the next action
            print(f"{log_prefix}Getting next action...")
            action_spec = self.get_action()
            action_type = action_spec.get("action", "self_solve")
            
            print(f"{log_prefix}Action: {action_type}")
            
            # Add this step to the agent's thinking
            step = f"🧠 Agent action: {action_type}"
            self.agent_steps.append(step)
            yield await self.format_sse_message(
                "\n".join(self.agent_steps), 
                "thinking"
            )
                
            # Execute the action
            print(f"{log_prefix}Executing action...")
            raw_response = self.execute_action(action_spec)
            response = json.loads(raw_response)
            formatted = self.format_response(raw_response)
            
            # Extract data based on the action type
            additional_data = {}
            
            if action_type == "search":
                # Handle search results as repository cards
                if "results" in response:
                    additional_data["repositories"] = response.get("results", [])
                    # Don't set repoName for search results as we're showing multiple options
            elif action_type in ["list_directory", "repo_tree", "clone"]:
                # Include file structure data for directory-related actions
                if "contents" in response:
                    additional_data["fileStructure"] = response.get("contents", [])
                    additional_data["repoName"] = response.get("repo_name", "")
                    # Update context with current repository
                    if response.get("repo_name"):
                        self.update_context({"current_repo": response.get("repo_name")})
                elif "structure" in response:
                    additional_data["fileStructure"] = response.get("structure", [])
                    additional_data["repoName"] = response.get("repo_name", "")
                    # Update context with current repository
                    if response.get("repo_name"):
                        self.update_context({"current_repo": response.get("repo_name")})
                
            elif action_type == "read_file":
                additional_data["filePath"] = response.get("file_path", "")
                additional_data["fileContent"] = response.get("content", "")
                additional_data["repoName"] = response.get("repo_name", "")
                # Update context with current file
                if response.get("file_path"):
                    current_files = self.context.get("current_files", [])
                    if response.get("file_path") not in current_files:
                        current_files.append(response.get("file_path"))
                    self.update_context({"current_files": current_files})
                
            elif action_type == "chart":
                additional_data["chartContent"] = response.get("diagram", "")
                additional_data["repoName"] = response.get("repo_name", "")
            
            # Stream the formatted response back to the client with action type
            yield await self.format_sse_message(
                formatted + "\n\n", 
                action_type,
                additional_data
            )
            
            # Add a small delay to avoid overwhelming the client
            await asyncio.sleep(0.1)

            # Check if we're done
            if action_spec.get("done") == "True":
                print(f"{log_prefix}Task complete")
                self.short_term_memory.is_done = True
                summary = action_spec.get("summary", "")
                self.long_term_memory.append(summary)
                # Log completion in the conversation data
                self.data_logger.log_completion(summary)
                yield await self.format_sse_message(f"\n\n✅ Task completed: {summary}", "completion")
                break

async def cleanup_inactive_sessions():
    """Periodically clean up inactive sessions to free resources"""
    while True:
        await asyncio.sleep(3600)  # Check once per hour
        # In a production system, you'd want to track last activity time
        # and remove only truly inactive sessions
        # This is just a placeholder for now

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
