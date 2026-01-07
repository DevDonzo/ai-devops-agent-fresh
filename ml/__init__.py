"""
ML components for the DevOps Intelligence Platform.

Provides:
- SageMaker endpoint deployment and inference
- Local model for testing without AWS
- Feature extraction utilities
"""

from .sagemaker_endpoint import SageMakerRiskClassifier
from .local_model import LocalRiskClassifier

__all__ = [
    "SageMakerRiskClassifier",
    "LocalRiskClassifier",
]
