"""
Abstract base classes for ML providers.

These define the contract that all LLM and storage providers must implement,
enabling seamless switching between AWS, Azure, and Google Cloud services.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RiskAssessment:
    """Standardized risk assessment result across all LLM providers."""
    risk_level: str  # 'low', 'medium', 'high', 'unknown'
    explanation: str
    recommendation: str  # 'proceed', 'review'
    provider: str  # 'gemini', 'bedrock', 'azure_openai'
    model: str  # specific model used
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "provider": self.provider,
            "model": self.model,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AssessmentRecord:
    """Complete record of a dependency update assessment for storage."""
    timestamp: datetime
    dependency: str
    current_version: str
    target_version: str
    risk_level: str
    recommendation: str
    llm_provider: str
    model: str
    vulnerabilities_found: int
    code_snippets_analyzed: int
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "dependency": self.dependency,
            "current_version": self.current_version,
            "target_version": self.target_version,
            "risk_level": self.risk_level,
            "recommendation": self.recommendation,
            "llm_provider": self.llm_provider,
            "model": self.model,
            "vulnerabilities_found": self.vulnerabilities_found,
            "code_snippets_analyzed": self.code_snippets_analyzed,
            "explanation": self.explanation
        }


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Implementations:
    - GeminiProvider: Google Gemini (gemini-2.5-flash)
    - BedrockProvider: AWS Bedrock (Claude 3, Titan)
    - AzureOpenAIProvider: Azure OpenAI (GPT-4)
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g., 'gemini', 'bedrock', 'azure_openai')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the specific model being used."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is properly configured and available."""
        pass

    @abstractmethod
    def assess_dependency_risk(
        self,
        dependency_name: str,
        current_version: str,
        new_version: str,
        code_snippets: List[str]
    ) -> RiskAssessment:
        """
        Assess the risk of updating a dependency.

        Args:
            dependency_name: Name of the package to update
            current_version: Current version string
            new_version: Target version string
            code_snippets: Relevant code snippets showing usage

        Returns:
            RiskAssessment with risk level, explanation, and recommendation
        """
        pass

    def _build_risk_prompt(
        self,
        dependency_name: str,
        current_version: str,
        new_version: str,
        code_snippets: List[str]
    ) -> str:
        """Build the standardized prompt for risk assessment."""
        code_context = "\n".join(code_snippets) if code_snippets else "No code snippets found."

        return f"""You are a software engineering expert analyzing the risk of updating a Python dependency.

**Dependency Update Details:**
- Package: {dependency_name}
- Current Version: {current_version}
- Target Version: {new_version}

**Code Usage Context:**
The following code snippets show how this dependency is currently used in the codebase:

```
{code_context}
```

**Your Task:**
Analyze the risk of updating from version {current_version} to {new_version} based on:
1. The code usage patterns shown above
2. Known breaking changes between these versions (if any)
3. API stability and backwards compatibility
4. Complexity of the usage (simple imports vs deep integration)

**Response Format:**
Provide your assessment in this exact format:

RISK_LEVEL: [low|medium|high]
RECOMMENDATION: [proceed|review]
EXPLANATION: [2-3 sentences explaining your risk assessment, including specific concerns if any]

**Risk Level Guidelines:**
- LOW: Minor version update with no known breaking changes, simple usage patterns
- MEDIUM: Major version update OR moderate breaking changes OR moderate integration complexity
- HIGH: Major version with significant breaking changes OR deep integration OR deprecated APIs in use

Be conservative - when in doubt, assign a higher risk level."""

    def _parse_risk_response(self, response_text: str) -> Dict[str, str]:
        """Parse the LLM response into structured data."""
        risk_level = 'unknown'
        recommendation = 'review'
        explanation = response_text

        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('RISK_LEVEL:'):
                risk_level = line.split(':', 1)[1].strip().lower()
            elif line.startswith('RECOMMENDATION:'):
                recommendation = line.split(':', 1)[1].strip().lower()
            elif line.startswith('EXPLANATION:'):
                explanation = line.split(':', 1)[1].strip()

        # Validate risk level
        if risk_level not in ['low', 'medium', 'high']:
            risk_level = 'unknown'
            recommendation = 'review'

        return {
            'risk_level': risk_level,
            'recommendation': recommendation,
            'explanation': explanation
        }


class StorageProvider(ABC):
    """
    Abstract base class for storage providers.

    Implementations:
    - LocalStorageProvider: Local JSON files (development/fallback)
    - S3StorageProvider: AWS S3 with partitioning for Athena
    - AzureBlobProvider: Azure Blob Storage
    - SynapseProvider: Azure Synapse Analytics with Delta tables
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g., 'local', 's3', 'azure_blob', 'synapse')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is properly configured and available."""
        pass

    @abstractmethod
    def save_assessment(self, record: AssessmentRecord) -> bool:
        """
        Save an assessment record to storage.

        Args:
            record: The assessment record to save

        Returns:
            True if saved successfully, False otherwise
        """
        pass

    @abstractmethod
    def get_assessments(
        self,
        dependency: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AssessmentRecord]:
        """
        Retrieve assessment records from storage.

        Args:
            dependency: Filter by dependency name (optional)
            start_date: Filter by start date (optional)
            end_date: Filter by end date (optional)
            limit: Maximum number of records to return

        Returns:
            List of matching assessment records
        """
        pass

    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate statistics from stored assessments.

        Returns:
            Dictionary with counts, averages, and trends
        """
        pass
