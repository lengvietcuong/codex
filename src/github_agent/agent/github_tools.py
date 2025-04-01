import os
import ast
import json
import tempfile
import subprocess
import logging
from collections import defaultdict
from github import Github, GithubException, Auth

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('github_tools')

class GitHubTools:
    def __init__(self):
        self.gh_token = os.getenv("GITHUB_TOKEN")
        if not self.gh_token:
            raise ValueError("Missing GITHUB_TOKEN environment variable")
        
        # Updated authentication using Auth.Token
        auth = Auth.Token(self.gh_token)
        self.client = Github(auth=auth)

    def get_repo_tree(self, repo_name):
        """Get complete repository file structure using Git Tree"""
        try:
            repo = self.client.get_repo(repo_name)
            tree = repo.get_git_tree(sha="main", recursive=True)
            structure = []
            for element in tree.tree:
                structure.append({
                    "path": element.path,
                    "type": "dir" if element.type == "tree" else "file",
                    "size": element.size,
                    "sha": element.sha
                })
            return json.dumps({
                "action": "repo_tree",
                "repo_name": repo_name,
                "structure": structure
            })
            
        except GithubException as e:
            return json.dumps({"error": f"GitHub API Error: {e.data.get('message', str(e))}"})

    def list_directory(self, repo_name, path=""):
        """List contents of a specific directory"""
        try:
            repo = self.client.get_repo(repo_name)
            contents = repo.get_contents(path)
            
            items = []
            if isinstance(contents, list):
                for item in contents:
                    items.append({
                        "name": item.name,
                        "path": item.path,
                        "type": "dir" if item.type == "dir" else "file",
                        "size": item.size,
                        "sha": item.sha,
                        "html_url": item.html_url
                    })
            else:
                items.append({
                    "name": contents.name,
                    "path": contents.path,
                    "type": "dir" if contents.type == "dir" else "file",
                    "size": contents.size,
                    "sha": contents.sha,
                    "html_url": contents.html_url
                })
                
            return json.dumps({
                "action": "list_directory",
                "repo_name": repo_name,
                "path": path,
                "contents": items
            })
            
        except GithubException as e:
            return json.dumps({"error": f"GitHub API Error: {e.data.get('message', str(e))}"})

    def search_repos(self, query, max_results=3):
        """Search repositories with directory structure preview"""
        try:
            repos = self.client.search_repositories(
                query=query,
                sort="stars",
                order="desc"
            )
            
            results = []
            for repo in repos[:max_results]:
                try:
                    # Get first 5 items (files + directories) in root
                    contents = repo.get_contents("")[:5]
                    items = []
                    for item in contents:
                        items.append({
                            "name": item.name,
                            "type": "dir" if item.type == "dir" else "file",
                            "path": item.path
                        })
                except GithubException:
                    items = []
                
                results.append({
                    "name": repo.full_name,
                    "description": repo.description or "No description",
                    "stars": repo.stargazers_count,
                    "contents_preview": items,
                    "clone_url": repo.clone_url,
                    "html_url": repo.html_url,
                    "language": repo.language or "Unknown",
                    "last_updated": repo.updated_at.isoformat() if repo.updated_at else None,
                    "repo_type": "repository"  # Explicitly mark as a repository for UI
                })
                
            return json.dumps({"action": "search", "results": results})
            
        except GithubException as e:
            return json.dumps({"error": f"GitHub API Error: {e.data.get('message', str(e))}"})
    def read_file(self, repo_name, file_path):
        """Read file with better error handling and detailed diagnostics"""
        logger.info(f"Reading file {repo_name}/{file_path}")
        
        try:
            # Handle potential duplicate repository name (e.g., "browser-use/browser-use")
            if "/" in repo_name and repo_name.count("/") > 1:
                # More than one slash - might be a problem
                parts = repo_name.split("/")
                if len(parts) > 3:
                    # Format could be like "owner/repo/owner/repo" - clean it up
                    repo_name = f"{parts[0]}/{parts[1]}"
                    file_path = "/".join(parts[2:]) + "/" + file_path
                    logger.info(f"Reformatted path: repo={repo_name}, file={file_path}")
            
            # Get the repo
            try:
                repo = self.client.get_repo(repo_name)
                logger.info(f"Successfully found repo: {repo_name}")
            except GithubException as e:
                logger.error(f"GitHub API Error finding repo {repo_name}: {str(e)}")
                if e.status == 404:
                    return json.dumps({
                        "error": f"Repository not found: {repo_name}. Please check the repository name."
                    })
                else:
                    return json.dumps({
                        "error": f"GitHub API Error: {e.data.get('message', str(e))}"
                    })
            
            # Get the file content
            try:
                file_content = repo.get_contents(file_path)
                logger.info(f"Successfully found file: {file_path}")
                
                if isinstance(file_content, list):
                    return json.dumps({"error": f"{file_path} is a directory, not a file"})
            except GithubException as e:
                logger.error(f"GitHub API Error finding file {file_path}: {str(e)}")
                if e.status == 404:
                    # Try alternative paths if file not found
                    alt_file_paths = self._get_alternative_paths(file_path)
                    for alt_path in alt_file_paths:
                        try:
                            logger.info(f"Trying alternative path: {alt_path}")
                            file_content = repo.get_contents(alt_path)
                            if not isinstance(file_content, list):
                                logger.info(f"Successfully found file at alternative path: {alt_path}")
                                file_path = alt_path  # Update file_path to the working one
                                break
                        except GithubException:
                            continue
                    else:
                        # None of the alternatives worked
                        return json.dumps({
                            "error": f"File not found: {file_path}. Please check the file path."
                        })
                else:
                    return json.dumps({
                        "error": f"GitHub API Error: {e.data.get('message', str(e))}"
                    })
            
            # Try to decode the file content
            try:
                content = file_content.decoded_content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = file_content.decoded_content.decode('latin-1')
                except UnicodeDecodeError:
                    return json.dumps({
                        "error": f"Unable to decode file content - this might be a binary file."
                    })
            
            return json.dumps({
                "action": "read_file",
                "content": content,
                "file_path": file_path,
                "repo_name": repo_name,
                "size": file_content.size,
                "file_type": file_path.split('.')[-1] if '.' in file_path else "unknown"
            })
            
        except Exception as e:
            logger.exception(f"Unexpected error reading file {repo_name}/{file_path}")
            return json.dumps({
                "error": f"Error reading file: {str(e)}"
            })
    
    def _get_alternative_paths(self, file_path):
        """Generate alternative paths to try if the primary path fails"""
        alternatives = []
        
        # Try with different path separators
        path_with_slashes = file_path.replace('\\', '/')
        if path_with_slashes != file_path:
            alternatives.append(path_with_slashes)
        
        # Try removing any leading slashes
        if file_path.startswith('/') or file_path.startswith('\\'):
            alternatives.append(file_path[1:])
        
        # Try with lowercase filename (common issue)
        parts = file_path.rsplit('/', 1)
        if len(parts) > 1:
            alternatives.append(f"{parts[0]}/{parts[1].lower()}")
        
        # Try with changes to common path prefixes
        if not file_path.startswith(('src/', 'lib/')):
            alternatives.extend([f"src/{file_path}", f"lib/{file_path}"])
        
        return alternatives

    def clone_repo(self, clone_url):
        """Clone repository to the agent's directory"""
        try:
            # Extract repo name from clone URL
            repo_name = clone_url.split('/')[-1].replace('.git', '')
            # Create clone path in the agent's directory
            clone_path = os.path.join('./', 'cloned_repos', repo_name)
            
            # Create cloned_repos directory if it doesn't exist
            os.makedirs(os.path.join('./', 'cloned_repos'), exist_ok=True)
            
            # Remove directory if it already exists
            if os.path.exists(clone_path):
                if os.name == 'nt':  # Windows
                    subprocess.run(['rmdir', '/s', '/q', clone_path], check=True)

            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, clone_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            
            return json.dumps({
                "action": "clone",
                "path": clone_path,
                "clone_url": clone_url
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    # --- New Function: Generate Mermaid Flowchart without Downloading the Repo ---
    def generate_flowchart(self, repo_name):
        """
        Generate a Mermaid flowchart for all Python files in a repository
        by using the GitHub API to read file contents (without downloading the repo).
        The flowchart groups nodes by file (as subgraphs) and shows classes,
        functions, methods, and the dependencies (calls/instantiates) between them.
        """
        # --- Helper functions defined locally ---
        def parse_python_content(content):
            """Parse Python code (string) to capture classes, methods, and standalone functions."""
            try:
                tree = ast.parse(content)
            except SyntaxError:
                return []
            entities = []
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    methods = []
                    for subnode in node.body:
                        if isinstance(subnode, ast.FunctionDef):
                            visibility = '+' if not subnode.name.startswith('_') else '-'
                            methods.append(f"{visibility}{subnode.name}()")
                    entities.append(('class', node.name, methods))
                elif isinstance(node, ast.FunctionDef):
                    entities.append(('function', node.name, []))
            return entities

        def find_dependency_edges_content(content, default_context, class_set):
            """
            Traverse the AST of Python code (string) to find dependency edges.
            Returns a list of edges in the form (caller, callee, label).
            """
            try:
                tree = ast.parse(content)
            except SyntaxError:
                return []
            var_to_class = {}
            class DependencyVisitor(ast.NodeVisitor):
                def __init__(self, default_context, var_to_class, class_set):
                    self.func_stack = [default_context]
                    self.edges = []
                    self.var_to_class = var_to_class
                    self.class_set = class_set
                    self.class_stack = []
                def visit_Assign(self, node):
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                        class_name = node.value.func.id
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                self.var_to_class[target.id] = class_name
                    self.generic_visit(node)
                def visit_ClassDef(self, node):
                    self.class_stack.append(node.name)
                    self.generic_visit(node)
                    self.class_stack.pop()
                def visit_FunctionDef(self, node):
                    if self.class_stack:
                        full_name = self.class_stack[-1] + "." + node.name
                    else:
                        full_name = node.name
                    self.func_stack.append(full_name)
                    self.generic_visit(node)
                    self.func_stack.pop()
                def visit_Call(self, node):
                    current_context = self.func_stack[-1] if self.func_stack else default_context
                    if isinstance(node.func, ast.Name):
                        if node.func.id in self.class_set:
                            callee = node.func.id
                            label = "instantiates"
                        else:
                            callee = node.func.id
                            label = "calls"
                    elif isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name):
                            caller_name = node.func.value.id
                            method = node.func.attr
                            if caller_name in self.var_to_class:
                                callee = self.var_to_class[caller_name] + "." + method
                            else:
                                callee = caller_name + "." + method
                            label = "calls"
                        else:
                            callee = "unknown"
                            label = "calls"
                    else:
                        callee = "unknown"
                        label = "calls"
                    self.edges.append((current_context, callee, label))
                    self.generic_visit(node)
            visitor = DependencyVisitor(default_context, var_to_class, class_set)
            visitor.visit(tree)
            return visitor.edges

        # --- Begin Flowchart Generation ---
        tree_json = self.get_repo_tree(repo_name)
        tree_data = json.loads(tree_json)
        all_files = []
        for element in tree_data.get("structure", []):
            if element["type"] == "file" and element["path"].endswith(".py"):
                all_files.append(element["path"])

        entities_by_file = defaultdict(list)
        global_entities = {}  # Map identifier -> (file_stem, node_id)
        relationships = []  # List of tuples (source_node, target_node, label)

        # First pass: Collect all entities
        for file_path in all_files:
            file_stem = os.path.splitext(os.path.basename(file_path))[0]
            module_node = f"{file_stem}_module"
            if module_node not in global_entities:
                entities_by_file[file_stem].append({
                    'node_id': module_node,
                    'name': module_node,
                    'type': 'module'
                })
                global_entities[module_node] = (file_stem, module_node)

            read_result = self.read_file(repo_name, file_path)
            file_data = json.loads(read_result)
            if "error" in file_data:
                continue
            content = file_data.get("content", "")
            if not content:
                continue

            for entity_type, name, methods in parse_python_content(content):
                node_id = f"{file_stem}_{name}"
                if node_id not in global_entities:
                    entities_by_file[file_stem].append({
                        'node_id': node_id,
                        'name': name,
                        'type': entity_type
                    })
                    global_entities[name] = (file_stem, node_id)
                if entity_type == 'class':
                    for method_sig in methods:
                        method_name = method_sig[1:].split('(')[0]
                        method_node_id = f"{node_id}_{method_name}"
                        entities_by_file[file_stem].append({
                            'node_id': method_node_id,
                            'name': method_name,
                            'type': 'method'
                        })
                        global_entities[f"{name}.{method_name}"] = (file_stem, method_node_id)
                        relationships.append((node_id, method_node_id, "contains"))

        # Second pass: Extract dependency edges from file content.
        for file_path in all_files:
            file_stem = os.path.splitext(os.path.basename(file_path))[0]
            default_context = f"{file_stem}_module"
            if file_stem == "cli_interface":
                for ent in entities_by_file[file_stem]:
                    if ent['type'] == 'function' and ent['name'] == "main":
                        default_context = ent['node_id']
                        break
            read_result = self.read_file(repo_name, file_path)
            file_data = json.loads(read_result)
            if "error" in file_data:
                continue
            content = file_data.get("content", "")
            if not content:
                continue
            class_set = {ent['name'] for ent in entities_by_file[file_stem] if ent['type'] == 'class'}
            edges = find_dependency_edges_content(content, default_context, class_set)
            for (source, target, label) in edges:
                if source in global_entities and target in global_entities:
                    source_node = global_entities[source][1]
                    target_node = global_entities[target][1]
                    relationships.append((source_node, target_node, label))

        # Build Mermaid flowchart output.
        flowchart_lines = [
            "%%{init: {",
            "  'theme': 'base',",
            "  'themeVariables': {",
            "    'primaryColor': '#fff',",
            "    'primaryBorderColor': '#000',",
            "    'lineColor': '#000'",
            "  },",
            "  'flowchart': {",
            "    'useMaxWidth': false,",
            "    'htmlLabels': true,",
            "    'nodeSpacing': 50,",
            "    'rankSpacing': 100",
            "  }",
            "}}%%",
            "flowchart TD"
        ]
        for file_stem, ents in entities_by_file.items():
            flowchart_lines.append(f"subgraph {file_stem}")
            for ent in ents:
                if ent['type'] == 'module':
                    flowchart_lines.append(f"    {ent['node_id']}[/\"📦 {file_stem}\"/]")
                elif ent['type'] == 'class':
                    flowchart_lines.append(f"    {ent['node_id']}[\"Class: {ent['name']}\"]")
                elif ent['type'] == 'function':
                    flowchart_lines.append(f"    {ent['node_id']}(\"Function: {ent['name']}\")")
                elif ent['type'] == 'method':
                    flowchart_lines.append(f"    {ent['node_id']}>\"Method: {ent['name']}\"]")
            flowchart_lines.append("end")
        # Example styling for known nodes.
        flowchart_lines.extend([
            "style cli_interface_module fill:#f0f8ff,stroke:#4682b4",
            "style code_agent_CodeAssistant fill:#f0fff0,stroke:#3cb371",
            "style cli_interface_main fill:#fff0f5,stroke:#ff69b4",
            "style code_agent_CodeAssistant_clean_json_response fill:#fffff0,stroke:#daa520"
        ])
        edge_colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEEAD",
            "#FF9F68", "#D4A5A5", "#79B473", "#6C5B7B", "#F8B195"
        ]
        for idx, (source, target, label) in enumerate(relationships):
            color = edge_colors[idx % len(edge_colors)]
            flowchart_lines.append(f"{source} --> |\"{label}\"| {target}")
            flowchart_lines.append(f"linkStyle {idx} stroke:{color},stroke-width:2px")
        return "\n".join(flowchart_lines)
