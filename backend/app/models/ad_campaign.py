"""Ad campaign model — normalized from Meta Ads, Google Ads, etc."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ProvenanceMixin, TimestampMixin, make_id


class AdCampaign(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "ad_campaigns"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: make_id("campaign")
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    campaign_name: Mapped[str] = mapped_column(String(512), nullable=False)
    campaign_id_external: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    objective: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Performance metrics
    spend: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    impressions: Mapped[int] = mapped_column(default=0)
    clicks: Mapped[int] = mapped_column(default=0)
    conversions: Mapped[int] = mapped_column(default=0)
    revenue: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    cpc: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    ctr: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    roas: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    # Date range
    date_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    merchant = relationship("Merchant", back_populates="ad_campaigns")

    __table_args__ = (
        Index("ix_campaigns_merchant_date", "merchant_id", "date_start"),
        Index("ix_campaigns_source", "source_platform", "source_row_id"),
        Index("ix_campaigns_status", "merchant_id", "status"),
        Index("ix_campaigns_roas", "merchant_id", "roas"),
    )

    def __repr__(self) -> str:
        return f"<AdCampaign {self.campaign_name} spend={self.spend} roas={self.roas}>"
