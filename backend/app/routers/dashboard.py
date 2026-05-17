"""Dashboard API routes — platform-wide overview and seed data."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ad_campaign import AdCampaign
from app.models.agent_log import AgentLog
from app.models.merchant import Merchant
from app.models.order import Order
from app.models.product import Product
from app.models.source_record import SourceRecord
from app.seed.seed_data import seed_demo_data

router = APIRouter()
_seed_lock = asyncio.Lock()


@router.get("/overview")
async def platform_overview(db: AsyncSession = Depends(get_db)):
    """Get platform-wide aggregated metrics."""
    merchants = (await db.execute(select(func.count(Merchant.id)))).scalar() or 0
    products = (await db.execute(select(func.count(Product.id)))).scalar() or 0
    orders = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    revenue = (await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0))
    )).scalar() or 0
    campaigns = (await db.execute(select(func.count(AdCampaign.id)))).scalar() or 0
    ad_spend = (await db.execute(
        select(func.coalesce(func.sum(AdCampaign.spend), 0))
    )).scalar() or 0
    source_records = (await db.execute(select(func.count(SourceRecord.id)))).scalar() or 0
    agent_recommendations = (await db.execute(select(func.count(AgentLog.id)))).scalar() or 0

    return {
        "merchants": merchants,
        "products": products,
        "orders": orders,
        "total_revenue": float(revenue),
        "campaigns": campaigns,
        "total_ad_spend": float(ad_spend),
        "source_records": source_records,
        "agent_recommendations": agent_recommendations,
    }


@router.post("/seed")
async def seed_data(db: AsyncSession = Depends(get_db)):
    """Seed the database with demo data for testing."""
    async with _seed_lock:
        result = await seed_demo_data(db)
        return result
