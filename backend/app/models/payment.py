"""Payment model — represents a payment transaction (e.g., Razorpay)."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String, JSON

from app.models.base import Base, ProvenanceMixin, TimestampMixin, make_id


class Payment(Base, ProvenanceMixin, TimestampMixin):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=lambda: make_id("payment"))
    merchant_id = Column(String(36), index=True, nullable=False)

    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    status = Column(String, index=True)
    order_id = Column(String, index=True)
    method = Column(String)
    customer_email = Column(String, index=True)

    payment_date = Column(DateTime())
    tags = Column(String, default="")
