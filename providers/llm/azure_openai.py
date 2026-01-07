"""
Azure OpenAI LLM provider for risk assessment.

Supports GPT-4 and GPT-4-Turbo models deployed on Azure OpenAI Service.
Requires Azure OpenAI configuration:
- AZURE_OPENAI_ENDPOINT: Your Azure OpenAI endpoint URL
- AZURE_OPENAI_API_KEY: API key (or use Azure AD auth)
- AZURE_OPENAI_DEPLOYMENT: Deployment name for your model

Demonstrates Azure DP-700 skills:
- Azure OpenAI Service integration
- Azure AD authentication patterns
- Azure SDK usage
- Enterprise AI deployment patterns
"""

import os
from typing import List, Optional

from ..base import LLMProvider, RiskAssessment


class AzureOpenAIProvider(LLMProvider):
    """
    Azure OpenAI implementation of LLMProvider.

    Supports GPT-4 models deployed on Azure OpenAI Service.
    Can authenticate via API key or Azure AD (DefaultAzureCredential).
    """

    def __init__(
        self,
        deployment_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_version: str = "2024-02-15-preview",
        use_azure_ad: bool = False
    ):
        """
        Initialize the Azure OpenAI provider.

        Args:
            deployment_name: Azure OpenAI deployment name
            endpoint: Azure OpenAI endpoint URL
            api_version: API version to use
            use_azure_ad: Use Azure AD auth instead of API key
        """
        self._deployment = deployment_name or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        self._endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self._api_version = api_version
        self._use_azure_ad = use_azure_ad
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Azure OpenAI client."""
        if not self._endpoint:
            print("Warning: AZURE_OPENAI_ENDPOINT not set")
            return

        try:
            from openai import AzureOpenAI

            if self._use_azure_ad:
                # Use Azure AD authentication (DefaultAzureCredential)
                # This is the recommended approach for production
                from azure.identity import DefaultAzureCredential, get_bearer_token_provider

                credential = DefaultAzureCredential()
                token_provider = get_bearer_token_provider(
                    credential,
                    "https://cognitiveservices.azure.com/.default"
                )

                self._client = AzureOpenAI(
                    azure_endpoint=self._endpoint,
                    azure_ad_token_provider=token_provider,
                    api_version=self._api_version
                )
                print("Azure OpenAI client initialized with Azure AD auth")
            else:
                # Use API key authentication
                api_key = os.getenv("AZURE_OPENAI_API_KEY")
                if not api_key:
                    print("Warning: AZURE_OPENAI_API_KEY not set")
                    return

                self._client = AzureOpenAI(
                    azure_endpoint=self._endpoint,
                    api_key=api_key,
                    api_version=self._api_version
                )
                print("Azure OpenAI client initialized with API key")

        except ImportError as e:
            print(f"Warning: Required packages not installed. Run: pip install openai azure-identity")
            print(f"Import error: {e}")
            self._client = None
        except Exception as e:
            print(f"Warning: Failed to initialize Azure OpenAI client: {e}")
            self._client = None

    @property
    def provider_name(self) -> str:
        return "azure_openai"

    @property
    def model_name(self) -> str:
        return self._deployment

    def is_available(self) -> bool:
        """Check if Azure OpenAI is properly configured."""
        return self._client is not None

    def assess_dependency_risk(
        self,
        dependency_name: str,
        current_version: str,
        new_version: str,
        code_snippets: List[str]
    ) -> RiskAssessment:
        """
        Assess dependency update risk using Azure OpenAI.

        Args:
            dependency_name: Name of the package
            current_version: Current version
            new_version: Target version
            code_snippets: Code showing usage patterns

        Returns:
            RiskAssessment with analysis results
        """
        if not self.is_available():
            return RiskAssessment(
                risk_level="unknown",
                explanation="Azure OpenAI not available. Check endpoint and credentials.",
                recommendation="review",
                provider=self.provider_name,
                model=self.model_name
            )

        try:
            prompt = self._build_risk_prompt(
                dependency_name, current_version, new_version, code_snippets
            )

            # Call Azure OpenAI using the Chat Completions API
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a software engineering expert specializing in dependency management and risk assessment."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=1024
            )

            response_text = response.choices[0].message.content.strip()

            # Parse response
            parsed = self._parse_risk_response(response_text)

            return RiskAssessment(
                risk_level=parsed['risk_level'],
                explanation=parsed['explanation'],
                recommendation=parsed['recommendation'],
                provider=self.provider_name,
                model=self.model_name
            )

        except Exception as e:
            print(f"Error calling Azure OpenAI API: {e}")
            return RiskAssessment(
                risk_level="unknown",
                explanation=f"API error: {str(e)}. Manual review recommended.",
                recommendation="review",
                provider=self.provider_name,
                model=self.model_name
            )

    def list_deployments(self) -> List[str]:
        """
        List available deployments (useful for debugging).

        Note: Requires additional permissions on the Azure OpenAI resource.
        """
        # This would require the Azure Management SDK
        # For now, just return the configured deployment
        return [self._deployment]
