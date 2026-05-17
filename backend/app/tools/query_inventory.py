"""
Tool: query_inventory — Queries inventory levels from the database.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory

QUERY_INVENTORY_SCHEMA = {
    "name": "query_inventory",
    "description": "Query inventory levels for a merchant. Returns stock quantities, low-stock alerts with source references.",
    "parameters": {
        "type": "object",
        "properties": {
            "merchant_id": {"type": "string", "description": "Merchant UUID"},
            "low_stock_only": {"type": "boolean", "description": "Only return items below reorder point", "default": False},
            "location": {"type": "string", "description": "Filter by warehouse location", "default": ""},
            "aggregation": {"type": "string", "enum": ["summary", "detail", "both"], "default": "both"},
        },
        "required": ["merchant_id"],
    },
}


async def query_inventory(
    db: AsyncSession, merchant_id: str, low_stock_only: bool = False,
    location: str = "", aggregation: str = "both",
) -> dict[str, Any]:
    mid = merchant_id
    conditions = [Inventory.merchant_id == mid]
    if location:
        conditions.append(Inventory.location == location)

    result: dict[str, Any] = {"source_refs": [], "data": {}}

    if aggregation in ("summary", "both"):
        stmt = select(
            func.count(Inventory.id).label("total_items"),
            func.coalesce(func.sum(Inventory.quantity), 0).label("total_quantity"),
        ).where(and_(*conditions))
        row = (await db.execute(stmt)).first()

        low_stmt = select(func.count(Inventory.id)).where(
            and_(*conditions, Inventory.quantity <= Inventory.reorder_point)
        )
        low_count = (await db.execute(low_stmt)).scalar() or 0

        result["data"]["summary"] = {
            "total_items": int(row.total_items) if row else 0,
            "total_quantity": int(row.total_quantity) if row else 0,
            "low_stock_count": low_count,
        }

    if aggregation in ("detail", "both"):
        base_conditions = list(conditions)
        if low_stock_only:
            base_conditions.append(Inventory.quantity <= Inventory.reorder_point)
        stmt = select(Inventory).where(and_(*base_conditions)).order_by(Inventory.quantity.asc()).limit(50)
        items = (await db.execute(stmt)).scalars().all()
        result["data"]["inventory"] = []
        for inv in items:
            is_low = inv.quantity <= inv.reorder_point
            result["data"]["inventory"].append({
                "id": str(inv.id), "sku": inv.sku, "product_title": inv.product_title,
                "quantity": inv.quantity, "location": inv.location,
                "reorder_point": inv.reorder_point, "is_low_stock": is_low,
                "source_platform": inv.source_platform, "source_row_id": inv.source_row_id,
            })
            result["source_refs"].append({
                "source_platform": inv.source_platform, "entity_type": "inventory",
                "source_row_id": inv.source_row_id, "db_id": str(inv.id),
            })

    return result
