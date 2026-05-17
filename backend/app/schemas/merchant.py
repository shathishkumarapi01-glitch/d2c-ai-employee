"""Pydantic schemas for merchant operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MerchantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: str | None = None
    plan: str = "free"
    settings: dict[str, Any] | None = None


class MerchantResponse(BaseModel):
    id: str
    name: str
    domain: str | None
    plan: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MerchantDashboard(BaseModel):
    """Aggregated merchant metrics for the dashboard."""
    merchant_id: str
    merchant_name: str
    total_products: int = 0
    total_orders: int = 0
    total_revenue: float = 0.0
    total_ad_spend: float = 0.0
    active_campaigns: int = 0
    low_stock_items: int = 0
    recent_agent_recommendations: int = 0
    connector_statuses: dict[str, str] = Field(default_factory=dict)


class MerchantListResponse(BaseModel):
    merchants: list[MerchantResponse]
    total: int
