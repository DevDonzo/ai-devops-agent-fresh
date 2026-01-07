# AWS Setup Guide

This guide covers setting up AWS services for the ML DevOps Intelligence Platform.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Python 3.9+

## Services Used

| Service | Purpose | Required |
|---------|---------|----------|
| AWS Bedrock | LLM inference (Claude 3, Titan) | Optional |
| Amazon S3 | Data lake storage | Optional |
| SageMaker | ML model deployment | Optional |
| IAM | Access management | Required |

## Step 1: Configure AWS Credentials

### Option A: AWS CLI (Recommended for Development)

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter your default region (e.g., us-east-1)
```

### Option B: Environment Variables

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
```

### Option C: IAM Role (Recommended for Production)

If running on EC2/ECS/Lambda, attach an IAM role with the necessary permissions.

## Step 2: Enable AWS Bedrock

AWS Bedrock requires explicit model access.

### 2.1 Request Model Access

1. Go to [AWS Bedrock Console](https://console.aws.amazon.com/bedrock)
2. Navigate to "Model access" in the left sidebar
3. Click "Manage model access"
4. Enable the following models:
   - Anthropic Claude 3 Sonnet
   - Anthropic Claude 3 Haiku
   - Amazon Titan Text Express

### 2.2 IAM Policy for Bedrock

Create a policy with these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-sonnet-*",
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-*",
                "arn:aws:bedrock:*::foundation-model/amazon.titan-text-express-v1"
            ]
        }
    ]
}
```

### 2.3 Test Bedrock Access

```python
import boto3

client = boto3.client('bedrock-runtime', region_name='us-east-1')
response = client.invoke_model(
    modelId='anthropic.claude-3-sonnet-20240229-v1:0',
    contentType='application/json',
    accept='application/json',
    body='{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"Hello"}]}'
)
print(response)
```

## Step 3: Set Up S3 Bucket

### 3.1 Create Bucket

```bash
aws s3 mb s3://your-devops-ml-bucket --region us-east-1
```

### 3.2 Enable Versioning (Recommended)

```bash
aws s3api put-bucket-versioning \
    --bucket your-devops-ml-bucket \
    --versioning-configuration Status=Enabled
```

### 3.3 IAM Policy for S3

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::your-devops-ml-bucket",
                "arn:aws:s3:::your-devops-ml-bucket/*"
            ]
        }
    ]
}
```

### 3.4 Configure Environment

```bash
export S3_BUCKET=your-devops-ml-bucket
export S3_PREFIX=assessments
export STORAGE_PROVIDER=s3
```

## Step 4: Set Up SageMaker (Optional)

### 4.1 Create SageMaker Execution Role

```bash
# Create trust policy
cat > trust-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "sagemaker.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF

# Create role
aws iam create-role \
    --role-name SageMakerDevOpsMLRole \
    --assume-role-policy-document file://trust-policy.json

# Attach policies
aws iam attach-role-policy \
    --role-name SageMakerDevOpsMLRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

aws iam attach-role-policy \
    --role-name SageMakerDevOpsMLRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```

### 4.2 Train and Deploy Model

```python
from ml import LocalRiskClassifier, SageMakerRiskClassifier

# Train locally first
classifier = LocalRiskClassifier()
# ... train with your data ...
classifier.save('./ml/model_artifacts/risk_classifier.joblib')

# Package for SageMaker
sm_classifier = SageMakerRiskClassifier()
sm_classifier.package_model(
    local_model_path='./ml/model_artifacts/risk_classifier.joblib',
    output_path='./model.tar.gz'
)

# Upload to S3
aws s3 cp ./model.tar.gz s3://your-devops-ml-bucket/models/

# Deploy endpoint
endpoint_name = sm_classifier.deploy_model(
    model_data_path='s3://your-devops-ml-bucket/models/model.tar.gz',
    instance_type='ml.t2.medium'
)

print(f"Endpoint deployed: {endpoint_name}")
```

### 4.3 Configure Environment

```bash
export SAGEMAKER_ENDPOINT=risk-classifier-endpoint-YYYYMMDD-HHMMSS
export SAGEMAKER_ROLE_ARN=arn:aws:iam::123456789:role/SageMakerDevOpsMLRole
export USE_SAGEMAKER=true
```

## Step 5: Set Up Athena (Optional)

For SQL analytics on S3 data:

### 5.1 Create Database

```sql
CREATE DATABASE devops_ml;
```

### 5.2 Create Table

Run the SQL from the S3 storage provider:

```python
from providers.storage.s3 import S3StorageProvider

provider = S3StorageProvider()
print(provider.get_athena_create_table_sql())
```

### 5.3 Query Data

```sql
SELECT
    dependency,
    risk_level,
    COUNT(*) as count
FROM devops_ml.assessments
GROUP BY dependency, risk_level
ORDER BY count DESC;
```

## Cost Optimization

### Bedrock Pricing
- Claude 3 Sonnet: ~$3 per 1M input tokens, ~$15 per 1M output tokens
- Claude 3 Haiku: ~$0.25 per 1M input tokens, ~$1.25 per 1M output tokens

**Tip**: Use local classifier for pre-screening to reduce LLM calls.

### SageMaker Pricing
- ml.t2.medium: ~$0.05/hour
- **Tip**: Delete endpoints when not in use:
  ```python
  sm_classifier.delete_endpoint()
  ```

### S3 Pricing
- Storage: ~$0.023/GB/month
- Requests: ~$0.0004 per 1000 PUT/GET

## Troubleshooting

### "Access Denied" for Bedrock

1. Verify model access is enabled in Bedrock console
2. Check IAM policy includes bedrock:InvokeModel
3. Verify region matches (Bedrock not available in all regions)

### "NoCredentialsError"

1. Run `aws configure` to set up credentials
2. Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY env vars

### SageMaker Endpoint Stuck "Creating"

1. Check CloudWatch logs for errors
2. Verify IAM role has necessary permissions
3. Ensure model.tar.gz is properly formatted

## Complete IAM Policy

For all AWS features, use this combined policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": "*"
        },
        {
            "Sid": "S3Access",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-devops-ml-bucket",
                "arn:aws:s3:::your-devops-ml-bucket/*"
            ]
        },
        {
            "Sid": "SageMakerAccess",
            "Effect": "Allow",
            "Action": [
                "sagemaker:CreateModel",
                "sagemaker:CreateEndpointConfig",
                "sagemaker:CreateEndpoint",
                "sagemaker:DescribeEndpoint",
                "sagemaker:InvokeEndpoint",
                "sagemaker:DeleteEndpoint",
                "sagemaker:DeleteEndpointConfig",
                "sagemaker:DeleteModel"
            ],
            "Resource": "*"
        }
    ]
}
```
