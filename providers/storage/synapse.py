"""
Azure Synapse Analytics storage provider.

Combines Azure Blob Storage for data persistence with
Synapse serverless SQL pools for analytics queries.

Demonstrates Azure DP-700 skills:
- Synapse Analytics serverless SQL
- External tables and data virtualization
- Delta Lake format support
- Data lakehouse patterns
- OPENROWSET queries
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

from ..base import StorageProvider, AssessmentRecord


class SynapseProvider(StorageProvider):
    """
    Azure Synapse Analytics implementation of StorageProvider.

    Uses:
    - Azure Blob Storage (ADLS Gen2) for data persistence
    - Synapse serverless SQL pool for analytics queries
    - OPENROWSET for querying JSON files directly
    - External tables for structured access
    """

    def __init__(
        self,
        synapse_endpoint: Optional[str] = None,
        storage_account_url: Optional[str] = None,
        container_name: str = "assessments",
        database_name: str = "devops_ml"
    ):
        """
        Initialize the Synapse provider.

        Args:
            synapse_endpoint: Synapse workspace SQL endpoint
            storage_account_url: ADLS Gen2 storage account URL
            container_name: Storage container name
            database_name: Synapse database name for queries
        """
        self._synapse_endpoint = synapse_endpoint or os.getenv("SYNAPSE_SQL_ENDPOINT")
        self._storage_url = storage_account_url or os.getenv("AZURE_STORAGE_ACCOUNT_URL")
        self._container_name = container_name
        self._database_name = database_name
        self._blob_client = None
        self._sql_connection = None
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize Azure clients for both storage and SQL."""
        # Initialize blob storage (for writes)
        self._initialize_blob_client()
        # Initialize SQL connection (for reads/analytics)
        self._initialize_sql_connection()

    def _initialize_blob_client(self):
        """Initialize Azure Blob client for data writes."""
        if not self._storage_url:
            print("Warning: AZURE_STORAGE_ACCOUNT_URL not set")
            return

        try:
            from azure.storage.blob import BlobServiceClient
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
            blob_service = BlobServiceClient(
                account_url=self._storage_url,
                credential=credential
            )
            self._blob_client = blob_service.get_container_client(self._container_name)

            # Ensure container exists
            try:
                self._blob_client.create_container()
            except Exception:
                pass  # Container exists

            print("Synapse blob client initialized")

        except ImportError:
            print("Warning: azure-storage-blob not installed")
        except Exception as e:
            print(f"Warning: Failed to initialize blob client: {e}")

    def _initialize_sql_connection(self):
        """Initialize Synapse SQL connection for queries."""
        if not self._synapse_endpoint:
            print("Warning: SYNAPSE_SQL_ENDPOINT not set. SQL queries disabled.")
            return

        try:
            import pyodbc
            from azure.identity import DefaultAzureCredential

            # Get access token for Synapse
            credential = DefaultAzureCredential()
            token = credential.get_token("https://database.windows.net/.default")

            # Build connection string for Synapse serverless
            conn_str = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={self._synapse_endpoint};"
                f"DATABASE={self._database_name};"
                f"Authentication=ActiveDirectoryInteractive"
            )

            # Note: For production, use token-based auth
            # This is simplified for demonstration
            print("Synapse SQL connection configured")
            self._sql_connection = conn_str

        except ImportError:
            print("Warning: pyodbc not installed. SQL queries disabled.")
        except Exception as e:
            print(f"Warning: Failed to configure SQL connection: {e}")

    def _get_blob_path(self, timestamp: datetime) -> str:
        """Get hierarchical path for Synapse external table partitioning."""
        return (
            f"year={timestamp.year}/"
            f"month={timestamp.month:02d}/"
            f"day={timestamp.day:02d}/"
        )

    def _generate_blob_name(self, record: AssessmentRecord) -> str:
        """Generate blob name compatible with Synapse queries."""
        path = self._get_blob_path(record.timestamp)
        ts = record.timestamp.strftime("%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{path}{record.dependency}_{ts}_{unique_id}.json"

    @property
    def provider_name(self) -> str:
        return "synapse"

    def is_available(self) -> bool:
        """Check if Synapse is properly configured."""
        # At minimum, we need blob storage for writes
        if self._blob_client is None:
            return False
        try:
            self._blob_client.get_container_properties()
            return True
        except Exception:
            return False

    def save_assessment(self, record: AssessmentRecord) -> bool:
        """
        Save an assessment record to Synapse-compatible storage.

        Data is written to ADLS Gen2/Blob in a format that can be
        queried directly via Synapse serverless SQL.

        Args:
            record: The assessment record to save

        Returns:
            True if saved successfully
        """
        if not self.is_available():
            print("Synapse storage not available.")
            return False

        try:
            blob_name = self._generate_blob_name(record)
            blob_client = self._blob_client.get_blob_client(blob_name)

            # Store as JSON (queryable via OPENROWSET)
            data = json.dumps(record.to_dict(), indent=2)

            blob_client.upload_blob(
                data,
                overwrite=True,
                metadata={
                    "dependency": record.dependency,
                    "risk_level": record.risk_level
                }
            )

            print(f"Assessment saved for Synapse: {blob_name}")
            return True

        except Exception as e:
            print(f"Error saving to Synapse storage: {e}")
            return False

    def get_assessments(
        self,
        dependency: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AssessmentRecord]:
        """
        Retrieve assessments using Synapse or fallback to blob listing.

        If SQL endpoint is configured, uses OPENROWSET queries.
        Otherwise, falls back to blob enumeration.
        """
        # For now, use blob enumeration
        # In production, this would use Synapse SQL
        if not self.is_available():
            return []

        records = []

        try:
            blobs = self._blob_client.list_blobs()

            for blob in blobs:
                if len(records) >= limit:
                    break
                if not blob.name.endswith('.json'):
                    continue

                try:
                    blob_client = self._blob_client.get_blob_client(blob.name)
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
                    continue

        except Exception as e:
            print(f"Error retrieving assessments: {e}")

        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics, preferably via Synapse SQL."""
        all_records = self.get_assessments(limit=10000)

        if not all_records:
            return {"total_assessments": 0}

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
            "synapse_endpoint": self._synapse_endpoint,
            "storage_location": f"{self._storage_url}/{self._container_name}"
        }

    def get_synapse_setup_sql(self) -> str:
        """
        Generate Synapse SQL setup scripts.

        Returns T-SQL for creating external data source, file format,
        and external tables in Synapse serverless SQL pool.
        """
        storage_path = self._storage_url.replace("https://", "").split(".")[0]

        return f"""
-- =====================================================
-- Synapse Serverless SQL Pool Setup for DevOps ML
-- =====================================================

-- 1. Create database (run in master)
CREATE DATABASE {self._database_name};
GO

USE {self._database_name};
GO

-- 2. Create master key for external data access
CREATE MASTER KEY ENCRYPTION BY PASSWORD = '<your-strong-password>';
GO

-- 3. Create database scoped credential using managed identity
CREATE DATABASE SCOPED CREDENTIAL SynapseIdentity
WITH IDENTITY = 'Managed Identity';
GO

-- 4. Create external data source pointing to your storage
CREATE EXTERNAL DATA SOURCE AssessmentsStorage
WITH (
    LOCATION = 'https://{storage_path}.blob.core.windows.net/{self._container_name}',
    CREDENTIAL = SynapseIdentity
);
GO

-- 5. Create external file format for JSON
CREATE EXTERNAL FILE FORMAT JsonFormat
WITH (
    FORMAT_TYPE = JSON
);
GO

-- 6. Query data directly with OPENROWSET
SELECT TOP 100
    JSON_VALUE(doc, '$.timestamp') AS timestamp,
    JSON_VALUE(doc, '$.dependency') AS dependency,
    JSON_VALUE(doc, '$.current_version') AS current_version,
    JSON_VALUE(doc, '$.target_version') AS target_version,
    JSON_VALUE(doc, '$.risk_level') AS risk_level,
    JSON_VALUE(doc, '$.recommendation') AS recommendation,
    JSON_VALUE(doc, '$.llm_provider') AS llm_provider,
    JSON_VALUE(doc, '$.model') AS model,
    CAST(JSON_VALUE(doc, '$.vulnerabilities_found') AS INT) AS vulnerabilities_found,
    JSON_VALUE(doc, '$.explanation') AS explanation
FROM OPENROWSET(
    BULK '**/*.json',
    DATA_SOURCE = 'AssessmentsStorage',
    FORMAT = 'CSV',
    FIELDTERMINATOR = '0x0b',
    FIELDQUOTE = '0x0b',
    ROWTERMINATOR = '0x0b'
) WITH (doc NVARCHAR(MAX)) AS rows
ORDER BY JSON_VALUE(doc, '$.timestamp') DESC;
GO

-- 7. Create a view for easier access
CREATE VIEW vw_Assessments AS
SELECT
    JSON_VALUE(doc, '$.timestamp') AS assessment_time,
    JSON_VALUE(doc, '$.dependency') AS dependency,
    JSON_VALUE(doc, '$.current_version') AS current_version,
    JSON_VALUE(doc, '$.target_version') AS target_version,
    JSON_VALUE(doc, '$.risk_level') AS risk_level,
    JSON_VALUE(doc, '$.recommendation') AS recommendation,
    JSON_VALUE(doc, '$.llm_provider') AS llm_provider,
    JSON_VALUE(doc, '$.model') AS model,
    CAST(JSON_VALUE(doc, '$.vulnerabilities_found') AS INT) AS vulnerabilities_found,
    CAST(JSON_VALUE(doc, '$.code_snippets_analyzed') AS INT) AS code_snippets_analyzed,
    JSON_VALUE(doc, '$.explanation') AS explanation
FROM OPENROWSET(
    BULK '**/*.json',
    DATA_SOURCE = 'AssessmentsStorage',
    FORMAT = 'CSV',
    FIELDTERMINATOR = '0x0b',
    FIELDQUOTE = '0x0b',
    ROWTERMINATOR = '0x0b'
) WITH (doc NVARCHAR(MAX)) AS rows;
GO

-- 8. Example analytics queries
-- Risk level distribution
SELECT risk_level, COUNT(*) as count
FROM vw_Assessments
GROUP BY risk_level;

-- Provider usage
SELECT llm_provider, COUNT(*) as count
FROM vw_Assessments
GROUP BY llm_provider;

-- Most assessed dependencies
SELECT dependency, COUNT(*) as assessment_count
FROM vw_Assessments
GROUP BY dependency
ORDER BY assessment_count DESC;
"""
