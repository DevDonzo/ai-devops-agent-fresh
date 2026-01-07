"""
Local JSON storage provider for development and fallback.

Stores assessment records as JSON files in a local directory.
Useful for development and testing when cloud storage is not configured.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from ..base import StorageProvider, AssessmentRecord


class LocalStorageProvider(StorageProvider):
    """
    Local file system implementation of StorageProvider.

    Stores data in JSON files organized by date for easy browsing.
    Structure:
        data/assessments/
            2024/
                01/
                    06/
                        assessment_123456.json
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the local storage provider.

        Args:
            base_path: Base directory for storage (default: ./data/assessments)
        """
        self._base_path = Path(
            base_path or os.getenv("LOCAL_STORAGE_PATH", "./data/assessments")
        )
        self._ensure_directory()

    def _ensure_directory(self):
        """Create the base directory if it doesn't exist."""
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _get_partition_path(self, timestamp: datetime) -> Path:
        """Get the partition path for a given timestamp (year/month/day)."""
        return self._base_path / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"

    def _generate_filename(self, record: AssessmentRecord) -> str:
        """Generate a unique filename for a record."""
        ts = record.timestamp.strftime("%H%M%S%f")
        return f"assessment_{record.dependency}_{ts}.json"

    @property
    def provider_name(self) -> str:
        return "local"

    def is_available(self) -> bool:
        """Local storage is always available."""
        return True

    def save_assessment(self, record: AssessmentRecord) -> bool:
        """
        Save an assessment record to local storage.

        Args:
            record: The assessment record to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            partition_path = self._get_partition_path(record.timestamp)
            partition_path.mkdir(parents=True, exist_ok=True)

            file_path = partition_path / self._generate_filename(record)

            with open(file_path, 'w') as f:
                json.dump(record.to_dict(), f, indent=2)

            print(f"Assessment saved to: {file_path}")
            return True

        except Exception as e:
            print(f"Error saving assessment: {e}")
            return False

    def get_assessments(
        self,
        dependency: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AssessmentRecord]:
        """
        Retrieve assessment records from local storage.

        Args:
            dependency: Filter by dependency name (optional)
            start_date: Filter by start date (optional)
            end_date: Filter by end date (optional)
            limit: Maximum number of records to return

        Returns:
            List of matching assessment records
        """
        records = []

        try:
            # Walk through all JSON files
            for json_file in self._base_path.rglob("*.json"):
                if len(records) >= limit:
                    break

                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)

                    # Parse timestamp
                    record_time = datetime.fromisoformat(data['timestamp'])

                    # Apply filters
                    if dependency and data['dependency'] != dependency:
                        continue
                    if start_date and record_time < start_date:
                        continue
                    if end_date and record_time > end_date:
                        continue

                    # Create record object
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

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Warning: Could not parse {json_file}: {e}")
                    continue

        except Exception as e:
            print(f"Error reading assessments: {e}")

        # Sort by timestamp descending (most recent first)
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate statistics from stored assessments.

        Returns:
            Dictionary with counts and distributions
        """
        all_records = self.get_assessments(limit=10000)

        if not all_records:
            return {
                "total_assessments": 0,
                "risk_distribution": {},
                "provider_distribution": {},
                "dependencies_analyzed": 0
            }

        risk_counts = {}
        provider_counts = {}
        dependencies = set()

        for record in all_records:
            # Count risk levels
            risk_counts[record.risk_level] = risk_counts.get(record.risk_level, 0) + 1

            # Count providers
            provider_counts[record.llm_provider] = provider_counts.get(record.llm_provider, 0) + 1

            # Track unique dependencies
            dependencies.add(record.dependency)

        return {
            "total_assessments": len(all_records),
            "risk_distribution": risk_counts,
            "provider_distribution": provider_counts,
            "dependencies_analyzed": len(dependencies),
            "date_range": {
                "earliest": all_records[-1].timestamp.isoformat() if all_records else None,
                "latest": all_records[0].timestamp.isoformat() if all_records else None
            }
        }
