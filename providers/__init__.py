"""
Multi-cloud ML providers for the DevOps Intelligence Platform.

This package provides abstract interfaces and implementations for:
- LLM providers (Gemini, AWS Bedrock, Azure OpenAI)
- Storage providers (Local, S3, Azure Blob, Synapse)
- ML inference (SageMaker endpoints)
"""

from .base import LLMProvider, StorageProvider
from .llm import get_llm_provider
from .storage import get_storage_provider

__all__ = [
    "LLMProvider",
    "StorageProvider",
    "get_llm_provider",
    "get_storage_provider",
]
