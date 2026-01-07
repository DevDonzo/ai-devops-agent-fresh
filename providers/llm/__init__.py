"""
LLM providers for risk assessment.

Supports:
- Google Gemini (default)
- AWS Bedrock (Claude 3, Titan)
- Azure OpenAI (GPT-4)
"""

import os
from typing import Optional
from ..base import LLMProvider


def get_llm_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """
    Factory function to get the appropriate LLM provider.

    Args:
        provider_name: One of 'gemini', 'bedrock', 'azure_openai'.
                      If None, uses LLM_PROVIDER env var or defaults to 'gemini'.

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider is not recognized or not available
    """
    if provider_name is None:
        provider_name = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider_name == "gemini":
        from .gemini import GeminiProvider
        provider = GeminiProvider()
    elif provider_name == "bedrock":
        from .bedrock import BedrockProvider
        provider = BedrockProvider()
    elif provider_name == "azure_openai":
        from .azure_openai import AzureOpenAIProvider
        provider = AzureOpenAIProvider()
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider_name}. "
            "Supported: gemini, bedrock, azure_openai"
        )

    if not provider.is_available():
        raise ValueError(
            f"LLM provider '{provider_name}' is not available. "
            "Check your credentials and configuration."
        )

    return provider


__all__ = ["get_llm_provider"]
