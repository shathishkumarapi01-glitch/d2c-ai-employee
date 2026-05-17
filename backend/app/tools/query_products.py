"""
Tool: query_products — Queries product catalog from the database.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product

QUERY_PRODUCTS_SCHEMA = {
    "name": "query_products",
    "description": "Query product catalog for a merchant. Returns product details with source references.",
    "parameters": {
        "type": "object",
        "properties": {
            "merchant_id": {"type": "string", "description": "Merchant UUID"},
            "status": {"type": "string", "enum": ["active", "draft", "archived", ""], "default": ""},
            "category": {"type": "string", "description": "Filter by category", "default": ""},
            "aggregation": {"type": "string", "enum": ["summary", "detail", "both"], "default": "both"},
        },
        "required": ["merchant_id"],
    },
}


async def query_products(
    db: AsyncSession, merchant_id: str, status: str = "", category: str = "", aggregation: str = "both",
) -> dict[str, Any]:
    mid = merchant_id
    conditions = [Product.merchant_id == mid]
    if status:
        conditions.append(Product.status == status)
    if category:
        conditions.append(Product.category == category)

    result: dict[str, Any] = {"source_refs": [], "data": {}}

    if aggregation in ("summary", "both"):
        stmt = select(
            func.count(Product.id).label("total"),
            func.coalesce(func.avg(Product.price), 0).label("avg_price"),
            func.coalesce(func.min(Product.price), 0).label("min_price"),
            func.coalesce(func.max(Product.price), 0).label("max_price"),
        ).where(and_(*conditions))
        row = (await db.execute(stmt)).first()
        result["data"]["summary"] = {
            "total_products": int(row.total) if row else 0,
            "avg_price": round(float(row.avg_price), 2) if row else 0,
            "min_price": float(row.min_price) if row else 0,
            "max_price": float(row.max_price) if row else 0,
        }

    if aggregation in ("detail", "both"):
        stmt = select(Product).where(and_(*conditions)).order_by(Product.title).limit(50)
        products = (await db.execute(stmt)).scalars().all()
        result["data"]["products"] = []
        for p in products:
            result["data"]["products"].append({
                "id": str(p.id), "title": p.title, "sku": p.sku,
                "price": float(p.price), "currency": p.currency, "status": p.status,
                "category": p.category, "source_platform": p.source_platform,
                "source_row_id": p.source_row_id,
            })
            result["source_refs"].append({
                "source_platform": p.source_platform, "entity_type": "product",
                "source_row_id": p.source_row_id, "db_id": str(p.id),
            })

    return result
