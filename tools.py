import os
import subprocess
from typing import List, Dict
from serpapi import GoogleSearch
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

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

def git_create_branch(branch_name: str) -> str:
    """
    Creates a new git branch.

    Args:
        branch_name (str): The name of the new branch.

    Returns:
        str: The output of the git branch command.
    """
    run_git_command(['checkout', 'main'])
    return run_git_command(['checkout', '-b', branch_name])

def git_commit_changes(commit_message: str) -> str:
    """
    Commits all changes in the current git repository.

    Args:
        commit_message (str): The commit message.

    Returns:
        str: The output of the git commit command.
    """
    run_git_command(['add', '.'])
    return run_git_command(['commit', '-m', commit_message])

def get_latest_version(dependency_name: str) -> str:
    """
    Gets the latest version of a dependency from PyPI using web search.

    Args:
        dependency_name (str): The name of the dependency.

    Returns:
        str: The latest version number, or 'unknown' if not found.
    """
    if not SERPER_API_KEY:
        return "unknown (SERPER_API_KEY not set)"

    params = {
        "engine": "google",
        "q": f"{dependency_name} pypi",
        "api_key": SERPER_API_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    if "organic_results" in results:
        for result in results["organic_results"]:
            if "pypi.org/project/" in result["link"]:
                # The title usually contains the version number
                title = result.get("title", "")
                parts = title.split()
                if len(parts) > 1:
                    # This is a bit fragile, it might be better to parse the page
                    # for now this is a good first step
                    return parts[1] 
    
    return "unknown"


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