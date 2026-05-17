"""
Abstract base connector interface.
All connectors (Shopify, Meta Ads, Google Sheets, etc.) must implement this.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.connector import ConnectorHealth, NormalizedRecord, SyncResult


class BaseConnector(ABC):
    """
    Shared connector interface.
    Every connector follows the same contract: fetch → normalize → sync.
    """

    name: str = "base"
    platform: str = "unknown"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._mock_mode = False

    @property
    def mock_mode(self) -> bool:
        return self._mock_mode

    @mock_mode.setter
    def mock_mode(self, value: bool) -> None:
        self._mock_mode = value

    @abstractmethod
    async def fetch_data(self, merchant_id: str, params: dict[str, Any] | None = None) -> list[dict]:
        """
        Fetch raw data from the external platform.
        Returns a list of raw records as dicts.
        In mock mode, returns realistic sample data.
        """
        ...

    @abstractmethod
    def normalize(self, raw_data: list[dict]) -> list[NormalizedRecord]:
        """
        Transform raw platform-specific data into normalized records.
        Each record includes source_platform and source_row_id for provenance.
        """
        ...

    @abstractmethod
    async def sync(self, merchant_id: str, params: dict[str, Any] | None = None) -> SyncResult:
        """
        Full sync pipeline: fetch → normalize → return results.
        The caller (SyncService) handles database persistence.
        """
        ...

    @abstractmethod
    def health_check(self) -> ConnectorHealth:
        """
        Check the health/availability of this connector.
        Returns status: healthy | degraded | error | mock
        """
        ...

    async def _fetch_with_retry(self, fetch_fn, max_retries: int = 3, **kwargs) -> Any:
        """Utility: retry HTTP calls with exponential backoff."""
        import asyncio

        last_error = None
        for attempt in range(max_retries):
            try:
                return await fetch_fn(**kwargs)
            except Exception as e:
                last_error = e
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)

        raise last_error
