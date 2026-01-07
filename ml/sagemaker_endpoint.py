"""
AWS SageMaker endpoint management for risk classification.

Provides:
- Model deployment to SageMaker endpoints
- Real-time inference via endpoints
- Endpoint lifecycle management

Demonstrates AWS ML Engineer Associate skills:
- SageMaker endpoint deployment
- Model packaging and containerization
- Real-time inference patterns
- Cost optimization (endpoint auto-scaling)
"""

import os
import json
import tarfile
import tempfile
from typing import Dict, List, Optional
from datetime import datetime

from .local_model import LocalRiskClassifier, RiskFeatures


class SageMakerRiskClassifier:
    """
    AWS SageMaker-based risk classifier.

    Deploys the local sklearn model to a SageMaker endpoint
    for scalable, managed inference.
    """

    def __init__(
        self,
        endpoint_name: Optional[str] = None,
        region: Optional[str] = None,
        role_arn: Optional[str] = None
    ):
        """
        Initialize the SageMaker classifier.

        Args:
            endpoint_name: Name of existing endpoint (or SAGEMAKER_ENDPOINT env var)
            region: AWS region
            role_arn: IAM role for SageMaker (or SAGEMAKER_ROLE_ARN env var)
        """
        self._endpoint_name = endpoint_name or os.getenv("SAGEMAKER_ENDPOINT")
        self._region = region or os.getenv("AWS_REGION", "us-east-1")
        self._role_arn = role_arn or os.getenv("SAGEMAKER_ROLE_ARN")
        self._client = None
        self._runtime_client = None
        self._local_classifier = LocalRiskClassifier()
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize SageMaker clients."""
        try:
            import boto3
            from botocore.config import Config

            config = Config(
                retries={"max_attempts": 3, "mode": "adaptive"}
            )

            self._client = boto3.client(
                "sagemaker",
                region_name=self._region,
                config=config
            )
            self._runtime_client = boto3.client(
                "sagemaker-runtime",
                region_name=self._region,
                config=config
            )
            print(f"SageMaker clients initialized for region: {self._region}")

        except ImportError:
            print("Warning: boto3 not installed. SageMaker features disabled.")
        except Exception as e:
            print(f"Warning: Failed to initialize SageMaker clients: {e}")

    def is_available(self) -> bool:
        """Check if SageMaker endpoint is available."""
        if self._runtime_client is None or not self._endpoint_name:
            return False

        try:
            response = self._client.describe_endpoint(
                EndpointName=self._endpoint_name
            )
            return response['EndpointStatus'] == 'InService'
        except Exception:
            return False

    def predict(
        self,
        dependency_name: str,
        current_version: str,
        new_version: str,
        code_snippets: List[str]
    ) -> Dict[str, any]:
        """
        Predict risk using SageMaker endpoint.

        Falls back to local model if endpoint unavailable.

        Args:
            dependency_name: Package name
            current_version: Current version
            new_version: Target version
            code_snippets: Code usage patterns

        Returns:
            Dict with risk_level, confidence, model info
        """
        # Extract features using local classifier
        features = self._local_classifier.extract_features(
            dependency_name, current_version, new_version, code_snippets
        )

        if not self.is_available():
            print("SageMaker endpoint not available. Using local model.")
            return self._local_classifier.predict(
                dependency_name, current_version, new_version, code_snippets
            )

        try:
            # Prepare payload
            payload = {
                "features": {
                    "version_jump_major": features.version_jump_major,
                    "version_jump_minor": features.version_jump_minor,
                    "version_jump_patch": features.version_jump_patch,
                    "code_snippet_count": features.code_snippet_count,
                    "avg_snippet_length": features.avg_snippet_length,
                    "has_import_only": features.has_import_only,
                    "has_deep_integration": features.has_deep_integration,
                    "has_config_usage": features.has_config_usage
                },
                "dependency": dependency_name,
                "current_version": current_version,
                "new_version": new_version
            }

            # Invoke endpoint
            response = self._runtime_client.invoke_endpoint(
                EndpointName=self._endpoint_name,
                ContentType="application/json",
                Body=json.dumps(payload)
            )

            result = json.loads(response['Body'].read().decode())

            return {
                "risk_level": result.get("risk_level", "unknown"),
                "confidence": result.get("confidence", 0.5),
                "model": f"sagemaker/{self._endpoint_name}",
                "explanation": result.get("explanation", "SageMaker inference")
            }

        except Exception as e:
            print(f"SageMaker inference failed: {e}. Falling back to local.")
            return self._local_classifier.predict(
                dependency_name, current_version, new_version, code_snippets
            )

    def deploy_model(
        self,
        model_data_path: str,
        instance_type: str = "ml.t2.medium",
        initial_instance_count: int = 1
    ) -> str:
        """
        Deploy a trained model to SageMaker endpoint.

        Args:
            model_data_path: S3 path to model.tar.gz
            instance_type: EC2 instance type for endpoint
            initial_instance_count: Number of instances

        Returns:
            Endpoint name
        """
        if not self._client or not self._role_arn:
            raise ValueError("SageMaker client or role not configured")

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        model_name = f"risk-classifier-{timestamp}"
        endpoint_config_name = f"risk-classifier-config-{timestamp}"
        endpoint_name = f"risk-classifier-endpoint-{timestamp}"

        try:
            # Create model
            print(f"Creating model: {model_name}")
            self._client.create_model(
                ModelName=model_name,
                PrimaryContainer={
                    'Image': self._get_sklearn_image(),
                    'ModelDataUrl': model_data_path,
                    'Environment': {
                        'SAGEMAKER_PROGRAM': 'inference.py',
                        'SAGEMAKER_SUBMIT_DIRECTORY': model_data_path
                    }
                },
                ExecutionRoleArn=self._role_arn
            )

            # Create endpoint config
            print(f"Creating endpoint config: {endpoint_config_name}")
            self._client.create_endpoint_config(
                EndpointConfigName=endpoint_config_name,
                ProductionVariants=[{
                    'VariantName': 'primary',
                    'ModelName': model_name,
                    'InitialInstanceCount': initial_instance_count,
                    'InstanceType': instance_type
                }]
            )

            # Create endpoint
            print(f"Creating endpoint: {endpoint_name}")
            self._client.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name
            )

            # Wait for endpoint
            print("Waiting for endpoint to be in service...")
            waiter = self._client.get_waiter('endpoint_in_service')
            waiter.wait(EndpointName=endpoint_name)

            self._endpoint_name = endpoint_name
            print(f"Endpoint deployed: {endpoint_name}")
            return endpoint_name

        except Exception as e:
            print(f"Deployment failed: {e}")
            raise

    def _get_sklearn_image(self) -> str:
        """Get the SageMaker sklearn container image URI."""
        # Use SageMaker's pre-built sklearn container
        region = self._region
        account_map = {
            "us-east-1": "683313688378",
            "us-west-2": "246618743249",
            "eu-west-1": "141502667606",
            # Add more regions as needed
        }
        account = account_map.get(region, "683313688378")
        return f"{account}.dkr.ecr.{region}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3"

    def package_model(
        self,
        local_model_path: str,
        output_path: str
    ) -> str:
        """
        Package local model for SageMaker deployment.

        Creates model.tar.gz with model artifacts and inference code.

        Args:
            local_model_path: Path to local model file
            output_path: Output path for tar.gz

        Returns:
            Path to the created tar.gz
        """
        # Create inference.py for SageMaker
        inference_code = '''
import os
import json
import joblib
import numpy as np

def model_fn(model_dir):
    """Load model from the model directory."""
    model_path = os.path.join(model_dir, "model.joblib")
    return joblib.load(model_path)

def input_fn(request_body, request_content_type):
    """Parse input data."""
    if request_content_type == "application/json":
        data = json.loads(request_body)
        return data
    raise ValueError(f"Unsupported content type: {request_content_type}")

def predict_fn(input_data, model):
    """Make prediction."""
    features = input_data["features"]
    X = np.array([[
        features["version_jump_major"],
        features["version_jump_minor"],
        features["version_jump_patch"],
        features["code_snippet_count"],
        features["avg_snippet_length"],
        int(features["has_import_only"]),
        int(features["has_deep_integration"]),
        int(features["has_config_usage"])
    ]])

    clf = model["model"]
    prediction = clf.predict(X)[0]
    probabilities = clf.predict_proba(X)[0]

    risk_labels = {0: "low", 1: "medium", 2: "high"}
    return {
        "risk_level": risk_labels.get(prediction, "unknown"),
        "confidence": float(max(probabilities))
    }

def output_fn(prediction, response_content_type):
    """Format output."""
    if response_content_type == "application/json":
        return json.dumps(prediction)
    raise ValueError(f"Unsupported content type: {response_content_type}")
'''

        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy model
            import shutil
            model_dest = os.path.join(tmpdir, "model.joblib")
            shutil.copy(local_model_path, model_dest)

            # Write inference code
            inference_path = os.path.join(tmpdir, "inference.py")
            with open(inference_path, 'w') as f:
                f.write(inference_code)

            # Create tar.gz
            with tarfile.open(output_path, "w:gz") as tar:
                tar.add(model_dest, arcname="model.joblib")
                tar.add(inference_path, arcname="inference.py")

        print(f"Model packaged: {output_path}")
        return output_path

    def delete_endpoint(self, endpoint_name: Optional[str] = None):
        """Delete a SageMaker endpoint to stop charges."""
        name = endpoint_name or self._endpoint_name
        if not name:
            print("No endpoint to delete")
            return

        try:
            # Delete endpoint
            self._client.delete_endpoint(EndpointName=name)
            print(f"Deleted endpoint: {name}")

            # Delete endpoint config
            self._client.delete_endpoint_config(
                EndpointConfigName=name.replace("endpoint", "config")
            )

            # Delete model
            self._client.delete_model(
                ModelName=name.replace("endpoint", "model")
            )

        except Exception as e:
            print(f"Error deleting endpoint: {e}")

    def get_endpoint_metrics(self) -> Dict[str, any]:
        """Get CloudWatch metrics for the endpoint."""
        if not self.is_available():
            return {"status": "unavailable"}

        try:
            import boto3
            cw = boto3.client("cloudwatch", region_name=self._region)

            # Get invocation metrics
            response = cw.get_metric_statistics(
                Namespace="AWS/SageMaker",
                MetricName="Invocations",
                Dimensions=[
                    {"Name": "EndpointName", "Value": self._endpoint_name},
                    {"Name": "VariantName", "Value": "primary"}
                ],
                StartTime=datetime.utcnow().replace(hour=0, minute=0, second=0),
                EndTime=datetime.utcnow(),
                Period=3600,
                Statistics=["Sum"]
            )

            total_invocations = sum(
                dp['Sum'] for dp in response.get('Datapoints', [])
            )

            return {
                "endpoint_name": self._endpoint_name,
                "status": "InService",
                "invocations_today": int(total_invocations),
                "region": self._region
            }

        except Exception as e:
            return {"error": str(e)}
