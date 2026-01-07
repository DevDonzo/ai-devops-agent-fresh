# ML-Powered DevOps Intelligence Platform

A multi-cloud dependency management system that intelligently analyzes and updates package dependencies using machine learning and LLM-powered risk assessment.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                  ML DevOps Intelligence Platform                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐    │
│  │   Ingest    │───▶│   ML Layer      │───▶│   Data Layer     │    │
│  │   Layer     │    │   (LLM + ML)    │    │   (Lakehouse)    │    │
│  └─────────────┘    └─────────────────┘    └──────────────────┘    │
│        │                    │                       │               │
│        ▼                    ▼                       ▼               │
│  ┌───────────┐       ┌───────────┐           ┌───────────┐         │
│  │ PyPI API  │       │ Gemini    │           │ Local     │         │
│  │ OSV.dev   │       │ Bedrock   │◀─────────▶│ S3        │         │
│  │ GitHub    │       │ Azure OAI │           │ Blob      │         │
│  └───────────┘       │ SageMaker │           │ Synapse   │         │
│                      └───────────┘           └───────────┘         │
└─────────────────────────────────────────────────────────────────────┘
```

## What It Does

Managing dependencies is tedious. You have to check versions, worry about breaking changes, and hope updates don't break production. This platform automates it by combining semantic code search with LLM analysis to understand the impact before updating anything.

## Features

### Multi-Cloud LLM Support
| Provider | Models | Use Case |
|----------|--------|----------|
| Google Gemini | gemini-2.5-flash | Default, fast & cost-effective |
| AWS Bedrock | Claude 3 Sonnet/Haiku, Titan | Enterprise AWS environments |
| Azure OpenAI | GPT-4, GPT-4-Turbo | Enterprise Azure environments |

### Multi-Cloud Storage
| Provider | Technology | Best For |
|----------|------------|----------|
| Local | JSON files | Development & testing |
| AWS S3 | S3 + Athena | AWS data lakes |
| Azure Blob | Blob Storage | Azure environments |
| Azure Synapse | Serverless SQL | Enterprise analytics |

### ML-Powered Risk Assessment
- **Semantic Search**: FAISS + sentence-transformers for code analysis
- **Local Classifier**: sklearn-based fast pre-screening
- **SageMaker Endpoint**: Scalable ML inference in production

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/DevDonzo/ai-devops-agent-fresh.git
cd ai-devops-agent-fresh
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

Minimum configuration (Gemini only):
```env
GEMINI_API_KEY=your-gemini-api-key
```

Get a free key from [Google AI Studio](https://aistudio.google.com/apikey).

### 3. Run

```bash
python main.py
```

## Usage

### Command Line Options

```bash
# Use specific LLM provider
python main.py --provider bedrock
python main.py --provider azure_openai

# Use specific storage
python main.py --storage s3
python main.py --storage synapse

# Enable ML classifier pre-screening
python main.py --use-classifier

# Check configuration status
python main.py --status
```

### Example Output

```
============================================================
  ML-Powered DevOps Intelligence Platform
============================================================

Initializing providers...
  LLM Provider: bedrock (claude-3-sonnet)
  Storage Provider: s3
  Risk Classifier: enabled (local sklearn)

Discovered 9 dependencies:
  - langchain: current=1.2.0, latest=1.3.0
  - boto3: current=1.34.0, latest=1.35.0
  ...

============================================================
Analyzing update for: langchain
============================================================

Version: 1.2.0 -> 1.3.0

Running ML classifier pre-screening...
  Classifier result: MEDIUM
  Confidence: 78.5%

Running LLM risk assessment (bedrock)...
  Risk Level: MEDIUM
  Recommendation: REVIEW
  Explanation: Major version components may have breaking changes...

============================================================
DECISION
============================================================

Flagging for review (medium risk)
Manual review recommended before updating
```

## How It Works

1. **Dependency Discovery**: Parses `requirements.txt` to find packages
2. **Version Check**: Queries PyPI for latest versions
3. **Vulnerability Scan**: Checks OSV.dev for known CVEs
4. **Code Analysis**: Uses FAISS semantic search to find usage patterns
5. **ML Pre-screening**: Optional sklearn classifier for fast assessment
6. **LLM Risk Assessment**: Deep analysis using Gemini/Bedrock/Azure OpenAI
7. **Decision**: Auto-update (low risk) or flag for review (medium/high)
8. **Storage**: Persist assessment for analytics and auditing

## Project Structure

```
ai-devops-agent/
├── main.py                 # Entry point
├── config.py               # Configuration management
├── tools.py                # Core utilities
├── requirements.txt        # Dependencies
├── providers/
│   ├── base.py             # Abstract interfaces
│   ├── llm/
│   │   ├── gemini.py       # Google Gemini
│   │   ├── bedrock.py      # AWS Bedrock
│   │   └── azure_openai.py # Azure OpenAI
│   └── storage/
│       ├── local.py        # Local JSON
│       ├── s3.py           # AWS S3
│       ├── azure_blob.py   # Azure Blob
│       └── synapse.py      # Azure Synapse
├── ml/
│   ├── local_model.py      # sklearn classifier
│   └── sagemaker_endpoint.py # SageMaker deployment
└── docs/
    ├── aws_setup.md        # AWS configuration guide
    └── azure_setup.md      # Azure configuration guide
```

## Cloud Setup Guides

- [AWS Setup Guide](docs/aws_setup.md) - Bedrock, S3, SageMaker
- [Azure Setup Guide](docs/azure_setup.md) - OpenAI, Blob Storage, Synapse

## Skills Demonstrated

### AWS ML Engineer Associate
| Skill | Implementation |
|-------|----------------|
| Bedrock LLM invocation | `providers/llm/bedrock.py` |
| SageMaker deployment | `ml/sagemaker_endpoint.py` |
| S3 data lake patterns | `providers/storage/s3.py` |
| IAM & credentials | All AWS providers |

### Azure DP-700 Data Engineer
| Skill | Implementation |
|-------|----------------|
| Azure OpenAI integration | `providers/llm/azure_openai.py` |
| Blob Storage patterns | `providers/storage/azure_blob.py` |
| Synapse serverless SQL | `providers/storage/synapse.py` |
| Azure AD authentication | All Azure providers |

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | gemini, bedrock, azure_openai | gemini |
| `STORAGE_PROVIDER` | local, s3, azure_blob, synapse | local |
| `USE_SAGEMAKER` | Enable SageMaker endpoint | false |
| `USE_LOCAL_CLASSIFIER` | Enable sklearn pre-screening | true |

See `.env.example` for complete list.

## Technology Stack

- **LLM Providers**: Google Gemini, AWS Bedrock (Claude 3, Titan), Azure OpenAI (GPT-4)
- **Vector Search**: FAISS + Sentence-Transformers
- **ML Framework**: scikit-learn, SageMaker
- **Storage**: S3, Azure Blob, Synapse Analytics
- **Security**: OSV.dev vulnerability database
- **Package Data**: PyPI JSON API

## Future Ideas

- Parse changelogs to supplement LLM analysis
- Run unit tests before updating to validate safety
- GitHub Actions integration for CI/CD
- Slack/Teams notifications for risky updates
- Configurable risk thresholds per project
- Multi-repo batch processing

## License

MIT
