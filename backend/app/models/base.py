"""
SQLAlchemy shared mixins and ID helper.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def make_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(8)}"


class TimestampMixin:
    """Adds created_at / updated_at to any model."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ProvenanceMixin:
    """
    Tracks data origin on every row.
    Every piece of data knows where it came from and when it was synced.
    """
    source_platform: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="Origin platform: shopify, meta_ads, google_sheets, manual"
    )
    source_row_id: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Original ID from the source system"
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="When this record was last synced from source"
    )
    raw_payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Original unmodified payload from source for auditability"
    )
