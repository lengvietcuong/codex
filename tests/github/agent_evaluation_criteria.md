# GitHub Agent Evaluation Criteria

## Core Capabilities

1. **Action Selection**: The agent should select the most appropriate action based on the user query.
2. **Context Awareness**: The agent should maintain context across a conversation and use previous information appropriately.
3. **Error Handling**: The agent should gracefully handle errors and provide helpful error messages.
4. **Completion Recognition**: The agent should correctly identify when a task is complete.

## Action-Specific Criteria

1. **Search**
   - Should use relevant search terms derived from the user query
   - Should present search results in a meaningful way

2. **Read File**
   - Should correctly identify and fetch the requested file
   - Should handle file not found scenarios properly

3. **Clone/Repository Navigation**
   - Should correctly clone repositories when needed
   - Should navigate repository structures effectively

4. **Directory Listing**
   - Should display directory contents in a clear, hierarchical manner
   - Should correctly handle path parameters

5. **Chart Generation**
   - Should create meaningful visualizations of repository structures

6. **Self Solve**
   - Should use self-solve when direct API actions aren't needed
   - Should provide clear, concise information to the user

## Test Case Success Criteria

For a test case to be considered successful:

1. The agent must follow the expected sequence of actions
2. Each action must produce a meaningful result
3. The agent must correctly identify when the task is complete
4. The final response should address the user's original query
