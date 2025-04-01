import json
import traceback
import time
import os
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from github_tools import GitHubTools, GithubException
from agent import ShortTermMemory
from prompt import goal_prompt, tool_prompt

class DataLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.conversations = []
        self.current_conversation = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_path = os.path.join(log_dir, f"conversation_log_{self.session_id}.json")
        
    def start_conversation(self, user_query):
        """Start a new conversation with a user query"""
        self.current_conversation = {
            "timestamp": datetime.now().isoformat(),
            "user_query": user_query,
            "interactions": []
        }
        self.conversations.append(self.current_conversation)
        self._save_to_file()
        
    def log_llm_interaction(self, prompt, response):
        """Log an interaction with the LLM"""
        if not self.current_conversation:
            return
            
        self.current_conversation["interactions"].append({
            "timestamp": datetime.now().isoformat(),
            "type": "llm",
            "prompt": prompt,
            "response": response
        })
        self._save_to_file()
        
    def log_tool_interaction(self, action, parameters, response):
        """Log an interaction with a GitHub tool"""
        if not self.current_conversation:
            return
            
        self.current_conversation["interactions"].append({
            "timestamp": datetime.now().isoformat(),
            "type": "tool",
            "action": action,
            "parameters": parameters,
            "response": response
        })
        self._save_to_file()
        
    def log_completion(self, summary):
        """Log the completion of a conversation"""
        if not self.current_conversation:
            return
            
        self.current_conversation["summary"] = summary
        self.current_conversation["completed_at"] = datetime.now().isoformat()
        self._save_to_file()
        
    def _save_to_file(self):
        """Save the current conversations to a JSON file"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.conversations, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving conversation log: {str(e)}")

class CodeAssistant:
    def __init__(self):
        self.gh_tools = GitHubTools()
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)
        self.short_term_memory = ShortTermMemory()
        self.long_term_memory = []
        self.tool_prompt = tool_prompt
        self.data_logger = DataLogger()

    def clean_json_response(self, response_text) -> str:
        # Remove markdown code block formatting if present
        if response_text.startswith("```"):
            # Remove the starting and ending triple backticks
            response_text = response_text.strip("`").strip()
            # Also remove the language identifier if present (like "json")
            if response_text.lower().startswith("json"):
                response_text = response_text[4:].strip()
        return response_text

    def get_goal(self, message):
        """Append a new message to the conversation history."""
        try:
            # Start a new conversation log with this user query
            self.data_logger.start_conversation(message)
            
            chain = goal_prompt | self.llm
            prompt_str = str(goal_prompt).replace("{task}", message)
            
            response = chain.invoke({
                "task": message
            })
            
            # Log the LLM interaction for the goal setting
            self.data_logger.log_llm_interaction(prompt_str, str(response.content))
            
            self.short_term_memory.goal = str(response.content)
            print("🎯 Agent goal:")
            print(response.content)
        except Exception as e:
            print(traceback.format_exc())
            err = {"error": str(e)}
            self.update_conversation(json.dumps(err))
    
    def clear_memory(self):
        """Clear the conversation history."""
        self.short_term_memory = ShortTermMemory()

    def update_conversation(self, message):
        """Append a new message to the conversation history."""
        self.short_term_memory.memory.append(message)

    def process_query(self, query):
        self.short_term_memory.is_done = False
        self.short_term_memory.goal = query

        while self.short_term_memory.is_done is False:
            action_spec = self.get_action()
            if action_spec.get("done") == "True":
                self.short_term_memory.is_done = True
                summary = action_spec.get("summary", "")
                self.long_term_memory.append(summary)
                # Log the completion of the conversation
                self.data_logger.log_completion(summary)
            raw_response = self.execute_action(action_spec)
            formatted = self.format_response(raw_response)
            print(formatted)

    def get_action(self, max_retries=3):
        """Use the tool prompt and LLM to decide on the best GitHub-related action."""
        retries = 0
        while retries < max_retries:
            try:
                chain = self.tool_prompt | self.llm
                
                # Prepare prompt for logging
                prompt_str = str(self.tool_prompt).replace("{goal}", self.short_term_memory.goal)
                prompt_str = prompt_str.replace("{conversation_history}", str(self.short_term_memory.memory))
                
                response = chain.invoke({
                    "goal": self.short_term_memory.goal,
                    "conversation_history": self.short_term_memory.memory,
                })
                
                # Log the LLM interaction
                self.data_logger.log_llm_interaction(prompt_str, str(response.content))
                
                # Check if response is empty
                if not response or not hasattr(response, 'content') or not response.content:
                    print("Warning: Empty response from LLM")
                    retries += 1
                    time.sleep(1)  # Wait a bit before retrying
                    continue
                
                # Debug the raw response
                print(f"Raw LLM response: {response.content[:100]}...")
                
                llm_instruction = self.clean_json_response(response.content)
                
                # Check if cleaned response is empty
                if not llm_instruction or llm_instruction.isspace():
                    print("Warning: Empty JSON after cleaning")
                    retries += 1
                    time.sleep(1)
                    continue
                
                try:
                    action_spec = json.loads(llm_instruction)
                    # Update conversation history with the LLM's decision
                    self.update_conversation(response.content)
                    return action_spec
                except json.JSONDecodeError as json_err:
                    print(f"JSON decode error: {json_err}")
                    print(f"Failed to parse: '{llm_instruction[:100]}...'")
                    retries += 1
                    time.sleep(1)
                    continue
                    
            except Exception as e:
                print(f"Error in get_action: {e}")
                print(traceback.format_exc())
                retries += 1
                time.sleep(1)
                
        # If we've exhausted all retries, return a fallback response
        fallback = {
            "action": "self_solve",
            "parameters": {
                "content": "I encountered an issue processing your request. Let me try a different approach."
            },
            "reason": "Fallback due to LLM response error"
        }
        
        err = {"error": f"Failed to get valid action after {max_retries} attempts"}
        self.update_conversation(json.dumps(err))
        return fallback

    def execute_action(self, action_spec):
        """Perform the chosen GitHub-related action and update conversation history."""
        try:
            action = action_spec.get("action")
            params = action_spec.get("parameters", {})
            response = {}

            # Log the beginning of the tool execution
            tool_response = None

            if action == "search":
                result = json.loads(self.gh_tools.search_repos(**params))
                if "results" in result:
                    self.search_history = result["results"]
                response = result
                tool_response = result

            elif action == "read_file":
                if "repo_name" not in params or "file_path" not in params:
                    response = {"error": "Missing repository name or file path"}
                else:
                    file_response = self.gh_tools.read_file(**params)
                    response = json.loads(file_response)
                    tool_response = response

            elif action == "clone":
                response = json.loads(self.gh_tools.clone_repo(**params))
                tool_response = response

            elif action == "repo_tree":
                if "repo_name" not in params:
                    response = {"error": "Missing repository name"}
                else:
                    tree_response = self.gh_tools.get_repo_tree(**params)
                    response = json.loads(tree_response)
                    tool_response = response

            elif action == "list_directory":
                if "repo_name" not in params:
                    response = {"error": "Missing repository name"}
                else:
                    params.setdefault("path", "")  # Default to root directory
                    dir_response = self.gh_tools.list_directory(**params)
                    response = json.loads(dir_response)
                    tool_response = response

            # New "chart" action to generate a Mermaid flowchart
            elif action == "chart":
                if "repo_name" not in params:
                    response = {"error": "Missing repository name"}
                else:
                    # Call the new generate_flowchart function from GitHubTools
                    diagram = self.gh_tools.generate_flowchart(params["repo_name"])
                    response = {"action": "chart", "diagram": diagram}
                    tool_response = response

            elif action == "self_solve":
                response = {"action": "self_solve", "summary": params.get("content", "")}
                tool_response = response

            else:
                response = {"error": "Unknown action"}
                tool_response = response

            # Log the tool interaction with parameters and response
            if tool_response:
                self.data_logger.log_tool_interaction(action, params, tool_response)

            self.update_conversation(json.dumps(response))
            return json.dumps(response, default=str)
        
        except GithubException as e:
            err_response = {"error": f"GitHub API Error ({e.status}): {e.data.get('message', 'Unknown error')}"}
            self.update_conversation(json.dumps(err_response))
            
            # Log the exception
            self.data_logger.log_tool_interaction(
                action_spec.get("action", "unknown"), 
                action_spec.get("parameters", {}), 
                err_response
            )
            
            return json.dumps(err_response)
        except Exception as e:
            err_response = {"error": str(e)}
            self.update_conversation(json.dumps(err_response))
            
            # Log the exception
            self.data_logger.log_tool_interaction(
                action_spec.get("action", "unknown"), 
                action_spec.get("parameters", {}), 
                err_response
            )
            
            return json.dumps(err_response)

    def format_response(self, raw_response):
        """Improved response formatting with directory structure and chart support."""
        try:
            response = json.loads(raw_response)
            if "error" in response:
                return f"🚨 Error: {response['error']}"

            action = response.get("action")
            
            if action == "search":
                output = ["🔍 Search Results:"]
                for idx, repo in enumerate(response.get("results", [])[:3], 1):
                    items = [f"{item['name']} ({'📁' if item['type'] == 'dir' else '📄'})" 
                             for item in repo.get("contents_preview", [])]
                    output.append(
                        f"{idx}. {repo.get('name', 'Unknown')} "
                        f"({repo.get('stars', 0)} ⭐)\n"
                        f"   {repo.get('description', 'No description')}\n"
                        f"   Contents: {', '.join(items)}"
                    )
                return "\n".join(output)
            
            elif action == "read_file":
                return (
                    f"📄 File: {response.get('file_path', 'Unknown')}\n"
                    f"🔗 Repo: {response.get('repo_name', 'Unknown')}\n\n"
                    f"{response.get('content', 'No content')[:500]}..."
                )
            
            elif action == "clone":
                return (
                    "📦 Repository cloned\n"
                    f"🔗 URL: {response.get('clone_url', 'Unknown')}\n"
                    f"📁 Path: {response.get('path', 'Temporary directory')}"
                )
            
            elif action == "repo_tree":
                structure = response.get("structure", [])
                repo_name = response.get("repo_name", "Unknown")
                total_items = len(structure)
                items = structure
                item_lines = [f"{'📁' if item['type'] == 'dir' else '📄'} {item['path']}" for item in items]
                return (
                    f"🌳 Repository Structure: {repo_name}\n"
                    f"Total items: {total_items}\n\n"
                    f"{'\n'.join(item_lines)}"
                )
            
            elif action == "list_directory":
                items = []
                for item in response.get("contents", []):
                    items.append(
                        f"{'📁' if item['type'] == 'dir' else '📄'} {item['name']}"
                        f" ({item.get('size', '?')} bytes)"
                    )
                return (
                    f"📂 Directory: {response.get('path', 'root')}\n"
                    f"🔗 Repo: {response.get('repo_name', 'Unknown')}\n\n" +
                    "\n".join(items[:15]) +
                    ("\n... (more items)" if len(items) > 15 else "")
                )

            elif action == "chart":
                # Return the raw Mermaid diagram code
                diagram = response.get("diagram", "")
                return f"📊 Mermaid Flowchart:\n\n{diagram}"
            
            elif action == "self_solve":
                return response.get("summary", "No summary provided")
            
            return f"Error: Unknown action '{action}'"
            
        except json.JSONDecodeError:
            return f"Invalid response format: {raw_response}"
        except Exception as e:
            return f"Formatting error: {str(e)}"
