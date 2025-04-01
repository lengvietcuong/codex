import json
import random
import os

def load_raw_data(input_file):
    """Load the raw GitHub data collected."""
    with open(input_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_training_examples(raw_data):
    """Convert raw GitHub data into training examples for fine-tuning."""
    training_examples = []
    
    for item in raw_data:
        repo_name = item['repo_name']
        file_path = item['file_path']
        content = item['content']
        
        # Generate different examples based on file content
        
        # Example 1: Read and understand a file
        training_examples.append({
            "messages": [
                {"role": "system", "content": "You are an agent that analyzes code from GitHub repositories."},
                {"role": "user", "content": f"I need to understand what this file does in the repository {repo_name}."},
                {"role": "assistant", "content": create_json_response("read_file", {"repo_name": repo_name, "file_path": file_path}, 
                                               f"Reading the file will help understand its functionality", "False")},
                {"role": "function", "name": "read_file", "content": content},
                {"role": "user", "content": "Can you explain what this file does?"},
                {"role": "assistant", "content": generate_explanation(content, file_path)}
            ]
        })
        
        # Example 2: Navigate repository structure
        training_examples.append({
            "messages": [
                {"role": "system", "content": "You are an agent that analyzes code from GitHub repositories."},
                {"role": "user", "content": f"I want to explore the structure of repository {repo_name}."},
                {"role": "assistant", "content": create_json_response("repo_tree", {"repo_name": repo_name}, 
                                               "Getting the repository structure will help understand its organization", "False")}
            ]
        })
        
    return training_examples

def create_json_response(action, parameters, reason, done="False", summary=None):
    """Create a properly formatted JSON response."""
    response = {
        "action": action,
        "parameters": parameters,
        "reason": reason,
        "done": done
    }
    
    if done == "True" and summary:
        response["summary"] = summary
    
    return json.dumps(response, indent=2)

def generate_explanation(content, file_path):
    """Generate a simple explanation based on file content."""
    # This is a placeholder. In a real implementation, you might use a smaller model
    # to generate explanations or create them manually.
    
    file_type = os.path.splitext(file_path)[1]
    
    if file_type == '.py':
        return f"This Python file contains {content.count('def')} function definitions and {content.count('class')} classes. It appears to be related to {guess_file_purpose(content)}."
    elif file_type == '.md':
        return f"This is a Markdown documentation file that explains {guess_file_purpose(content)}."
    else:
        return f"This file contains {len(content.split())} words and seems to be related to {guess_file_purpose(content)}."

def guess_file_purpose(content):
    """Make a simple guess about file purpose based on keywords."""
    keywords = {
        "API": ["api", "request", "endpoint", "response"],
        "Data Processing": ["data", "process", "transform", "pandas"],
        "UI/Frontend": ["component", "render", "ui", "interface"],
        "Testing": ["test", "assert", "mock", "pytest"],
        "Configuration": ["config", "setting", "environment", "setup"]
    }
    
    content_lower = content.lower()
    counts = {category: sum(1 for kw in kws if kw in content_lower) for category, kws in keywords.items()}
    
    if not any(counts.values()):
        return "general programming tasks"
    
    return max(counts.items(), key=lambda x: x[1])[0]

def save_training_data(data, output_file):
    """Save processed training data."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Training data saved to {output_file}")

if __name__ == "__main__":
    raw_data = load_raw_data("../data/raw/github_code_data.json")
    training_examples = create_training_examples(raw_data)
    save_training_data(training_examples, "../data/processed/training_data.jsonl")
    
    # Create a smaller validation set (10% of data)
    random.shuffle(training_examples)
    split_point = max(1, int(len(training_examples) * 0.1))
    validation_examples = training_examples[:split_point]
    save_training_data(validation_examples, "../data/processed/validation_data.jsonl")
    
    # Update the training data to exclude validation examples
    training_examples = training_examples[split_point:]
    save_training_data(training_examples, "../data/processed/training_data.jsonl")
