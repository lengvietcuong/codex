import asyncio
import json
import time
import uuid
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Add the parent directory to sys.path to import the agent module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.assistant import CodeAssistant

class TestCase:
    """Represents a test case for the GitHub agent."""
    
    def __init__(self, 
                 name: str, 
                 query: str, 
                 expected_actions: List[Dict[str, Any]],
                 description: str = ""):
        """
        Initialize a test case.
        
        Args:
            name: A unique identifier for the test case
            query: The user query to test
            expected_actions: List of expected actions with their parameters
            description: Description of what the test is checking
        """
        self.name = name
        self.query = query
        self.expected_actions = expected_actions
        self.description = description
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert the test case to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "query": self.query,
            "expected_actions": self.expected_actions
        }
        
class TestResult:
    """Represents the result of running a test case."""
    
    def __init__(self, 
                 test_case: TestCase, 
                 passed: bool, 
                 actual_actions: List[Dict[str, Any]],
                 errors: List[str] = None,
                 execution_time: float = 0.0):
        """
        Initialize a test result.
        
        Args:
            test_case: The test case that was run
            passed: Whether the test passed
            actual_actions: The actions the agent actually took
            errors: Any errors that occurred during testing
            execution_time: How long the test took to run in seconds
        """
        self.test_case = test_case
        self.passed = passed
        self.actual_actions = actual_actions
        self.errors = errors or []
        self.execution_time = execution_time
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert the test result to a dictionary."""
        return {
            "test_case": self.test_case.to_dict(),
            "passed": self.passed,
            "actual_actions": self.actual_actions,
            "errors": self.errors,
            "execution_time": self.execution_time
        }

class AgentTestRunner:
    """Runs tests against the GitHub agent."""
    
    def __init__(self, output_path: str = None):
        """
        Initialize the test runner.
        
        Args:
            output_path: Path to write test results to
        """
        self.output_path = output_path or f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    def extract_actions_from_conversation(self, assistant: CodeAssistant) -> List[Dict[str, Any]]:
        """
        Extract actions taken from the assistant's conversation history.
        
        Args:
            assistant: The assistant instance that processed a query
            
        Returns:
            A list of actions that the agent took
        """
        actions = []
        # Process the conversation history to extract actions
        for message in assistant.short_term_memory.memory:
            try:
                # Try to parse message as JSON
                if isinstance(message, str) and message.strip().startswith("{"):
                    data = json.loads(message)
                    
                    # Check if this message represents an action
                    if "action" in data:
                        action_type = data.get("action")
                        # Skip thinking steps and internal messages
                        if action_type in ["search", "read_file", "clone", "repo_tree", 
                                          "list_directory", "chart", "self_solve"]:
                            
                            # Extract parameters
                            parameters = {}
                            if action_type == "search" and "results" in data:
                                parameters["repositories"] = data.get("results", [])
                            elif action_type in ["list_directory", "repo_tree", "clone"]:
                                if "contents" in data:
                                    parameters["fileStructure"] = data.get("contents", [])
                                elif "structure" in data:
                                    parameters["fileStructure"] = data.get("structure", [])
                                parameters["repoName"] = data.get("repo_name", "")
                            elif action_type == "read_file":
                                parameters["filePath"] = data.get("file_path", "")
                                parameters["repoName"] = data.get("repo_name", "")
                            elif action_type == "chart":
                                parameters["chartContent"] = data.get("diagram", "")
                                parameters["repoName"] = data.get("repo_name", "")
                            
                            # Extract content based on action type
                            content = ""
                            if action_type == "self_solve":
                                content = data.get("parameters", "")
                                if(content):
                                    content = content.get("content", "")
                            else:
                                # For non-self_solve actions, use reason field instead
                                content = data.get("reason", "")
                                
                            actions.append({
                                "action": action_type,
                                "content": content,
                                "parameters": parameters
                            })
            except json.JSONDecodeError:
                # Not a JSON message, skip it
                continue
            except Exception as e:
                print(f"Error processing message: {str(e)}")
                continue
                
        return actions
        
    async def run_test(self, test_case: TestCase) -> TestResult:
        """
        Run a single test case.
        
        Args:
            test_case: The test case to run
            
        Returns:
            The result of running the test
        """
        print(f"Running test: {test_case.name}")
        
        # Create a new assistant for this test
        assistant = CodeAssistant()
        
        # Track execution time
        start_time = time.time()
        errors = []
        
        # Process the query
        try:
            # The CodeAssistant.process_query method doesn't return anything,
            # it updates conversation history internally
            assistant.process_query(test_case.query)
            
            # Extract actions from the assistant's conversation history
            actual_actions = self.extract_actions_from_conversation(assistant)
        except Exception as e:
            errors.append(f"Exception during test execution: {str(e)}")
            actual_actions = []
        
        execution_time = time.time() - start_time
        
        # Determine if the test passed
        passed = self._validate_actions(test_case.expected_actions, actual_actions, errors)
        
        print(f"Test {test_case.name} {'passed' if passed else 'failed'}")
        if errors:
            for error in errors:
                print(f"  - {error}")
        
        return TestResult(
            test_case=test_case,
            passed=passed,
            actual_actions=actual_actions,
            errors=errors,
            execution_time=execution_time
        )
    
    def _validate_actions(self, 
                          expected_actions: List[Dict[str, Any]], 
                          actual_actions: List[Dict[str, Any]], 
                          errors: List[str]) -> bool:
        """
        Validate that the actual actions match the expected actions.
        
        Args:
            expected_actions: List of expected actions
            actual_actions: List of actual actions
            errors: List to append errors to
            
        Returns:
            True if the actions match, False otherwise
        """
        # Check if we have the right number of actions
        if len(actual_actions) != len(expected_actions):
            errors.append(f"Expected {len(expected_actions)} actions, got {len(actual_actions)}")
            return False
        
        # Check each action
        for i, (expected, actual) in enumerate(zip(expected_actions, actual_actions)):
            # Check the action type
            if expected["action"] != actual["action"]:
                errors.append(f"Action {i+1}: Expected action '{expected['action']}', got '{actual['action']}'")
                return False
            
            # For search actions, check that we searched for the right thing
            if expected["action"] == "search" and "query" in expected.get("parameters", {}):
                actual_repos = actual.get("parameters", {}).get("repositories", [])
                if not actual_repos:
                    errors.append(f"Action {i+1}: Search returned no repositories")
                    return False
            
            # For read_file actions, check that we read the right file
            if expected["action"] == "read_file":
                expected_file = expected.get("parameters", {}).get("file_path", "")
                actual_file = actual.get("parameters", {}).get("filePath", "")
                if expected_file and expected_file != actual_file:
                    errors.append(f"Action {i+1}: Expected to read file '{expected_file}', got '{actual_file}'")
                    return False
        
        return True
    
    async def run_tests(self, test_cases: List[TestCase]) -> List[TestResult]:
        """
        Run multiple test cases.
        
        Args:
            test_cases: List of test cases to run
            
        Returns:
            List of test results
        """
        results = []
        
        for test_case in test_cases:
            result = await self.run_test(test_case)
            results.append(result)
            
            # Add a small delay between tests
            await asyncio.sleep(1)
        
        return results
    
    def save_results(self, results: List[TestResult]) -> None:
        """
        Save test results to a file.
        
        Args:
            results: List of test results to save
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        
        # Convert results to dictionaries
        result_dicts = [result.to_dict() for result in results]
        
        # Calculate overall statistics
        total_tests = len(results)
        passed_tests = sum(1 for result in results if result.passed)
        pass_rate = passed_tests / total_tests if total_tests > 0 else 0
        
        # Create the final report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "pass_rate": pass_rate,
            "results": result_dicts
        }
        
        # Write the report to file
        with open(self.output_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"Test results saved to {self.output_path}")
        print(f"Pass rate: {passed_tests}/{total_tests} ({pass_rate:.2%})")

# Define test cases
def get_test_cases() -> List[TestCase]:
    """Define the test cases to run."""
    return [
        TestCase(
            name="search_python_libraries",
            description="Test if agent can search for Python libraries",
            query="Find popular Python web frameworks",
            expected_actions=[
                {"action": "search", "parameters": {"query": "python web framework"}},
                {"action": "self_solve"}
            ]
        ),
        TestCase(
            name="read_readme_file",
            description="Test if agent can read a README file from a repository",
            query="Show me the README of the Flask project",
            expected_actions=[
                {"action": "search", "parameters": {"query": "flask"}},
                {"action": "read_file", "parameters": {"repo_name": "pallets/flask", "file_path": "README.md"}}
            ]
        ),
        TestCase(
            name="explore_repository_structure",
            description="Test if agent can explore a repository structure",
            query="Show me the structure of the Django repository",
            expected_actions=[
                {"action": "search", "parameters": {"query": "django"}},
                {"action": "repo_tree", "parameters": {"repo_name": "django/django"}}
            ]
        ),
        TestCase(
            name="search_and_read_specific_file",
            description="Test if agent can search for a repository and read a specific file",
            query="Show me the setup.py file from the requests library",
            expected_actions=[
                {"action": "search", "parameters": {"query": "requests library"}},
                {"action": "read_file", "parameters": {"repo_name": "psf/requests", "file_path": "setup.py"}}
            ]
        ),
        TestCase(
            name="generate_repository_diagram",
            description="Test if agent can generate a diagram for a repository",
            query="Create a diagram of the PyTorch project structure",
            expected_actions=[
                {"action": "search", "parameters": {"query": "pytorch"}},
                {"action": "chart", "parameters": {"repo_name": "pytorch/pytorch"}}
            ]
        ),
        TestCase(
            name="search_and_explore_directory",
            description="Test if agent can search and explore a specific directory",
            query="Show me the tests directory in the NumPy project",
            expected_actions=[
                {"action": "search", "parameters": {"query": "numpy"}},
                {"action": "list_directory", "parameters": {"repo_name": "numpy/numpy", "path": "tests"}}
            ]
        ),
        TestCase(
            name="contextual_file_browsing",
            description="Test if agent can maintain context when browsing files",
            query="First show me the scikit-learn repository, then its examples directory",
            expected_actions=[
                {"action": "search", "parameters": {"query": "scikit-learn"}},
                {"action": "repo_tree", "parameters": {"repo_name": "scikit-learn/scikit-learn"}},
                {"action": "list_directory", "parameters": {"repo_name": "scikit-learn/scikit-learn", "path": "examples"}}
            ]
        ),
        TestCase(
            name="question_about_popular_projects",
            description="Test if agent can answer general questions about GitHub projects",
            query="What are the most popular machine learning repositories?",
            expected_actions=[
                {"action": "search", "parameters": {"query": "machine learning"}},
                {"action": "self_solve"}
            ]
        ),
        TestCase(
            name="find_and_explain_code",
            description="Test if agent can find and explain code in repositories",
            query="Explain how the JWT encoding works in the PyJWT library",
            expected_actions=[
                {"action": "search", "parameters": {"query": "pyjwt"}},
                {"action": "read_file", "parameters": {"repo_name": "jpadilla/pyjwt", "file_path": "jwt/api_jwt.py"}},
                {"action": "self_solve"}
            ]
        ),
        TestCase(
            name="compare_libraries",
            description="Test if agent can compare different libraries",
            query="Compare FastAPI and Flask web frameworks",
            expected_actions=[
                {"action": "search", "parameters": {"query": "fastapi"}},
                {"action": "read_file", "parameters": {"repo_name": "tiangolo/fastapi", "file_path": "README.md"}},
                {"action": "search", "parameters": {"query": "flask"}},
                {"action": "read_file", "parameters": {"repo_name": "pallets/flask", "file_path": "README.md"}},
                {"action": "self_solve"}
            ]
        )
    ]

async def main():
    """Run the tests and save the results."""
    test_cases = get_test_cases()
    
    # Create the test runner
    runner = AgentTestRunner(output_path="d:/scrape_github_agent/tests/test_results.json")
    
    # Run the tests
    results = await runner.run_tests(test_cases)
    
    # Save the results
    runner.save_results(results)

if __name__ == "__main__":
    asyncio.run(main())
