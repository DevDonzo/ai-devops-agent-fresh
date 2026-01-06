# AI DevOps & Security Automator

## 1. Project Goal

The core mission of this project is to build an autonomous AI agent that intelligently manages third-party dependencies in software projects. The agent will automate the tedious and critical process of keeping dependencies up-to-date, secure, and compatible with the existing codebase.

This goes beyond simple version bumping. The agent uses a "Context-Aware Update Strategy" powered by Retrieval-Augmented Generation (RAG) to understand how each dependency is used within the project. This allows it to make informed decisions, identify potential breaking changes, and ensure that updates are not just the latest, but also the safest.

## 2. High-Level Architecture

The agent operates through a series of coordinated capabilities:

1.  **Dependency Discovery**: It starts by identifying and parsing dependency files (e.g., `requirements.txt`).
2.  **Intelligence Gathering**: For each dependency, it gathers two key pieces of information:
    *   **Version Intelligence**: It finds the latest stable version available.
    *   **Vulnerability Scanning**: It checks for any known security vulnerabilities (CVEs) in the current version.
3.  **Context-Aware Analysis (RAG)**: Before updating, the agent queries a vector database of the project's own source code to find where the dependency is used. This context can be used to assess the risk of breaking changes.
4.  **Automated Action**:
    *   **Code Modification**: It directly updates the dependency files with safe changes.
    *   **Git Integration**: It creates a new feature branch, commits the changes, and prepares for a pull request, isolating the update for review.

## 3. Core Agentic Capabilities

*   [x] **Dependency Discovery**: Automatically identifies and parses `requirements.txt`.
*   [x] **Version Intelligence**: Autonomously queries PyPI to find the latest stable version of each dependency.
*   [x] **Vulnerability Scanning**: Checks for known security vulnerabilities (CVEs) against the OSV.dev database.
*   [x] **Context-Aware Update Strategy (RAG)**:
    *   [x] Indexes the codebase into a FAISS vector store.
    *   [x] Queries the vector store to find how and where the dependency is used.
    *   [x] **Integrates with Google Gemini LLM to analyze code snippets and assess update risk** ✨ (COMPLETE).
*   [x] **Intelligent Risk Assessment**: LLM analyzes code usage patterns to determine update safety.
*   [x] **Risk-Based Decision Making**: Auto-proceeds with low-risk updates, flags medium/high-risk for review.
*   [x] **Automated Code Modification**: Directly updates `requirements.txt` with safe changes.
*   [x] **Git Integration**: Creates a new branch, and commits the changes.

## 4. Technology Stack

*   **Agent Orchestration**: Python with LangChain and the Google Gemini API.
*   **Vector Database (RAG)**: `faiss-cpu` (running locally).
*   **Web Search/API Calls**: `requests` to query PyPI and OSV.dev.
*   **Codebase Indexing**: `sentence-transformers` library.
*   **Git Operations**: Python's `subprocess` module.
*   **Environment**: Python `venv` for dependency management.

## 5. Setup and Execution

1.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    ```
2.  **Activate the virtual environment:**
    ```bash
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set up API Keys:**
    *   Create a `.env` file in the project root.
    *   Add your Gemini API key to the `.env` file (required for LLM risk assessment):
        ```
        GEMINI_API_KEY="your-gemini-api-key"
        ```
    *   Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
5.  **Run the agent:**
    ```bash
    python3 main.py
    ```

## 6. LLM-Powered Risk Assessment ✨

The agent uses **Google Gemini 2.5 Flash** to perform intelligent risk analysis on dependency updates. This is the core of the "Context-Aware Update Strategy."

### How It Works

1. **Code Context Extraction**: The RAG system retrieves actual code snippets showing how each dependency is used in the project.
2. **LLM Analysis**: The snippets are passed to Gemini along with:
   - Dependency name, current version, and target version
   - Code usage patterns showing how the dependency is integrated
3. **Risk Assessment**: The LLM evaluates:
   - Whether the version change is major, minor, or patch
   - Known breaking changes between versions
   - API stability and backwards compatibility
   - Complexity of the dependency integration in the codebase
4. **Smart Decision Making**:
   - **LOW RISK** → Auto-proceeds with the update
   - **MEDIUM RISK** → Flags for manual review (no update)
   - **HIGH RISK** → Blocks update, recommends careful review
   - **UNKNOWN** → Conservative default: flags for review (API failures, missing key, etc.)

### Example Flow

```
Dependency: langchain, Current: 1.0.0, Target: 1.5.0

1. RAG Query finds code usage:
   - from langchain import OpenAI
   - chain = LLMChain(...)

2. LLM Analysis:
   "Major version bump. Usage shows deep integration with LangChain's
    core APIs. Target version has breaking changes in LLMChain API."

3. Risk Assessment: HIGH

4. Decision: Block update, flag for manual review
```

### Implementation Details

- **Function**: `assess_dependency_update_risk()` in `tools.py` (lines 102-210)
- **Model**: `gemini-2.5-flash` (fast, cost-effective)
- **Prompt Engineering**: Structured prompts with clear risk guidelines
- **Error Handling**: Graceful fallback to manual review on API failures
- **Integration**: Called in `main.py` after RAG code snippet retrieval (lines 70-99)

## 7. Future Enhancements

Potential improvements for future versions:

1. **Enhanced Risk Detection**:
   - Parse and analyze changelogs for breaking changes
   - Check GitHub/GitLab release notes automatically
   - Track package health metrics (stars, contributors, last update)

2. **Advanced Decision Logic**:
   - User confirmation prompts for medium-risk updates
   - Audit trails and logging of all risk assessments
   - Configurable risk thresholds per project

3. **Multi-LLM Support**:
   - Support for Claude, GPT-4, and other LLM providers
   - Fallback to secondary LLM if primary fails
   - Ensemble risk assessment (multiple LLMs voting)

4. **Test Integration**:
   - Automatically run unit tests before updating
   - Only proceed if tests pass
   - Generate test reports in the commit message

5. **Performance Optimization**:
   - Cache risk assessments to avoid redundant LLM calls
   - Batch process multiple dependencies
   - Implement request queuing for rate limiting