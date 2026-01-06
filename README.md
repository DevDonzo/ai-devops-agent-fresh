# AI DevOps Agent

An autonomous agent that intelligently manages Python dependencies. Instead of just bumping versions, it understands your code and makes informed decisions about which updates are safe to apply.

## What It Does

Managing dependencies sucks. You have to:
- Check what versions are available
- Worry about breaking changes
- Hope the update doesn't break production
- Do this for dozens of packages across multiple projects

This agent automates it by combining RAG (code search) with LLM analysis to actually understand the impact before updating anything.

## How It Works

1. **Scans your code** - Indexes everything with FAISS so it can find where each dependency is used
2. **Checks for security issues** - Queries OSV.dev for known vulnerabilities
3. **Finds the latest versions** - Checks PyPI for what's available
4. **Analyzes the risk** - Uses Google Gemini to look at your actual code usage and assess breaking change risk
5. **Makes a decision** - Auto-updates low-risk changes, flags risky ones for review

The key part is step 4. Instead of blind version bumping, it:
- Retrieves code snippets showing how you actually use the dependency
- Passes them to an LLM along with version info
- Gets back a risk assessment (low/medium/high)
- Only proceeds if it's confident the update is safe

## Features

- Dependency discovery from requirements.txt
- Version checking against PyPI
- Vulnerability scanning via OSV.dev
- RAG-based code analysis with FAISS vector search
- LLM-powered risk assessment using Google Gemini
- Git integration for automated branches and commits
- Risk-based decision making (auto-update safe changes, flag risky ones)

## Setup

1. Clone and set up:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Add your Gemini API key:
```bash
# Create .env file
echo 'GEMINI_API_KEY=your-key-here' > .env
```

Get a free key from [Google AI Studio](https://aistudio.google.com/apikey).

3. Run it:
```bash
python3 main.py
```

## How The LLM Risk Assessment Works

When the agent wants to update a dependency, here's what happens:

1. It searches your codebase and finds actual code snippets showing how you use that dependency
2. It sends those snippets to Gemini along with the version numbers
3. Gemini analyzes the code and assesses whether the update is risky
4. Based on the assessment, it decides what to do:
   - **Low risk** - Updates automatically
   - **Medium risk** - Flags for manual review
   - **High risk** - Blocks the update

Example: You want to update langchain 1.0 to 2.0. The agent finds that your code deeply integrates with LangChain's core APIs. Gemini sees the major version bump and breaking changes, and recommends blocking it for manual review. Smart.

## Technology

- Python with LangChain for orchestration
- FAISS for semantic code search
- Sentence-transformers for embeddings
- Google Gemini 2.5 Flash for risk analysis
- OSV.dev API for vulnerability data
- PyPI API for version checking
- Git for version control integration

## Future Ideas

- Parse changelogs to supplement LLM analysis
- Run unit tests before updating to validate safety
- Support multiple LLM providers (Claude, GPT-4, etc)
- Cache risk assessments to avoid redundant API calls
- Configurable risk thresholds per project
