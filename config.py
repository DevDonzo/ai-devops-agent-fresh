"""
Configuration management for the ML DevOps Intelligence Platform.

Centralizes all configuration with:
- Environment variable loading
- Sensible defaults
- Validation
- Easy switching between providers

Usage:
    from config import Config
    config = Config()
    llm = config.get_llm_provider()
    storage = config.get_storage_provider()
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Literal
from dotenv import load_dotenv


# Load environment variables
load_dotenv()


@dataclass
class AWSConfig:
    """AWS-specific configuration."""
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    access_key_id: Optional[str] = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID"))
    secret_access_key: Optional[str] = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY"))

    # S3
    s3_bucket: Optional[str] = field(default_factory=lambda: os.getenv("S3_BUCKET"))
    s3_prefix: str = field(default_factory=lambda: os.getenv("S3_PREFIX", "assessments"))

    # Bedrock
    bedrock_model: str = field(default_factory=lambda: os.getenv("BEDROCK_MODEL", "claude-3-sonnet"))

    # SageMaker
    sagemaker_endpoint: Optional[str] = field(default_factory=lambda: os.getenv("SAGEMAKER_ENDPOINT"))
    sagemaker_role_arn: Optional[str] = field(default_factory=lambda: os.getenv("SAGEMAKER_ROLE_ARN"))

    def is_configured(self) -> bool:
        """Check if AWS credentials are available."""
        # boto3 can use various credential sources
        try:
            import boto3
            session = boto3.Session()
            return session.get_credentials() is not None
        except Exception:
            return False


@dataclass
class AzureConfig:
    """Azure-specific configuration."""
    # Storage
    storage_account_url: Optional[str] = field(
        default_factory=lambda: os.getenv("AZURE_STORAGE_ACCOUNT_URL")
    )
    storage_connection_string: Optional[str] = field(
        default_factory=lambda: os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    )
    storage_container: str = field(
        default_factory=lambda: os.getenv("AZURE_STORAGE_CONTAINER", "assessments")
    )

    # OpenAI
    openai_endpoint: Optional[str] = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY")
    )
    openai_deployment: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
    )

    # Synapse
    synapse_endpoint: Optional[str] = field(
        default_factory=lambda: os.getenv("SYNAPSE_SQL_ENDPOINT")
    )
    synapse_database: str = field(
        default_factory=lambda: os.getenv("SYNAPSE_DATABASE", "devops_ml")
    )

    # Auth preference
    use_azure_ad: bool = field(
        default_factory=lambda: os.getenv("AZURE_USE_AD", "true").lower() == "true"
    )

    def is_configured(self) -> bool:
        """Check if Azure credentials are available."""
        # Check for connection string or AD auth capability
        if self.storage_connection_string:
            return True
        if self.storage_account_url:
            try:
                from azure.identity import DefaultAzureCredential
                DefaultAzureCredential()
                return True
            except Exception:
                pass
        return False


@dataclass
class GeminiConfig:
    """Google Gemini configuration."""
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))

    def is_configured(self) -> bool:
        return self.api_key is not None


@dataclass
class Config:
    """
    Main configuration class for the ML DevOps Platform.

    Aggregates all provider configurations and provides
    factory methods for creating provider instances.
    """

    # Provider selection
    llm_provider: Literal["gemini", "bedrock", "azure_openai"] = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini")
    )
    storage_provider: Literal["local", "s3", "azure_blob", "synapse"] = field(
        default_factory=lambda: os.getenv("STORAGE_PROVIDER", "local")
    )

    # ML options
    use_sagemaker: bool = field(
        default_factory=lambda: os.getenv("USE_SAGEMAKER", "false").lower() == "true"
    )
    use_local_classifier: bool = field(
        default_factory=lambda: os.getenv("USE_LOCAL_CLASSIFIER", "true").lower() == "true"
    )

    # Sub-configurations
    aws: AWSConfig = field(default_factory=AWSConfig)
    azure: AzureConfig = field(default_factory=AzureConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)

    # Local paths
    local_storage_path: str = field(
        default_factory=lambda: os.getenv("LOCAL_STORAGE_PATH", "./data/assessments")
    )
    local_model_path: str = field(
        default_factory=lambda: os.getenv("LOCAL_MODEL_PATH", "./ml/model_artifacts/risk_classifier.joblib")
    )

    def get_llm_provider(self):
        """
        Get the configured LLM provider instance.

        Returns the appropriate provider based on LLM_PROVIDER setting,
        falling back to available providers if the configured one fails.
        """
        from providers import get_llm_provider

        try:
            return get_llm_provider(self.llm_provider)
        except ValueError as e:
            print(f"Warning: {e}")

            # Try fallbacks in order of preference
            fallbacks = ["gemini", "bedrock", "azure_openai"]
            for fallback in fallbacks:
                if fallback == self.llm_provider:
                    continue
                try:
                    return get_llm_provider(fallback)
                except ValueError:
                    continue

            raise ValueError("No LLM providers available. Check your configuration.")

    def get_storage_provider(self):
        """
        Get the configured storage provider instance.

        Returns the appropriate provider based on STORAGE_PROVIDER setting,
        always falling back to local storage if cloud providers fail.
        """
        from providers import get_storage_provider
        return get_storage_provider(self.storage_provider)

    def get_risk_classifier(self):
        """
        Get the appropriate risk classifier.

        Uses SageMaker endpoint if configured, otherwise local model.
        """
        if self.use_sagemaker and self.aws.sagemaker_endpoint:
            from ml import SageMakerRiskClassifier
            classifier = SageMakerRiskClassifier(
                endpoint_name=self.aws.sagemaker_endpoint,
                region=self.aws.region
            )
            if classifier.is_available():
                return classifier

        if self.use_local_classifier:
            from ml import LocalRiskClassifier
            return LocalRiskClassifier(model_path=self.local_model_path)

        return None

    def print_status(self):
        """Print current configuration status."""
        print("\n" + "="*60)
        print("ML DevOps Intelligence Platform - Configuration Status")
        print("="*60)

        print(f"\nLLM Provider: {self.llm_provider}")
        if self.llm_provider == "gemini":
            status = "configured" if self.gemini.is_configured() else "NOT configured"
            print(f"  Gemini API: {status}")
        elif self.llm_provider == "bedrock":
            status = "configured" if self.aws.is_configured() else "NOT configured"
            print(f"  AWS Bedrock: {status}")
            print(f"  Model: {self.aws.bedrock_model}")
        elif self.llm_provider == "azure_openai":
            status = "configured" if self.azure.openai_endpoint else "NOT configured"
            print(f"  Azure OpenAI: {status}")
            print(f"  Deployment: {self.azure.openai_deployment}")

        print(f"\nStorage Provider: {self.storage_provider}")
        if self.storage_provider == "s3":
            print(f"  S3 Bucket: {self.aws.s3_bucket or 'NOT SET'}")
        elif self.storage_provider in ["azure_blob", "synapse"]:
            print(f"  Storage URL: {self.azure.storage_account_url or 'NOT SET'}")
        elif self.storage_provider == "local":
            print(f"  Path: {self.local_storage_path}")

        print(f"\nML Options:")
        print(f"  SageMaker: {'enabled' if self.use_sagemaker else 'disabled'}")
        print(f"  Local Classifier: {'enabled' if self.use_local_classifier else 'disabled'}")

        print("\n" + "="*60 + "\n")

    def validate(self) -> bool:
        """
        Validate the configuration.

        Returns True if at least one LLM and one storage provider are available.
        """
        has_llm = (
            self.gemini.is_configured() or
            self.aws.is_configured() or
            (self.azure.openai_endpoint is not None)
        )

        has_storage = True  # Local storage is always available

        if not has_llm:
            print("Warning: No LLM provider configured. Set GEMINI_API_KEY, AWS credentials, or AZURE_OPENAI_* vars.")

        return has_llm and has_storage


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
