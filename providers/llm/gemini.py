"""
Google Gemini LLM provider for risk assessment.

Uses the Gemini 2.5 Flash model for fast, cost-effective analysis.
Requires GEMINI_API_KEY environment variable.
"""

import os
from typing import List

from ..base import LLMProvider, RiskAssessment


class GeminiProvider(LLMProvider):
    """
    Google Gemini implementation of LLMProvider.

    This is the default provider, using Gemini 2.5 Flash for
    fast and cost-effective dependency risk assessment.
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        """
        Initialize the Gemini provider.

        Args:
            model: Gemini model to use (default: gemini-2.5-flash)
        """
        self._model_name = model
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Gemini client if API key is available."""
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._client = genai.GenerativeModel(self._model_name)
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini client: {e}")
                self._client = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        """Check if Gemini is properly configured."""
        return self._client is not None

    def assess_dependency_risk(
        self,
        dependency_name: str,
        current_version: str,
        new_version: str,
        code_snippets: List[str]
    ) -> RiskAssessment:
        """
        Assess dependency update risk using Gemini.

        Args:
            dependency_name: Name of the package
            current_version: Current version
            new_version: Target version
            code_snippets: Code showing usage patterns

        Returns:
            RiskAssessment with analysis results
        """
        # Fallback if not available
        if not self.is_available():
            return RiskAssessment(
                risk_level="unknown",
                explanation="Gemini API not available. Manual review recommended.",
                recommendation="review",
                provider=self.provider_name,
                model=self.model_name
            )

        try:
            # Build and send prompt
            prompt = self._build_risk_prompt(
                dependency_name, current_version, new_version, code_snippets
            )
            response = self._client.generate_content(prompt)
            response_text = response.text.strip()

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
            print(f"Error calling Gemini API: {e}")
            return RiskAssessment(
                risk_level="unknown",
                explanation=f"API error: {str(e)}. Manual review recommended.",
                recommendation="review",
                provider=self.provider_name,
                model=self.model_name
            )
