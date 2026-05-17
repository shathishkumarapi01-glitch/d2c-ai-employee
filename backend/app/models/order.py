"""Order model — normalized from any source platform."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ProvenanceMixin, TimestampMixin, make_id


class Order(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: make_id("order")
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    order_number: Mapped[str] = mapped_column(String(128), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    financial_status: Mapped[str] = mapped_column(String(64), default="pending")
    fulfillment_status: Mapped[str] = mapped_column(String(64), default="unfulfilled")
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_date: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    line_items: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    shipping_address: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)

    merchant = relationship("Merchant", back_populates="orders")

    __table_args__ = (
        Index("ix_orders_merchant_date", "merchant_id", "order_date"),
        Index("ix_orders_source", "source_platform", "source_row_id"),
        Index("ix_orders_financial_status", "merchant_id", "financial_status"),
    )

    def __repr__(self) -> str:
        return f"<Order #{self.order_number} ₹{self.total_amount}>"
