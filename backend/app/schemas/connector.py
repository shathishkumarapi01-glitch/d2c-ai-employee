"""Pydantic schemas for connector operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConnectorHealth(BaseModel):
    """Health status of a connector."""
    name: str
    status: str = Field(description="healthy | degraded | error | mock")
    mock_mode: bool = False
    last_sync: datetime | None = None
    error: str | None = None
    records_synced: int = 0


class ConnectorListResponse(BaseModel):
    """List of all connectors and their status."""
    connectors: list[ConnectorHealth]


class SyncRequest(BaseModel):
    """Request to trigger a connector sync."""
    merchant_id: str
    full_sync: bool = False


class SyncResult(BaseModel):
    """Result of a connector sync operation."""
    connector: str
    merchant_id: str
    status: str
    records_fetched: int = 0
    records_normalized: int = 0
    records_saved: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class NormalizedRecord(BaseModel):
    """A single normalized record ready for database insertion."""
    entity_type: str
    source_platform: str
    source_row_id: str
    data: dict[str, Any]
    raw_payload: dict[str, Any]
