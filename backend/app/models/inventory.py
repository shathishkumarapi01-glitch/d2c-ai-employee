"""Inventory model — stock levels normalized from any source."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ProvenanceMixin, TimestampMixin, make_id


class Inventory(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "inventory"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: make_id("inventory")
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    location: Mapped[str] = mapped_column(String(255), default="default")
    reorder_point: Mapped[int] = mapped_column(Integer, default=10)

    merchant = relationship("Merchant", back_populates="inventory_items")

    __table_args__ = (
        Index("ix_inventory_merchant_product", "merchant_id", "product_id"),
        Index("ix_inventory_source", "source_platform", "source_row_id"),
        Index("ix_inventory_low_stock", "merchant_id", "quantity"),
    )

    def __repr__(self) -> str:
        return f"<Inventory {self.sku} qty={self.quantity}>"
