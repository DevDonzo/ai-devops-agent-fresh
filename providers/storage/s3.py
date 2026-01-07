"""
AWS S3 storage provider for assessment data.

Stores assessment records in S3 with Hive-style partitioning
for efficient querying via AWS Athena.

Partition scheme: s3://bucket/prefix/year=YYYY/month=MM/day=DD/

Demonstrates AWS ML Engineer Associate skills:
- S3 data lake patterns
- Hive-style partitioning for Athena
- boto3 SDK usage
- IAM credential handling
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

from ..base import StorageProvider, AssessmentRecord


class S3StorageProvider(StorageProvider):
    """
    AWS S3 implementation of StorageProvider.

    Uses Hive-style partitioning (year=YYYY/month=MM/day=DD)
    which is compatible with AWS Athena for SQL queries.
    """

    def __init__(
        self,
        bucket: Optional[str] = None,
        prefix: str = "assessments",
        region: Optional[str] = None
    ):
        """
        Initialize the S3 storage provider.

        Args:
            bucket: S3 bucket name (or S3_BUCKET env var)
            prefix: Key prefix for all objects (default: assessments)
            region: AWS region (or AWS_REGION env var)
        """
        self._bucket = bucket or os.getenv("S3_BUCKET")
        self._prefix = prefix
        self._region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the S3 client."""
        if not self._bucket:
            print("Warning: S3_BUCKET not set")
            return

        try:
            import boto3
            from botocore.config import Config

            config = Config(
                retries={"max_attempts": 3, "mode": "adaptive"}
            )

            self._client = boto3.client(
                "s3",
                region_name=self._region,
                config=config
            )
            print(f"S3 client initialized for bucket: {self._bucket}")

        except ImportError:
            print("Warning: boto3 not installed. Run: pip install boto3")
            self._client = None
        except Exception as e:
            print(f"Warning: Failed to initialize S3 client: {e}")
            self._client = None

    def _get_partition_prefix(self, timestamp: datetime) -> str:
        """
        Get the Hive-style partition prefix for a timestamp.

        Format: prefix/year=YYYY/month=MM/day=DD/
        """
        return (
            f"{self._prefix}/"
            f"year={timestamp.year}/"
            f"month={timestamp.month:02d}/"
            f"day={timestamp.day:02d}/"
        )

    def _generate_key(self, record: AssessmentRecord) -> str:
        """Generate a unique S3 key for a record."""
        partition = self._get_partition_prefix(record.timestamp)
        ts = record.timestamp.strftime("%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{partition}{record.dependency}_{ts}_{unique_id}.json"

    @property
    def provider_name(self) -> str:
        return "s3"

    def is_available(self) -> bool:
        """Check if S3 is properly configured."""
        if self._client is None or not self._bucket:
            return False

        try:
            # Verify bucket access
            self._client.head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            return False

    def save_assessment(self, record: AssessmentRecord) -> bool:
        """
        Save an assessment record to S3.

        Args:
            record: The assessment record to save

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.is_available():
            print("S3 not available. Check bucket configuration.")
            return False

        try:
            key = self._generate_key(record)
            body = json.dumps(record.to_dict(), indent=2)

            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType="application/json",
                Metadata={
                    "dependency": record.dependency,
                    "risk_level": record.risk_level,
                    "llm_provider": record.llm_provider
                }
            )

            print(f"Assessment saved to: s3://{self._bucket}/{key}")
            return True

        except Exception as e:
            print(f"Error saving to S3: {e}")
            return False

    def get_assessments(
        self,
        dependency: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AssessmentRecord]:
        """
        Retrieve assessment records from S3.

        Note: For production use with large datasets, use Athena instead.
        This method is for small-scale retrieval only.

        Args:
            dependency: Filter by dependency name (optional)
            start_date: Filter by start date (optional)
            end_date: Filter by end date (optional)
            limit: Maximum number of records to return

        Returns:
            List of matching assessment records
        """
        if not self.is_available():
            return []

        records = []
        paginator = self._client.get_paginator('list_objects_v2')

        try:
            # List all objects (inefficient for large datasets - use Athena)
            for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    if len(records) >= limit:
                        break
                    if not obj['Key'].endswith('.json'):
                        continue

                    try:
                        response = self._client.get_object(
                            Bucket=self._bucket,
                            Key=obj['Key']
                        )
                        data = json.loads(response['Body'].read().decode('utf-8'))

                        # Parse and filter
                        record_time = datetime.fromisoformat(data['timestamp'])

                        if dependency and data['dependency'] != dependency:
                            continue
                        if start_date and record_time < start_date:
                            continue
                        if end_date and record_time > end_date:
                            continue

                        record = AssessmentRecord(
                            timestamp=record_time,
                            dependency=data['dependency'],
                            current_version=data['current_version'],
                            target_version=data['target_version'],
                            risk_level=data['risk_level'],
                            recommendation=data['recommendation'],
                            llm_provider=data['llm_provider'],
                            model=data['model'],
                            vulnerabilities_found=data['vulnerabilities_found'],
                            code_snippets_analyzed=data['code_snippets_analyzed'],
                            explanation=data['explanation']
                        )
                        records.append(record)

                    except Exception as e:
                        print(f"Warning: Could not parse {obj['Key']}: {e}")
                        continue

                if len(records) >= limit:
                    break

        except Exception as e:
            print(f"Error listing S3 objects: {e}")

        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate statistics from S3.

        Note: For production, use Athena queries instead.
        """
        all_records = self.get_assessments(limit=10000)

        if not all_records:
            return {
                "total_assessments": 0,
                "storage_location": f"s3://{self._bucket}/{self._prefix}/"
            }

        risk_counts = {}
        provider_counts = {}
        dependencies = set()

        for record in all_records:
            risk_counts[record.risk_level] = risk_counts.get(record.risk_level, 0) + 1
            provider_counts[record.llm_provider] = provider_counts.get(record.llm_provider, 0) + 1
            dependencies.add(record.dependency)

        return {
            "total_assessments": len(all_records),
            "risk_distribution": risk_counts,
            "provider_distribution": provider_counts,
            "dependencies_analyzed": len(dependencies),
            "storage_location": f"s3://{self._bucket}/{self._prefix}/",
            "athena_compatible": True
        }

    def get_athena_create_table_sql(self, database: str = "devops_ml", table: str = "assessments") -> str:
        """
        Generate the Athena CREATE TABLE statement for querying this data.

        This can be used to set up Athena for SQL analysis of assessments.
        """
        return f"""
CREATE EXTERNAL TABLE IF NOT EXISTS {database}.{table} (
    timestamp STRING,
    dependency STRING,
    current_version STRING,
    target_version STRING,
    risk_level STRING,
    recommendation STRING,
    llm_provider STRING,
    model STRING,
    vulnerabilities_found INT,
    code_snippets_analyzed INT,
    explanation STRING
)
PARTITIONED BY (
    year STRING,
    month STRING,
    day STRING
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://{self._bucket}/{self._prefix}/'
TBLPROPERTIES ('has_encrypted_data'='false');

-- After creating, run:
-- MSCK REPAIR TABLE {database}.{table};
"""
