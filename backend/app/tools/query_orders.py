"""
Tool: query_orders — Queries order data from the database.
Returns structured results with source references for citation tracking.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order

# OpenAI function calling schema
QUERY_ORDERS_SCHEMA = {
    "name": "query_orders",
    "description": "Query order data for a merchant. Returns order counts, revenue totals, and individual order details with source references for citations.",
    "parameters": {
        "type": "object",
        "properties": {
            "merchant_id": {
                "type": "string",
                "description": "The merchant UUID to query orders for.",
            },
            "days_back": {
                "type": "integer",
                "description": (
                    "Number of days to look back. Use 7 for last week/recent week, "
                    "30 for last month. Default 60."
                ),
                "default": 60,
            },
            "financial_status": {
                "type": "string",
                "description": "Filter by financial status: paid, pending, refunded. Leave empty for all.",
                "enum": ["paid", "pending", "refunded", ""],
            },
            "aggregation": {
                "type": "string",
                "description": "Type of aggregation: summary (totals), detail (individual orders), both.",
                "enum": ["summary", "detail", "both"],
                "default": "both",
            },
        },
        "required": ["merchant_id"],
    },
}


async def query_orders(
    db: AsyncSession,
    merchant_id: str,
    days_back: int = 60,
    financial_status: str = "",
    aggregation: str = "both",
) -> dict[str, Any]:
    """
    Query orders and return structured data with source_refs for citations.
    Every numerical value includes a traceable source reference.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_back)
    mid = merchant_id

    conditions = [
        Order.merchant_id == mid,
        Order.order_date >= cutoff,
    ]
    if financial_status:
        conditions.append(Order.financial_status == financial_status)

    result: dict[str, Any] = {"source_refs": [], "data": {}}
    effective_conditions = list(conditions)

    requested_count_stmt = select(func.count(Order.id)).where(and_(*conditions))
    requested_count = (await db.execute(requested_count_stmt)).scalar() or 0

    data_coverage: dict[str, Any] = {
        "requested_period_days": days_back,
        "requested_start": cutoff.isoformat(),
        "requested_end": now.isoformat(),
        "used_latest_available_window": False,
    }

    if requested_count == 0:
        latest_conditions = [Order.merchant_id == mid]
        if financial_status:
            latest_conditions.append(Order.financial_status == financial_status)

        latest_order = (
            await db.execute(
                select(Order)
                .where(and_(*latest_conditions))
                .order_by(Order.order_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if latest_order:
            fallback_end = latest_order.order_date
            fallback_start = fallback_end - timedelta(days=days_back)
            effective_conditions = [
                Order.merchant_id == mid,
                Order.order_date >= fallback_start,
                Order.order_date <= fallback_end,
            ]
            if financial_status:
                effective_conditions.append(Order.financial_status == financial_status)

            data_coverage.update({
                "used_latest_available_window": True,
                "latest_order_date": fallback_end.isoformat(),
                "analysis_start": fallback_start.isoformat(),
                "analysis_end": fallback_end.isoformat(),
                "note": (
                    "No orders were found in the requested period, so the tool "
                    "returned the latest available order window with data."
                ),
            })
        else:
            data_coverage["note"] = "No order data exists for this merchant yet."

    result["data"]["data_coverage"] = data_coverage

    if aggregation in ("summary", "both"):
        stmt = select(
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total_amount), 0).label("total_revenue"),
            func.coalesce(func.avg(Order.total_amount), 0).label("avg_order_value"),
        ).where(and_(*effective_conditions))

        row = (await db.execute(stmt)).first()
        total_orders = int(row.total_orders) if row else 0
        total_revenue = float(row.total_revenue) if row else 0
        avg_order_value = round(float(row.avg_order_value), 2) if row else 0

        result["data"]["summary"] = {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "avg_order_value": avg_order_value,
            "period_days": days_back,
            "financial_status": financial_status or "all",
            "currency": "INR",
        }

        # Source refs for summary numbers — reference the aggregation query itself
        detail_stmt = select(Order.id, Order.source_platform, Order.source_row_id).where(and_(*effective_conditions))
        order_rows = (await db.execute(detail_stmt)).all()
        for orow in order_rows:
            result["source_refs"].append({
                "source_platform": orow.source_platform,
                "entity_type": "order",
                "source_row_id": orow.source_row_id,
                "db_id": str(orow.id),
            })

    if aggregation in ("detail", "both"):
        stmt = (
            select(Order)
            .where(and_(*effective_conditions))
            .order_by(Order.order_date.desc())
            .limit(50)
        )
        orders = (await db.execute(stmt)).scalars().all()
        result["data"]["orders"] = [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "total_amount": float(o.total_amount),
                "currency": o.currency,
                "financial_status": o.financial_status,
                "fulfillment_status": o.fulfillment_status,
                "order_date": o.order_date.isoformat(),
                "source_platform": o.source_platform,
                "source_row_id": o.source_row_id,
            }
            for o in orders
        ]

    return result
