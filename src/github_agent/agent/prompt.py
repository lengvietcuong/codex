from langchain_core.prompts import ChatPromptTemplate

goal_prompt = ChatPromptTemplate.from_template("""
You are an agent that can interact with a GitHub API to search for repositories, read files, and clone repositories.
you need to define the goal for the following task:
{task}
                                                   
You should only return a string that describes the goal of the task.
""")

tool_prompt = ChatPromptTemplate.from_template(
    """Analyze the GitHub-related query and select the best action.
Available actions:
1. search - Find repositories (requires 'query')
2. read_file - Read a specific file (requires 'repo_name', 'file_path')
3. clone - Clone repository (requires 'clone_url')
4. repo_tree - Get complete repository structure (requires 'repo_name')
5. list_directory - List directory contents (requires 'repo_name', 'path' [optional])
6. chart - Generate a Mermaid flowchart for the repository (requires 'repo_name')
7. self_solve - Tasks that can be solved without API calls (requires 'content')

Conversation history: {conversation_history}
Task goal: {goal}

RESPONSE FORMAT: Respond with valid JSON in this exact format:
{{
    "action": "search|read_file|clone|repo_tree|list_dir|chart|self_solve",
    "parameters": {{
        // Action-specific parameters
    }},
    "reason": "explanation",
    "done": "True|False",
    "summary": "if done=True, progress summary"
}}"""
)
