"""Product model — normalized from any source platform."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ProvenanceMixin, TimestampMixin, make_id


class Product(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: make_id("product")
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[str] = mapped_column(String(32), default="active")
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    merchant = relationship("Merchant", back_populates="products")

    __table_args__ = (
        Index("ix_products_merchant_created", "merchant_id", "created_at"),
        Index("ix_products_source", "source_platform", "source_row_id"),
        Index("ix_products_sku", "merchant_id", "sku"),
    )

    def __repr__(self) -> str:
        return f"<Product {self.title} ({self.sku})>"
