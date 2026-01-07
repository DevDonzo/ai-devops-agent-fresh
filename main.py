"""
ML-Powered DevOps Intelligence Platform

A multi-cloud dependency management system that intelligently updates
package dependencies using:
- Multi-provider LLM support (Gemini, AWS Bedrock, Azure OpenAI)
- Multi-cloud storage (Local, S3, Azure Blob, Synapse)
- ML-based risk classification (Local sklearn, SageMaker)

Demonstrates:
- AWS ML Engineer Associate skills (Bedrock, SageMaker, S3)
- Azure DP-700 Data Engineer skills (Azure OpenAI, Blob, Synapse)

Usage:
    python main.py [--provider gemini|bedrock|azure_openai] [--storage local|s3|azure_blob|synapse]
"""

import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

from tools import (
    discover_dependencies,
    get_latest_version,
    update_dependency_in_requirements,
    git_create_branch,
    git_commit_changes,
    check_vulnerabilities,
    run_git_command,
    initialize_faiss_index,
    index_codebase_faiss,
    query_faiss_index
)
from config import get_config, Config
from providers.base import AssessmentRecord


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ML-Powered DevOps Intelligence Platform"
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "bedrock", "azure_openai"],
        help="LLM provider to use (overrides LLM_PROVIDER env var)"
    )
    parser.add_argument(
        "--storage",
        choices=["local", "s3", "azure_blob", "synapse"],
        help="Storage provider to use (overrides STORAGE_PROVIDER env var)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print configuration status and exit"
    )
    parser.add_argument(
        "--use-classifier",
        action="store_true",
        help="Use ML classifier for fast risk pre-screening"
    )
    return parser.parse_args()


def main():
    """Main entry point for the ML DevOps Intelligence Platform."""
    # Load environment variables
    load_dotenv()

    # Parse arguments
    args = parse_args()

    # Override config from CLI if provided
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    if args.storage:
        os.environ["STORAGE_PROVIDER"] = args.storage
    if args.use_classifier:
        os.environ["USE_LOCAL_CLASSIFIER"] = "true"

    # Get configuration
    config = get_config()

    # Just print status if requested
    if args.status:
        config.print_status()
        return

    print("\n" + "="*60)
    print("  ML-Powered DevOps Intelligence Platform")
    print("="*60)

    # Initialize providers
    print("\nInitializing providers...")

    try:
        llm_provider = config.get_llm_provider()
        print(f"  LLM Provider: {llm_provider.provider_name} ({llm_provider.model_name})")
    except ValueError as e:
        print(f"  LLM Provider: FAILED - {e}")
        print("  Continuing without LLM risk assessment...")
        llm_provider = None

    storage_provider = config.get_storage_provider()
    print(f"  Storage Provider: {storage_provider.provider_name}")

    risk_classifier = config.get_risk_classifier()
    if risk_classifier:
        print(f"  Risk Classifier: enabled (local sklearn)")
    else:
        print(f"  Risk Classifier: disabled")

    # Discover dependencies
    project_path = "."
    dependencies = discover_dependencies(project_path)

    if dependencies:
        print(f"\nDiscovered {len(dependencies)} dependencies:")
        for dep in dependencies:
            latest_version = get_latest_version(dep['name'])
            print(f"  - {dep['name']}: current={dep['version']}, latest={latest_version}")

            # Check for vulnerabilities
            if dep['version'] != 'any':
                vulnerabilities = check_vulnerabilities(dep['name'], dep['version'])
                if vulnerabilities:
                    print(f"    [!] {len(vulnerabilities)} vulnerabilities found")
                    for vuln in vulnerabilities[:2]:  # Show first 2
                        print(f"        - {vuln['id']}: {vuln['summary'][:60]}...")
    else:
        print("\nNo dependencies found.")
        return

    # Initialize FAISS index for semantic search
    print("\nInitializing semantic search index...")
    faiss_index = initialize_faiss_index(dimension=384)
    documents = []
    if faiss_index:
        documents = index_codebase_faiss(project_path, faiss_index)
        print(f"  Indexed {len(documents)} code snippets")

    # Process a specific dependency (langchain for demo)
    dependency_to_update = "langchain"
    print(f"\n{'='*60}")
    print(f"Analyzing update for: {dependency_to_update}")
    print("="*60)

    # Get version info
    current_dep = next((d for d in dependencies if d['name'] == dependency_to_update), None)
    if not current_dep:
        print(f"Dependency {dependency_to_update} not found in requirements.txt")
        return

    current_version = current_dep['version']
    latest_version = get_latest_version(dependency_to_update)
    print(f"\nVersion: {current_version} -> {latest_version}")

    # Get code snippets using semantic search
    code_snippets = []
    if faiss_index and documents:
        print(f"\nSearching codebase for {dependency_to_update} usage...")
        code_snippets = query_faiss_index(faiss_index, documents, dependency_to_update)
        if code_snippets:
            print(f"Found {len(code_snippets)} relevant code snippets:")
            for snippet in code_snippets[:3]:
                print(f"  | {snippet.strip()[:70]}...")

    # Fast pre-screening with ML classifier (if available)
    classifier_result = None
    if risk_classifier and code_snippets:
        print(f"\nRunning ML classifier pre-screening...")
        classifier_result = risk_classifier.predict(
            dependency_to_update, current_version, latest_version, code_snippets
        )
        print(f"  Classifier result: {classifier_result['risk_level'].upper()}")
        print(f"  Confidence: {classifier_result['confidence']:.2%}")
        print(f"  Model: {classifier_result['model']}")

    # LLM-based risk assessment
    risk_assessment = None
    if llm_provider:
        print(f"\nRunning LLM risk assessment ({llm_provider.provider_name})...")
        risk_assessment = llm_provider.assess_dependency_risk(
            dependency_to_update, current_version, latest_version, code_snippets
        )
        print(f"\n  Risk Level: {risk_assessment.risk_level.upper()}")
        print(f"  Recommendation: {risk_assessment.recommendation.upper()}")
        print(f"  Explanation: {risk_assessment.explanation}")
        print(f"  Provider: {risk_assessment.provider}/{risk_assessment.model}")

    # Determine final decision
    if risk_assessment:
        risk_level = risk_assessment.risk_level
        recommendation = risk_assessment.recommendation
    elif classifier_result:
        risk_level = classifier_result['risk_level']
        recommendation = 'proceed' if risk_level == 'low' else 'review'
    else:
        risk_level = 'unknown'
        recommendation = 'review'

    # Store assessment record
    if risk_assessment:
        record = AssessmentRecord(
            timestamp=datetime.utcnow(),
            dependency=dependency_to_update,
            current_version=current_version,
            target_version=latest_version,
            risk_level=risk_level,
            recommendation=recommendation,
            llm_provider=risk_assessment.provider,
            model=risk_assessment.model,
            vulnerabilities_found=len(check_vulnerabilities(dependency_to_update, current_version)),
            code_snippets_analyzed=len(code_snippets),
            explanation=risk_assessment.explanation
        )

        print(f"\nSaving assessment to {storage_provider.provider_name}...")
        if storage_provider.save_assessment(record):
            print("  Assessment saved successfully")
        else:
            print("  Failed to save assessment")

    # Decision and action
    print(f"\n{'='*60}")
    print("DECISION")
    print("="*60)

    should_proceed = risk_level == 'low' and recommendation == 'proceed'

    if should_proceed:
        print(f"\nProceeding with update (low risk)")

        # Update requirements.txt
        updated = update_dependency_in_requirements(
            "requirements.txt", dependency_to_update, latest_version
        )

        if updated:
            print(f"Updated {dependency_to_update} to {latest_version}")

            # Git operations
            branch_name = f"feature/update-{dependency_to_update}"
            commit_message = f"Update {dependency_to_update} to {latest_version}"

            try:
                # Ensure on main first
                run_git_command(['checkout', 'main'])

                print(f"\nCreating branch: {branch_name}")
                git_create_branch(branch_name)

                run_git_command(['add', 'requirements.txt'])
                git_commit_changes(commit_message)
                print("Changes committed successfully")

            except Exception as e:
                print(f"Git operation failed: {e}")
        else:
            print("No update needed or update failed")

    elif risk_level == 'medium':
        print(f"\nFlagging for review (medium risk)")
        print("Manual review recommended before updating")

    elif risk_level == 'high':
        print(f"\nBlocking update (high risk)")
        print("This update requires careful manual review")

    else:
        print(f"\nFlagging for review (risk assessment unavailable)")
        print("Unable to assess risk. Manual review recommended.")

    # Print storage statistics
    print(f"\n{'='*60}")
    print("ANALYTICS")
    print("="*60)
    stats = storage_provider.get_statistics()
    print(f"\nTotal assessments: {stats.get('total_assessments', 0)}")
    if stats.get('risk_distribution'):
        print("Risk distribution:")
        for level, count in stats['risk_distribution'].items():
            print(f"  {level}: {count}")
    if stats.get('provider_distribution'):
        print("Provider usage:")
        for provider, count in stats['provider_distribution'].items():
            print(f"  {provider}: {count}")

    print("\n" + "="*60)
    print("Done!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
