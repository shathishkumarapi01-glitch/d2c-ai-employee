"""
Tool: query_campaigns — Queries ad campaign data from the database.
Returns performance metrics with source references for citations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ad_campaign import AdCampaign

QUERY_CAMPAIGNS_SCHEMA = {
    "name": "query_campaigns",
    "description": "Query ad campaign performance data for a merchant. Returns spend, impressions, clicks, conversions, ROAS with source references.",
    "parameters": {
        "type": "object",
        "properties": {
            "merchant_id": {
                "type": "string",
                "description": "The merchant UUID to query campaigns for.",
            },
            "status": {
                "type": "string",
                "description": "Filter by campaign status: active, paused, completed.",
                "enum": ["active", "paused", "completed", ""],
            },
            "min_spend": {
                "type": "number",
                "description": "Minimum spend threshold to filter campaigns.",
            },
            "aggregation": {
                "type": "string",
                "description": "summary for totals, detail for individual campaigns, both for all.",
                "enum": ["summary", "detail", "both"],
                "default": "both",
            },
        },
        "required": ["merchant_id"],
    },
}


async def query_campaigns(
    db: AsyncSession,
    merchant_id: str,
    status: str = "",
    min_spend: float = 0,
    aggregation: str = "both",
) -> dict[str, Any]:
    """Query campaigns with full provenance tracking."""
    mid = merchant_id

    conditions = [AdCampaign.merchant_id == mid]
    if status:
        conditions.append(AdCampaign.status == status)
    if min_spend > 0:
        conditions.append(AdCampaign.spend >= min_spend)

    result: dict[str, Any] = {"source_refs": [], "data": {}}

    if aggregation in ("summary", "both"):
        stmt = select(
            func.count(AdCampaign.id).label("total_campaigns"),
            func.coalesce(func.sum(AdCampaign.spend), 0).label("total_spend"),
            func.coalesce(func.sum(AdCampaign.revenue), 0).label("total_revenue"),
            func.coalesce(func.sum(AdCampaign.impressions), 0).label("total_impressions"),
            func.coalesce(func.sum(AdCampaign.clicks), 0).label("total_clicks"),
            func.coalesce(func.sum(AdCampaign.conversions), 0).label("total_conversions"),
        ).where(and_(*conditions))

        row = (await db.execute(stmt)).first()
        total_spend = float(row.total_spend) if row else 0
        total_revenue = float(row.total_revenue) if row else 0

        result["data"]["summary"] = {
            "total_campaigns": int(row.total_campaigns) if row else 0,
            "total_spend": total_spend,
            "total_revenue": total_revenue,
            "total_impressions": int(row.total_impressions) if row else 0,
            "total_clicks": int(row.total_clicks) if row else 0,
            "total_conversions": int(row.total_conversions) if row else 0,
            "overall_roas": round(total_revenue / total_spend, 2) if total_spend > 0 else 0,
            "currency": "INR",
        }

    if aggregation in ("detail", "both"):
        stmt = select(AdCampaign).where(and_(*conditions)).order_by(AdCampaign.spend.desc())
        campaigns = (await db.execute(stmt)).scalars().all()
        result["data"]["campaigns"] = []
        for c in campaigns:
            result["data"]["campaigns"].append({
                "id": str(c.id),
                "campaign_name": c.campaign_name,
                "status": c.status,
                "spend": float(c.spend),
                "revenue": float(c.revenue),
                "impressions": c.impressions,
                "clicks": c.clicks,
                "conversions": c.conversions,
                "roas": float(c.roas) if c.roas else 0,
                "cpc": float(c.cpc) if c.cpc else 0,
                "source_platform": c.source_platform,
                "source_row_id": c.source_row_id,
            })
            result["source_refs"].append({
                "source_platform": c.source_platform,
                "entity_type": "ad_campaign",
                "source_row_id": c.source_row_id,
                "db_id": str(c.id),
            })

    return result
