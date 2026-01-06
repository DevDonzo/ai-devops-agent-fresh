from tools import discover_dependencies, get_latest_version, update_dependency_in_requirements, git_create_branch, git_commit_changes
from dotenv import load_dotenv

def main():
    """
    Main function for the AI DevOps & Security Automator.
    """
    print("Starting AI DevOps & Security Automator...")
    
    # Load environment variables
    load_dotenv()

    # Discover dependencies
    project_path = "." # Assuming the agent is run from the project root
    dependencies = discover_dependencies(project_path)
    
    if dependencies:
        print("\nDiscovered Dependencies:")
        for dep in dependencies:
            latest_version = get_latest_version(dep['name'])
            print(f"- {dep['name']}: current={dep['version']}, latest={latest_version}")
    else:
        print("\nNo dependencies found.")

    # Demonstrate dependency update
    print("\nDemonstrating dependency update...")
    dependency_to_update = "langchain"
    new_version = "1.2.1" # A simulated new version
    print(f"Attempting to update {dependency_to_update} to {new_version}...")
    
    updated = update_dependency_in_requirements("requirements.txt", dependency_to_update, new_version)
    
    if updated:
        print(f"Successfully updated {dependency_to_update}.")
        print("\nNew dependencies:")
        dependencies = discover_dependencies(".")
        for dep in dependencies:
            print(f"- {dep['name']}: {dep['version']}")
    else:
        print(f"Could not find {dependency_to_update} in requirements.txt")

    # Demonstrate Git Integration
    print("\nDemonstrating Git Integration...")
    branch_name = "feature/update-langchain"
    commit_message = f"Update {dependency_to_update} to {new_version}"

    try:
        print(f"Creating new branch: {branch_name}")
        git_create_branch(branch_name)
        print(f"Branch '{branch_name}' created and checked out.")

        print(f"Committing changes with message: '{commit_message}'")
        git_commit_changes(commit_message)
        print("Changes committed successfully.")
    except Exception as e:
        print(f"Git operation failed: {e}")


if __name__ == "__main__":
    main()