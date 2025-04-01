import os
import requests
import json
import time
import base64
from dotenv import load_dotenv

load_dotenv()

# GitHub API token
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Headers for GitHub API
headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def search_repositories(query, limit=10):
    """Search for repositories matching the query."""
    url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data['items'][:limit]
    else:
        print(f"Error searching repositories: {response.status_code}")
        return []

def get_repo_contents(repo_name, path=""):
    """Get contents of a repository at the specified path."""
    url = f"https://api.github.com/repos/{repo_name}/contents/{path}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting repo contents: {response.status_code}")
        return []

def get_file_content(repo_name, file_path):
    """Get content of a specific file in the repository."""
    url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data['type'] == 'file':
            content = base64.b64decode(data['content']).decode('utf-8')
            return content
        else:
            print("Not a file")
            return None
    else:
        print(f"Error getting file content: {response.status_code}")
        return None

def collect_data_from_repos(queries, file_extensions, max_repos=5, max_files_per_repo=20):
    """Collect code data from repositories based on queries."""
    all_data = []
    
    for query in queries:
        repos = search_repositories(f"{query} language:python", limit=max_repos)
        
        for repo in repos:
            repo_name = repo['full_name']
            print(f"Processing repository: {repo_name}")
            
            # Get repo tree to find all files
            repo_tree = get_repo_tree(repo_name)
            
            # Filter files by extension
            code_files = [item for item in repo_tree if any(item.endswith(ext) for ext in file_extensions)]
            code_files = code_files[:max_files_per_repo]  # Limit number of files
            
            for file_path in code_files:
                content = get_file_content(repo_name, file_path)
                if content:
                    all_data.append({
                        "repo_name": repo_name,
                        "file_path": file_path,
                        "content": content
                    })
            
            # Respect API rate limits
            time.sleep(2)
    
    return all_data

def get_repo_tree(repo_name):
    """Get all file paths in a repository."""
    url = f"https://api.github.com/repos/{repo_name}/git/trees/main?recursive=1"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if 'tree' in data:
            return [item['path'] for item in data['tree'] if item['type'] == 'blob']
    
    # Try with 'master' if 'main' fails
    url = f"https://api.github.com/repos/{repo_name}/git/trees/master?recursive=1"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if 'tree' in data:
            return [item['path'] for item in data['tree'] if item['type'] == 'blob']
    
    # Fallback to manual traversal
    return get_file_paths_manually(repo_name)

def get_file_paths_manually(repo_name, path=""):
    """Manually traverse repository to get file paths."""
    file_paths = []
    contents = get_repo_contents(repo_name, path)
    
    for item in contents:
        if item['type'] == 'file':
            file_paths.append(item['path'])
        elif item['type'] == 'dir':
            file_paths.extend(get_file_paths_manually(repo_name, item['path']))
    
    return file_paths

def save_data(data, output_file):
    """Save collected data to a JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Data saved to {output_file}")

if __name__ == "__main__":
    queries = [
        "code analysis tool",
        "github automation",
        "repository analyzer"
    ]
    file_extensions = ['.py', '.md', '.txt', '.json']
    
    data = collect_data_from_repos(queries, file_extensions)
    save_data(data, "../data/raw/github_code_data.json")
