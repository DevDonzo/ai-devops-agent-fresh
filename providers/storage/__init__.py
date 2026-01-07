"""
Storage providers for assessment data persistence.

Supports:
- Local JSON files (development/fallback)
- AWS S3 with Athena-compatible partitioning
- Azure Blob Storage
- Azure Synapse Analytics (serverless SQL)
"""

import os
from typing import Optional
from ..base import StorageProvider


def get_storage_provider(provider_name: Optional[str] = None) -> StorageProvider:
    """
    Factory function to get the appropriate storage provider.

    Args:
        provider_name: One of 'local', 's3', 'azure_blob', 'synapse'.
                      If None, uses STORAGE_PROVIDER env var or defaults to 'local'.

    Returns:
        Configured storage provider instance

    Raises:
        ValueError: If provider is not recognized or not available
    """
    if provider_name is None:
        provider_name = os.getenv("STORAGE_PROVIDER", "local").lower()

    if provider_name == "local":
        from .local import LocalStorageProvider
        provider = LocalStorageProvider()
    elif provider_name == "s3":
        from .s3 import S3StorageProvider
        provider = S3StorageProvider()
    elif provider_name == "azure_blob":
        from .azure_blob import AzureBlobProvider
        provider = AzureBlobProvider()
    elif provider_name == "synapse":
        from .synapse import SynapseProvider
        provider = SynapseProvider()
    else:
        raise ValueError(
            f"Unknown storage provider: {provider_name}. "
            "Supported: local, s3, azure_blob, synapse"
        )

    if not provider.is_available():
        print(f"Warning: Storage provider '{provider_name}' not available, falling back to local")
        from .local import LocalStorageProvider
        provider = LocalStorageProvider()

    return provider


__all__ = ["get_storage_provider"]
