"""Merchant API routes — CRUD and dashboard data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ad_campaign import AdCampaign
from app.models.agent_log import AgentLog
from app.models.inventory import Inventory
from app.models.merchant import Merchant
from app.models.order import Order
from app.models.product import Product
from app.schemas.merchant import (
    MerchantCreate,
    MerchantDashboard,
    MerchantListResponse,
    MerchantResponse,
)

router = APIRouter()


@router.get("", response_model=MerchantListResponse)
async def list_merchants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Merchant).order_by(Merchant.created_at.desc()))
    merchants = result.scalars().all()
    return MerchantListResponse(
        merchants=[MerchantResponse.model_validate(m) for m in merchants],
        total=len(merchants),
    )


@router.post("", response_model=MerchantResponse)
async def create_merchant(data: MerchantCreate, db: AsyncSession = Depends(get_db)):
    merchant = Merchant(**data.model_dump())
    db.add(merchant)
    await db.flush()
    await db.refresh(merchant)
    return MerchantResponse.model_validate(merchant)


@router.get("/{merchant_id}", response_model=MerchantResponse)
async def get_merchant(merchant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    merchant = result.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return MerchantResponse.model_validate(merchant)


@router.get("/{merchant_id}/dashboard", response_model=MerchantDashboard)
async def get_merchant_dashboard(merchant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    merchant = result.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    products_count = (await db.execute(
        select(func.count(Product.id)).where(Product.merchant_id == merchant_id)
    )).scalar() or 0

    order_stats = (await db.execute(
        select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
        ).where(Order.merchant_id == merchant_id)
    )).first()

    campaign_stats = (await db.execute(
        select(
            func.count(AdCampaign.id),
            func.coalesce(func.sum(AdCampaign.spend), 0),
        ).where(and_(
            AdCampaign.merchant_id == merchant_id,
            AdCampaign.status == "active",
        ))
    )).first()

    low_stock = (await db.execute(
        select(func.count(Inventory.id)).where(and_(
            Inventory.merchant_id == merchant_id,
            Inventory.quantity <= Inventory.reorder_point,
        ))
    )).scalar() or 0

    agent_recs = (await db.execute(
        select(func.count(AgentLog.id)).where(and_(
            AgentLog.merchant_id == merchant_id,
            AgentLog.status == "pending",
        ))
    )).scalar() or 0

    return MerchantDashboard(
        merchant_id=merchant_id,
        merchant_name=merchant.name,
        total_products=products_count,
        total_orders=order_stats[0] if order_stats else 0,
        total_revenue=float(order_stats[1]) if order_stats else 0,
        total_ad_spend=float(campaign_stats[1]) if campaign_stats else 0,
        active_campaigns=campaign_stats[0] if campaign_stats else 0,
        low_stock_items=low_stock,
        recent_agent_recommendations=agent_recs,
    )
