"""
Azure Blob Storage provider for assessment data.

Stores assessment records in Azure Blob Storage with
hierarchical namespace support for efficient querying.

Demonstrates Azure DP-700 skills:
- Azure Blob Storage patterns
- Azure Identity (DefaultAzureCredential)
- Data lake organization
- Integration with Synapse Analytics
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

from ..base import StorageProvider, AssessmentRecord


class AzureBlobProvider(StorageProvider):
    """
    Azure Blob Storage implementation of StorageProvider.

    Supports both connection string and Azure AD authentication.
    Organizes data in a hierarchical structure compatible with
    Azure Synapse Analytics serverless SQL pools.
    """

    def __init__(
        self,
        account_url: Optional[str] = None,
        container_name: str = "assessments",
        use_azure_ad: bool = True
    ):
        """
        Initialize the Azure Blob storage provider.

        Args:
            account_url: Storage account URL (or AZURE_STORAGE_ACCOUNT_URL env var)
            container_name: Blob container name
            use_azure_ad: Use Azure AD auth (recommended) vs connection string
        """
        self._account_url = account_url or os.getenv("AZURE_STORAGE_ACCOUNT_URL")
        self._container_name = container_name
        self._use_azure_ad = use_azure_ad
        self._client = None
        self._container_client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Azure Blob client."""
        if not self._account_url:
            # Try connection string as fallback
            conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            if conn_str:
                self._initialize_from_connection_string(conn_str)
            else:
                print("Warning: AZURE_STORAGE_ACCOUNT_URL or AZURE_STORAGE_CONNECTION_STRING not set")
            return

        try:
            from azure.storage.blob import BlobServiceClient

            if self._use_azure_ad:
                from azure.identity import DefaultAzureCredential
                credential = DefaultAzureCredential()
                self._client = BlobServiceClient(
                    account_url=self._account_url,
                    credential=credential
                )
                print("Azure Blob client initialized with Azure AD auth")
            else:
                # Use account key from environment
                account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
                if not account_key:
                    print("Warning: AZURE_STORAGE_ACCOUNT_KEY not set")
                    return
                self._client = BlobServiceClient(
                    account_url=self._account_url,
                    credential=account_key
                )
                print("Azure Blob client initialized with account key")

            self._container_client = self._client.get_container_client(self._container_name)
            self._ensure_container()

        except ImportError:
            print("Warning: azure-storage-blob not installed. Run: pip install azure-storage-blob azure-identity")
            self._client = None
        except Exception as e:
            print(f"Warning: Failed to initialize Azure Blob client: {e}")
            self._client = None

    def _initialize_from_connection_string(self, conn_str: str):
        """Initialize using a connection string."""
        try:
            from azure.storage.blob import BlobServiceClient
            self._client = BlobServiceClient.from_connection_string(conn_str)
            self._container_client = self._client.get_container_client(self._container_name)
            self._ensure_container()
            print("Azure Blob client initialized with connection string")
        except Exception as e:
            print(f"Warning: Failed to initialize from connection string: {e}")
            self._client = None

    def _ensure_container(self):
        """Create container if it doesn't exist."""
        try:
            self._container_client.create_container()
            print(f"Created container: {self._container_name}")
        except Exception:
            # Container already exists
            pass

    def _get_blob_path(self, timestamp: datetime) -> str:
        """
        Get the hierarchical path for a timestamp.

        Format: year=YYYY/month=MM/day=DD/
        Compatible with Synapse serverless SQL.
        """
        return (
            f"year={timestamp.year}/"
            f"month={timestamp.month:02d}/"
            f"day={timestamp.day:02d}/"
        )

    def _generate_blob_name(self, record: AssessmentRecord) -> str:
        """Generate a unique blob name for a record."""
        path = self._get_blob_path(record.timestamp)
        ts = record.timestamp.strftime("%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{path}{record.dependency}_{ts}_{unique_id}.json"

    @property
    def provider_name(self) -> str:
        return "azure_blob"

    def is_available(self) -> bool:
        """Check if Azure Blob is properly configured."""
        if self._container_client is None:
            return False

        try:
            # Verify container access
            self._container_client.get_container_properties()
            return True
        except Exception:
            return False

    def save_assessment(self, record: AssessmentRecord) -> bool:
        """
        Save an assessment record to Azure Blob Storage.

        Args:
            record: The assessment record to save

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.is_available():
            print("Azure Blob not available. Check storage configuration.")
            return False

        try:
            blob_name = self._generate_blob_name(record)
            blob_client = self._container_client.get_blob_client(blob_name)

            data = json.dumps(record.to_dict(), indent=2)

            blob_client.upload_blob(
                data,
                overwrite=True,
                metadata={
                    "dependency": record.dependency,
                    "risk_level": record.risk_level,
                    "llm_provider": record.llm_provider
                }
            )

            print(f"Assessment saved to: {self._container_name}/{blob_name}")
            return True

        except Exception as e:
            print(f"Error saving to Azure Blob: {e}")
            return False

    def get_assessments(
        self,
        dependency: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AssessmentRecord]:
        """
        Retrieve assessment records from Azure Blob Storage.

        Note: For production with large datasets, use Synapse serverless SQL.

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

        try:
            blobs = self._container_client.list_blobs()

            for blob in blobs:
                if len(records) >= limit:
                    break
                if not blob.name.endswith('.json'):
                    continue

                try:
                    blob_client = self._container_client.get_blob_client(blob.name)
                    content = blob_client.download_blob().readall().decode('utf-8')
                    data = json.loads(content)

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
                    print(f"Warning: Could not parse {blob.name}: {e}")
                    continue

        except Exception as e:
            print(f"Error listing blobs: {e}")

        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregate statistics from Azure Blob Storage."""
        all_records = self.get_assessments(limit=10000)

        if not all_records:
            return {
                "total_assessments": 0,
                "storage_location": f"{self._account_url}/{self._container_name}"
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
            "storage_location": f"{self._account_url}/{self._container_name}",
            "synapse_compatible": True
        }
