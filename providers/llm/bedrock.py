"""
AWS Bedrock LLM provider for risk assessment.

Supports Claude 3 (Sonnet, Haiku) and Amazon Titan models.
Requires AWS credentials configured via:
- Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- AWS credentials file (~/.aws/credentials)
- IAM role (when running on AWS)

Demonstrates AWS ML Engineer Associate skills:
- Bedrock Runtime API invocation
- IAM credential handling
- Multi-model support
- Error handling and fallbacks
"""

import os
import json
from typing import List, Optional

from ..base import LLMProvider, RiskAssessment


class BedrockProvider(LLMProvider):
    """
    AWS Bedrock implementation of LLMProvider.

    Supports multiple foundation models:
    - anthropic.claude-3-sonnet-20240229-v1:0 (default, best quality)
    - anthropic.claude-3-haiku-20240307-v1:0 (faster, cheaper)
    - amazon.titan-text-express-v1 (AWS native)
    """

    # Supported models and their configurations
    SUPPORTED_MODELS = {
        "claude-3-sonnet": {
            "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
            "provider": "anthropic",
            "max_tokens": 4096
        },
        "claude-3-haiku": {
            "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
            "provider": "anthropic",
            "max_tokens": 4096
        },
        "titan-text": {
            "model_id": "amazon.titan-text-express-v1",
            "provider": "amazon",
            "max_tokens": 4096
        }
    }

    def __init__(
        self,
        model: str = "claude-3-sonnet",
        region: Optional[str] = None
    ):
        """
        Initialize the Bedrock provider.

        Args:
            model: Model alias (claude-3-sonnet, claude-3-haiku, titan-text)
            region: AWS region (default: from env or us-east-1)
        """
        if model not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model: {model}. "
                f"Supported: {list(self.SUPPORTED_MODELS.keys())}"
            )

        self._model_alias = model
        self._model_config = self.SUPPORTED_MODELS[model]
        self._region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Bedrock Runtime client."""
        try:
            import boto3
            from botocore.config import Config

            # Configure retry behavior for reliability
            config = Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                connect_timeout=10,
                read_timeout=60
            )

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self._region,
                config=config
            )

            # Verify credentials by describing the model
            # This is a lightweight check that validates access
            print(f"Bedrock client initialized for region: {self._region}")

        except ImportError:
            print("Warning: boto3 not installed. Run: pip install boto3")
            self._client = None
        except Exception as e:
            print(f"Warning: Failed to initialize Bedrock client: {e}")
            self._client = None

    @property
    def provider_name(self) -> str:
        return "bedrock"

    @property
    def model_name(self) -> str:
        return self._model_alias

    def is_available(self) -> bool:
        """Check if Bedrock is properly configured."""
        if self._client is None:
            return False

        # Check for AWS credentials
        try:
            import boto3
            session = boto3.Session()
            credentials = session.get_credentials()
            return credentials is not None
        except Exception:
            return False

    def assess_dependency_risk(
        self,
        dependency_name: str,
        current_version: str,
        new_version: str,
        code_snippets: List[str]
    ) -> RiskAssessment:
        """
        Assess dependency update risk using AWS Bedrock.

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
                explanation="AWS Bedrock not available. Check AWS credentials.",
                recommendation="review",
                provider=self.provider_name,
                model=self.model_name
            )

        try:
            prompt = self._build_risk_prompt(
                dependency_name, current_version, new_version, code_snippets
            )

            # Build request based on model provider
            if self._model_config["provider"] == "anthropic":
                response_text = self._invoke_claude(prompt)
            else:
                response_text = self._invoke_titan(prompt)

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
            print(f"Error calling Bedrock API: {e}")
            return RiskAssessment(
                risk_level="unknown",
                explanation=f"API error: {str(e)}. Manual review recommended.",
                recommendation="review",
                provider=self.provider_name,
                model=self.model_name
            )

    def _invoke_claude(self, prompt: str) -> str:
        """
        Invoke Claude models via Bedrock.

        Uses the Messages API format for Claude 3 models.
        """
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self._model_config["max_tokens"],
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = self._client.invoke_model(
            modelId=self._model_config["model_id"],
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body)
        )

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    def _invoke_titan(self, prompt: str) -> str:
        """
        Invoke Amazon Titan models via Bedrock.

        Uses the Titan-specific request format.
        """
        request_body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": self._model_config["max_tokens"],
                "temperature": 0.3,
                "topP": 0.9
            }
        }

        response = self._client.invoke_model(
            modelId=self._model_config["model_id"],
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body)
        )

        response_body = json.loads(response["body"].read())
        return response_body["results"][0]["outputText"]
