import os
import subprocess
import requests
from typing import List, Dict
from dotenv import load_dotenv
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

load_dotenv()

# Initialize SentenceTransformer model globally to avoid re-loading
# This model will be used for generating embeddings for code snippets.
try:
    _model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    print(f"Error loading SentenceTransformer model: {e}")
    _model = None # Handle case where model loading fails

def initialize_faiss_index(dimension: int):
    """
    Initializes a FAISS index.

    Args:
        dimension (int): The dimension of the embeddings.

    Returns:
        faiss.IndexFlatL2: The FAISS index object.
    """
    if _model is None:
        return None
    return faiss.IndexFlatL2(dimension)

def index_codebase_faiss(project_path: str, index: faiss.IndexFlatL2):
    """
    Indexes the project codebase into a FAISS index.

    Args:
        project_path (str): The path to the project directory.
        index (faiss.IndexFlatL2): The FAISS index to add data to.

    Returns:
        List[str]: A list of the documents (code lines) that were indexed.
    """
    if not _model or not index:
        print("SentenceTransformer model or FAISS index not loaded, cannot index codebase.")
        return []

    documents = []
    
    files_to_index = ["main.py", "tools.py"]
    for file_name in files_to_index:
        file_path = os.path.join(project_path, file_name)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Simple line-based chunking
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.strip(): # Only index non-empty lines
                    documents.append(line)
                        
    if documents:
        embeddings = _model.encode(documents)
        index.add(embeddings)
    
    print(f"Codebase from '{project_path}' indexed into FAISS.")
    return documents

def query_faiss_index(index: faiss.IndexFlatL2, documents: List[str], query_text: str, k: int = 5):
    """
    Queries a FAISS index for the most similar documents.

    Args:
        index (faiss.IndexFlatL2): The FAISS index to search.
        documents (List[str]): The list of documents corresponding to the index.
        query_text (str): The query text.
        k (int, optional): The number of similar documents to retrieve. Defaults to 5.

    Returns:
        List[str]: A list of the k most similar documents.
    """
    if not _model or not index:
        print("SentenceTransformer model or FAISS index not loaded, cannot query index.")
        return []
    
    query_embedding = _model.encode([query_text])
    distances, indices = index.search(query_embedding, k)

    results = []
    for i in indices[0]:
        if i < len(documents):
            results.append(documents[i])
    
    return results


def assess_dependency_update_risk(dependency_name: str, current_version: str,
                                   new_version: str, code_snippets: List[str]) -> Dict[str, str]:
    """
    Uses Google Gemini LLM to assess the risk of updating a dependency based on code usage.

    Args:
        dependency_name (str): Name of the dependency being updated
        current_version (str): Current version of the dependency
        new_version (str): Target version for the update
        code_snippets (List[str]): Code snippets showing how the dependency is used

    Returns:
        Dict[str, str]: Dictionary with keys:
            - 'risk_level': 'low', 'medium', or 'high'
            - 'explanation': Detailed explanation of the risk assessment
            - 'recommendation': Whether to proceed with the update ('proceed' or 'review')
    """
    # Fallback response in case of API failure
    fallback_response = {
        'risk_level': 'unknown',
        'explanation': 'Unable to assess risk due to LLM API failure. Manual review recommended.',
        'recommendation': 'review'
    }

    # Check if API key is available
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("Warning: GEMINI_API_KEY not found in environment. Skipping LLM risk assessment.")
        return fallback_response

    try:
        # Configure Gemini API
        genai.configure(api_key=gemini_api_key)

        # Use Gemini 2.5 Flash for fast, cost-effective analysis
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Construct the prompt
        code_context = "\n".join(code_snippets) if code_snippets else "No code snippets found."

        prompt = f"""You are a software engineering expert analyzing the risk of updating a Python dependency.

**Dependency Update Details:**
- Package: {dependency_name}
- Current Version: {current_version}
- Target Version: {new_version}

**Code Usage Context:**
The following code snippets show how this dependency is currently used in the codebase:

```
{code_context}
```

**Your Task:**
Analyze the risk of updating from version {current_version} to {new_version} based on:
1. The code usage patterns shown above
2. Known breaking changes between these versions (if any)
3. API stability and backwards compatibility
4. Complexity of the usage (simple imports vs deep integration)

**Response Format:**
Provide your assessment in this exact format:

RISK_LEVEL: [low|medium|high]
RECOMMENDATION: [proceed|review]
EXPLANATION: [2-3 sentences explaining your risk assessment, including specific concerns if any]

**Risk Level Guidelines:**
- LOW: Minor version update with no known breaking changes, simple usage patterns
- MEDIUM: Major version update OR moderate breaking changes OR moderate integration complexity
- HIGH: Major version with significant breaking changes OR deep integration OR deprecated APIs in use

Be conservative - when in doubt, assign a higher risk level."""

        # Call the Gemini API
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Parse the response
        risk_level = 'unknown'
        recommendation = 'review'
        explanation = response_text

        # Extract structured data from response
        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('RISK_LEVEL:'):
                risk_level = line.split(':', 1)[1].strip().lower()
            elif line.startswith('RECOMMENDATION:'):
                recommendation = line.split(':', 1)[1].strip().lower()
            elif line.startswith('EXPLANATION:'):
                explanation = line.split(':', 1)[1].strip()

        # Validate risk level
        if risk_level not in ['low', 'medium', 'high']:
            print(f"Warning: LLM returned unexpected risk level '{risk_level}', defaulting to 'unknown'")
            risk_level = 'unknown'
            recommendation = 'review'

        return {
            'risk_level': risk_level,
            'explanation': explanation,
            'recommendation': recommendation
        }

    except Exception as e:
        print(f"Error calling Gemini API for risk assessment: {e}")
        return fallback_response


def run_git_command(command: List[str]) -> str:
    """
    Runs a git command and returns its output.

    Args:
        command (List[str]): A list of strings representing the git command and its arguments.

    Returns:
        str: The standard output of the command.

    Raises:
        subprocess.CalledProcessError: If the git command fails.
    """
    try:
        result = subprocess.run(['git'] + command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {' '.join(command)}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise

def git_has_changes() -> bool:
    """
    Checks if there are any uncommitted changes in the git repository.

    Returns:
        bool: True if there are changes, False otherwise.
    """
    try:
        output = run_git_command(['status', '--porcelain'])
        return bool(output)
    except subprocess.CalledProcessError:
        return False # If git status fails, assume no changes or not a git repo

def git_branch_exists(branch_name: str) -> bool:
    """
    Checks if a git branch with the given name exists.

    Args:
        branch_name (str): The name of the branch to check.

    Returns:
        bool: True if the branch exists, False otherwise.
    """
    try:
        run_git_command(['show-ref', '--verify', f'refs/heads/{branch_name}'])
        return True
    except subprocess.CalledProcessError:
        return False

def git_create_branch(branch_name: str) -> str:
    """
    Creates a new git branch or checks out to an existing one.

    Args:
        branch_name (str): The name of the new branch.

    Returns:
        str: The output of the git command.
    """
    run_git_command(['checkout', 'main']) # Always go back to main first

    if git_branch_exists(branch_name):
        return run_git_command(['checkout', branch_name])
    else:
        return run_git_command(['checkout', '-b', branch_name])

def git_commit_changes(commit_message: str, files_to_add: List[str] = None) -> str:
    """
    Commits changes in the current git repository.

    Args:
        commit_message (str): The commit message.
        files_to_add (List[str], optional): A list of files to add to the staging area.
                                            If None, defaults to 'requirements.txt'.
    Returns:
        str: The output of the git commit command.
    """
    if files_to_add is None:
        files_to_add = ['requirements.txt'] # Default to only adding requirements.txt

    for file_path in files_to_add:
        run_git_command(['add', file_path])
        
    return run_git_command(['commit', '-m', commit_message])

def get_latest_version(dependency_name: str) -> str:
    """
    Gets the latest version of a dependency from PyPI.

    Args:
        dependency_name (str): The name of the dependency.

    Returns:
        str: The latest version number, or 'unknown' if not found.
    """
    try:
        response = requests.get(f"https://pypi.org/pypi/{dependency_name}/json")
        response.raise_for_status() # Raise an exception for HTTP errors
        data = response.json()
        return data["info"]["version"]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest version for {dependency_name} from PyPI: {e}")
        return "unknown"
    except KeyError:
        print(f"Could not find version info for {dependency_name} on PyPI.")
        return "unknown"

def check_vulnerabilities(dependency_name: str, version: str) -> List[Dict[str, str]]:
    """
    Checks for vulnerabilities for a given dependency and version using OSV.dev API.

    Args:
        dependency_name (str): The name of the dependency.
        version (str): The version of the dependency.

    Returns:
        List[Dict[str, str]]: A list of dictionaries, where each dictionary
                               represents a vulnerability with 'id', 'summary', and 'details' keys.
                               Returns an empty list if no vulnerabilities are found or an error occurs.
    """
    try:
        payload = {
            "package": {
                "ecosystem": "PyPI",
                "name": dependency_name
            },
            "version": version
        }
        response = requests.post("https://api.osv.dev/v1/query", json=payload)
        response.raise_for_status()

        data = response.json()
        vulnerabilities = []
        if "vulns" in data:
            for vuln in data["vulns"]:
                vulnerabilities.append({
                    "id": vuln.get("id", "N/A"),
                    "summary": vuln.get("summary", "No summary provided."),
                    "details": vuln.get("details", "No details provided.")
                })
        return vulnerabilities
    except requests.exceptions.RequestException as e:
        print(f"Error checking vulnerabilities for {dependency_name}@{version} from OSV.dev: {e}")
        return []
    except KeyError:
        print(f"Invalid response from OSV.dev for {dependency_name}@{version}.")
        return []


def parse_requirements_txt(file_path: str) -> List[Dict[str, str]]:
    """
    Parses a requirements.txt file and returns a list of dependencies.

    Args:
        file_path (str): The path to the requirements.txt file.

    Returns:
        List[Dict[str, str]]: A list of dictionaries, where each dictionary
                               represents a dependency with 'name' and 'version' keys.
    """
    dependencies = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Simple parsing for name==version format
                if '==' in line:
                    name, version = line.split('==')
                    dependencies.append({'name': name, 'version': version})
                # Simple parsing for name>=version format
                elif '>=' in line:
                    name, version = line.split('>=')
                    dependencies.append({'name': name, 'version': version})
                # Simple parsing for name<=version format
                elif '<=' in line:
                    name, version = line.split('<=')
                    dependencies.append({'name': name, 'version': version})
                # Simple parsing for name~=version format
                elif '~=' in line:
                    name, version = line.split('~=')
                    dependencies.append({'name': name, 'version': version})
                else:
                    dependencies.append({'name': line, 'version': 'any'})
    return dependencies

def discover_dependencies(project_path: str) -> List[Dict[str, str]]:
    """
    Discovers dependencies in a project by looking for dependency files.

    Args:
        project_path (str): The path to the project.

    Returns:
        List[Dict[str, str]]: A list of discovered dependencies.
    """
    requirements_file = os.path.join(project_path, 'requirements.txt')
    if os.path.exists(requirements_file):
        return parse_requirements_txt(requirements_file)
    else:
        return []

def update_dependency_in_requirements(file_path: str, dependency_name: str, new_version: str) -> bool:
    """
    Updates a dependency to a new version in a requirements.txt file.

    Args:
        file_path (str): The path to the requirements.txt file.
        dependency_name (str): The name of the dependency to update.
        new_version (str): The new version of the dependency.

    Returns:
        bool: True if the dependency was updated, False otherwise.
    """
    with open(file_path, 'r') as f:
        lines = f.readlines()

    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(dependency_name):
            lines[i] = f"{dependency_name}=={new_version}\n"
            updated = True
            break
    
    if updated:
        with open(file_path, 'w') as f:
            f.writelines(lines)

    return updated
