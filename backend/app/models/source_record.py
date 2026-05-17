"""Source record — append-only log of every raw ingestion for full data lineage."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, make_id


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: make_id("source")
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    source_platform: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    sync_status: Mapped[str] = mapped_column(String(32), default="ingested")
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    merchant = relationship("Merchant", back_populates="source_records")

    __table_args__ = (
        Index("ix_source_records_merchant", "merchant_id", "ingested_at"),
        Index("ix_source_records_platform", "source_platform", "entity_type"),
        Index("ix_source_records_source_id", "source_platform", "source_row_id"),
    )

    def __repr__(self) -> str:
        return f"<SourceRecord {self.source_platform}.{self.entity_type}.{self.source_row_id}>"
