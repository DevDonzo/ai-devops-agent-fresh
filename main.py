from tools import discover_dependencies, get_latest_version, update_dependency_in_requirements, git_create_branch, git_commit_changes, check_vulnerabilities, run_git_command, initialize_faiss_index, index_codebase_faiss, query_faiss_index, assess_dependency_update_risk
from dotenv import load_dotenv
import os
import shutil # Import shutil for rmtree

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

            # Check for vulnerabilities for current version
            if dep['version'] != 'any': # Only check if a specific version is defined
                vulnerabilities = check_vulnerabilities(dep['name'], dep['version'])
                if vulnerabilities:
                    print(f"  🚨 Vulnerabilities found for {dep['name']}@{dep['version']}:")
                    for vuln in vulnerabilities:
                        print(f"    - ID: {vuln['id']}")
                        print(f"      Summary: {vuln['summary']}")
                else:
                    print(f"  ✅ No vulnerabilities found for {dep['name']}@{dep['version']}.")
            else:
                print(f"  Skipping vulnerability check for {dep['name']} (version 'any').")
    else:
        print("\nNo dependencies found.")

    # Initialize FAISS index and index the codebase
    print("\nInitializing FAISS index...")
    # The dimension of the embeddings from 'all-MiniLM-L6-v2' is 384
    faiss_index = initialize_faiss_index(dimension=384)
    documents = []
    if faiss_index:
        print("\nIndexing codebase...")
        documents = index_codebase_faiss(project_path, faiss_index)

    # Demonstrate dependency update and Git Integration
    print("\nDemonstrating dependency update and Git Integration...")
    dependency_to_update = "langchain"
    
    # Get the actual latest version to use for update
    actual_latest_version = get_latest_version(dependency_to_update)
    print(f"Latest version for {dependency_to_update}: {actual_latest_version}")

    # RAG Query demonstration with LLM Risk Assessment
    should_proceed = False

    if faiss_index:
        print(f"\nQuerying codebase for usages of '{dependency_to_update}'...")
        rag_results = query_faiss_index(faiss_index, documents, dependency_to_update)
        if rag_results:
            print(f"Found {len(rag_results)} code snippets related to '{dependency_to_update}':")
            for snippet in rag_results:
                print(f"  - {snippet.strip()}")
        else:
            print(f"No code snippets found for '{dependency_to_update}'.")

        # LLM Risk Assessment
        print(f"\nAnalyzing update risk with LLM...")
        current_dep = next((d for d in dependencies if d['name'] == dependency_to_update), None)
        current_version = current_dep['version'] if current_dep else 'unknown'

        risk_assessment = assess_dependency_update_risk(
            dependency_name=dependency_to_update,
            current_version=current_version,
            new_version=actual_latest_version,
            code_snippets=rag_results
        )

        print(f"\nRisk Assessment Results:")
        print(f"  Risk Level: {risk_assessment['risk_level'].upper()}")
        print(f"  Recommendation: {risk_assessment['recommendation'].upper()}")
        print(f"  Explanation: {risk_assessment['explanation']}")

        # Decision logic based on risk assessment
        if risk_assessment['risk_level'] == 'low':
            should_proceed = True
            print(f"\nDecision: Proceeding with update (low risk)")
        elif risk_assessment['risk_level'] == 'medium':
            print(f"\nDecision: Flagging for review (medium risk)")
            print(f"  Manual review recommended before updating {dependency_to_update}")
        elif risk_assessment['risk_level'] == 'high':
            print(f"\nDecision: Blocking update (high risk)")
            print(f"  High risk detected. Update requires careful manual review.")
        else:  # unknown risk
            print(f"\nDecision: Flagging for review (risk assessment unavailable)")
            print(f"  Unable to assess risk. Manual review recommended.")
    else:
        # No FAISS index - proceed without LLM analysis
        print("\nNo FAISS index available. Proceeding without risk assessment.")
        should_proceed = True

    # Conditional update based on risk assessment
    if should_proceed:
        # Ensure a change happens for git to pick up
        print(f"\nAttempting to update {dependency_to_update} to {actual_latest_version}...")
        updated = update_dependency_in_requirements("requirements.txt", dependency_to_update, actual_latest_version)

        if updated:
            print(f"\nSuccessfully updated {dependency_to_update}.")
            print("New dependencies:")
            dependencies = discover_dependencies(".")
            for dep in dependencies:
                print(f"- {dep['name']}: {dep['version']}")

            # Git operations
            branch_name = "feature/update-langchain"
            commit_message = f"Update {dependency_to_update} to {actual_latest_version}"

            try:
                # Clean __pycache__ before git operations
                if os.path.exists("__pycache__"):
                    print("Cleaning __pycache__ directory...")
                    shutil.rmtree("__pycache__")

                # Ensure we are on main branch before creating a new branch
                run_git_command(['checkout', 'main'])

                print(f"\nCreating new branch: {branch_name}")
                git_create_branch(branch_name) # This function handles existence check and checkout

                # Only add requirements.txt for the commit, and then commit
                run_git_command(['add', 'requirements.txt'])
                print(f"Committing changes with message: '{commit_message}'")
                git_commit_changes(commit_message) # Now git_commit_changes only commits what's staged
                print("Changes committed successfully.")
            except Exception as e:
                print(f"Git operation failed: {e}")
        else:
            print(f"\nCould not find {dependency_to_update} in requirements.txt or no update was needed. No commit performed.")
    else:
        print(f"\nUpdate skipped based on risk assessment. No changes made.")


if __name__ == "__main__":
    main()
