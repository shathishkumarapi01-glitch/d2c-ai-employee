"""Agent log — stores autonomous agent reasoning, recommendations, and citations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, make_id


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: make_id("agent")
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger: Mapped[str] = mapped_column(String(64), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_savings: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    citations: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=list,
    )
    status: Mapped[str] = mapped_column(String(32), default="pending")
    metadata_extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    merchant = relationship("Merchant", back_populates="agent_logs")

    __table_args__ = (
        Index("ix_agent_logs_merchant", "merchant_id", "created_at"),
        Index("ix_agent_logs_type", "agent_type", "status"),
    )

    def __repr__(self) -> str:
        return f"<AgentLog {self.agent_type} confidence={self.confidence_score}>"
