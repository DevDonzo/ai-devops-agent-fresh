"""
Local risk classification model for development and testing.

This module provides a simple sklearn-based classifier that can:
1. Run locally without AWS credentials
2. Serve as a template for SageMaker deployment
3. Provide fast "first-pass" risk assessment before LLM calls

Demonstrates AWS ML Engineer skills:
- Feature engineering for ML
- Model serialization (joblib)
- Inference pipeline design
"""

import os
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import json

# Optional sklearn imports (graceful degradation)
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    import joblib
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


@dataclass
class RiskFeatures:
    """Features extracted for risk classification."""
    version_jump_major: int  # Major version difference
    version_jump_minor: int  # Minor version difference
    version_jump_patch: int  # Patch version difference
    code_snippet_count: int  # Number of code snippets using the dep
    avg_snippet_length: float  # Average snippet complexity
    has_import_only: bool  # Only used in imports (low risk)
    has_deep_integration: bool  # Used in class inheritance, decorators
    has_config_usage: bool  # Used in configuration


class LocalRiskClassifier:
    """
    Local sklearn-based risk classifier.

    This is a simple model that provides fast risk assessment
    based on version differences and code usage patterns.
    Can be deployed to SageMaker for production use.
    """

    # Risk level mapping
    RISK_LABELS = {0: "low", 1: "medium", 2: "high"}

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the classifier.

        Args:
            model_path: Path to saved model. If None, creates a new model.
        """
        self._model = None
        self._vectorizer = None
        self._model_path = model_path or os.getenv(
            "LOCAL_MODEL_PATH", "./ml/model_artifacts/risk_classifier.joblib"
        )

        if SKLEARN_AVAILABLE:
            self._load_or_create_model()
        else:
            print("Warning: sklearn not installed. Using rule-based fallback.")

    def _load_or_create_model(self):
        """Load existing model or create a new one."""
        if os.path.exists(self._model_path):
            try:
                saved = joblib.load(self._model_path)
                self._model = saved['model']
                self._vectorizer = saved['vectorizer']
                print(f"Loaded model from {self._model_path}")
                return
            except Exception as e:
                print(f"Warning: Could not load model: {e}")

        # Create new model with default configuration
        self._model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight='balanced'
        )
        self._vectorizer = TfidfVectorizer(
            max_features=100,
            ngram_range=(1, 2)
        )
        print("Created new risk classifier model")

    def extract_features(
        self,
        dependency_name: str,
        current_version: str,
        new_version: str,
        code_snippets: List[str]
    ) -> RiskFeatures:
        """
        Extract ML features from dependency update context.

        Args:
            dependency_name: Name of the package
            current_version: Current version string
            new_version: Target version string
            code_snippets: Code snippets showing usage

        Returns:
            RiskFeatures dataclass with extracted features
        """
        # Parse version differences
        major_c, minor_c, patch_c = self._parse_version(current_version)
        major_n, minor_n, patch_n = self._parse_version(new_version)

        version_jump_major = major_n - major_c
        version_jump_minor = minor_n - minor_c
        version_jump_patch = patch_n - patch_c

        # Analyze code snippets
        code_snippet_count = len(code_snippets)
        avg_snippet_length = (
            sum(len(s) for s in code_snippets) / code_snippet_count
            if code_snippets else 0
        )

        # Pattern detection in code
        all_code = "\n".join(code_snippets)
        has_import_only = self._is_import_only(code_snippets)
        has_deep_integration = self._has_deep_integration(all_code, dependency_name)
        has_config_usage = self._has_config_usage(all_code, dependency_name)

        return RiskFeatures(
            version_jump_major=version_jump_major,
            version_jump_minor=version_jump_minor,
            version_jump_patch=version_jump_patch,
            code_snippet_count=code_snippet_count,
            avg_snippet_length=avg_snippet_length,
            has_import_only=has_import_only,
            has_deep_integration=has_deep_integration,
            has_config_usage=has_config_usage
        )

    def _parse_version(self, version: str) -> Tuple[int, int, int]:
        """Parse semver version string into (major, minor, patch)."""
        try:
            # Handle versions like "1.2.3", "1.2", "1"
            parts = version.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2].split("-")[0]) if len(parts) > 2 else 0
            return (major, minor, patch)
        except (ValueError, IndexError):
            return (0, 0, 0)

    def _is_import_only(self, snippets: List[str]) -> bool:
        """Check if the dependency is only used in import statements."""
        import_patterns = [
            r'^import\s+',
            r'^from\s+\w+\s+import'
        ]
        for snippet in snippets:
            is_import = any(re.match(p, snippet.strip()) for p in import_patterns)
            if not is_import:
                return False
        return True

    def _has_deep_integration(self, code: str, dep_name: str) -> bool:
        """Check for deep integration patterns."""
        deep_patterns = [
            rf'class\s+\w+\([^)]*{dep_name}',  # Class inheritance
            rf'@{dep_name}\.',  # Decorators
            rf'{dep_name}\.\w+\.\w+\.\w+',  # Deep attribute access
        ]
        return any(re.search(p, code, re.IGNORECASE) for p in deep_patterns)

    def _has_config_usage(self, code: str, dep_name: str) -> bool:
        """Check if used in configuration contexts."""
        config_patterns = [
            r'config',
            r'settings',
            r'\.configure\(',
            r'\.init\('
        ]
        return any(re.search(p, code, re.IGNORECASE) for p in config_patterns)

    def predict(
        self,
        dependency_name: str,
        current_version: str,
        new_version: str,
        code_snippets: List[str]
    ) -> Dict[str, any]:
        """
        Predict risk level for a dependency update.

        Args:
            dependency_name: Name of the package
            current_version: Current version
            new_version: Target version
            code_snippets: Code showing usage patterns

        Returns:
            Dict with risk_level, confidence, and explanation
        """
        features = self.extract_features(
            dependency_name, current_version, new_version, code_snippets
        )

        if not SKLEARN_AVAILABLE or self._model is None:
            # Rule-based fallback
            return self._rule_based_prediction(features)

        try:
            # Convert features to array
            X = self._features_to_array(features, code_snippets)

            # Predict
            prediction = self._model.predict(X)[0]
            probabilities = self._model.predict_proba(X)[0]

            risk_level = self.RISK_LABELS.get(prediction, "unknown")
            confidence = float(max(probabilities))

            return {
                "risk_level": risk_level,
                "confidence": confidence,
                "model": "random_forest",
                "explanation": self._generate_explanation(features, risk_level)
            }

        except Exception as e:
            print(f"Prediction error: {e}")
            return self._rule_based_prediction(features)

    def _features_to_array(self, features: RiskFeatures, snippets: List[str]):
        """Convert features to numpy array for sklearn."""
        # Numerical features
        numerical = np.array([[
            features.version_jump_major,
            features.version_jump_minor,
            features.version_jump_patch,
            features.code_snippet_count,
            features.avg_snippet_length,
            int(features.has_import_only),
            int(features.has_deep_integration),
            int(features.has_config_usage)
        ]])

        return numerical

    def _rule_based_prediction(self, features: RiskFeatures) -> Dict[str, any]:
        """Simple rule-based prediction when sklearn unavailable."""
        # Major version jump = high risk
        if features.version_jump_major > 0:
            if features.has_deep_integration:
                risk_level = "high"
            else:
                risk_level = "medium"
        # Only imports with minor/patch updates = low risk
        elif features.has_import_only and features.version_jump_major == 0:
            risk_level = "low"
        # Deep integration with any version change
        elif features.has_deep_integration:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "confidence": 0.7,  # Rule-based confidence
            "model": "rule_based",
            "explanation": self._generate_explanation(features, risk_level)
        }

    def _generate_explanation(self, features: RiskFeatures, risk_level: str) -> str:
        """Generate human-readable explanation."""
        reasons = []

        if features.version_jump_major > 0:
            reasons.append(f"major version jump (+{features.version_jump_major})")
        if features.has_deep_integration:
            reasons.append("deep integration patterns detected")
        if features.has_import_only:
            reasons.append("only used in imports")
        if features.code_snippet_count > 10:
            reasons.append(f"widely used ({features.code_snippet_count} occurrences)")

        if reasons:
            return f"Risk assessment based on: {', '.join(reasons)}"
        return "Standard update with no notable risk factors."

    def save(self, path: Optional[str] = None):
        """Save the model to disk."""
        if not SKLEARN_AVAILABLE:
            print("Cannot save: sklearn not available")
            return

        save_path = path or self._model_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        joblib.dump({
            'model': self._model,
            'vectorizer': self._vectorizer
        }, save_path)
        print(f"Model saved to {save_path}")

    def train(self, training_data: List[Dict]) -> None:
        """
        Train the model on historical assessment data.

        Args:
            training_data: List of dicts with keys:
                - dependency, current_version, new_version
                - code_snippets, risk_level (label)
        """
        if not SKLEARN_AVAILABLE:
            print("Cannot train: sklearn not available")
            return

        X_list = []
        y_list = []

        for record in training_data:
            features = self.extract_features(
                record['dependency'],
                record['current_version'],
                record['new_version'],
                record.get('code_snippets', [])
            )
            X = self._features_to_array(features, record.get('code_snippets', []))
            X_list.append(X[0])

            # Convert risk level to int
            risk_label = {'low': 0, 'medium': 1, 'high': 2}.get(
                record['risk_level'], 1
            )
            y_list.append(risk_label)

        X_train = np.array(X_list)
        y_train = np.array(y_list)

        self._model.fit(X_train, y_train)
        print(f"Model trained on {len(training_data)} samples")
