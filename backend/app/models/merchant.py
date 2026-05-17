"""Merchant model — top-level tenant entity."""

from __future__ import annotations

from sqlalchemy import JSON, String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, make_id


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: make_id("merchant")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(64), default="free")
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    products = relationship("Product", back_populates="merchant", lazy="selectin")
    orders = relationship("Order", back_populates="merchant", lazy="selectin")
    inventory_items = relationship("Inventory", back_populates="merchant", lazy="selectin")
    ad_campaigns = relationship("AdCampaign", back_populates="merchant", lazy="selectin")
    source_records = relationship("SourceRecord", back_populates="merchant", lazy="selectin")
    agent_logs = relationship("AgentLog", back_populates="merchant", lazy="selectin")
    chat_sessions = relationship("ChatSession", back_populates="merchant", lazy="selectin")

    __table_args__ = (
        Index("ix_merchants_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Merchant {self.name} ({self.id})>"
