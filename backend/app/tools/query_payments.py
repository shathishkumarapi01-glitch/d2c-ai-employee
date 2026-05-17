"""Tool for querying Razorpay payments."""

from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment

def get_query_payments_schema() -> dict:
    return {
        "name": "query_payments",
        "description": "Query Razorpay payment records to inspect payment status, refunds, and payment-side anomalies.",
        "parameters": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string", "description": "Merchant UUID"},
                "limit": {"type": "integer", "description": "Max records to return", "default": 10},
                "status": {"type": "string", "description": "Filter by status (e.g., captured, refunded, failed)"},
                "customer_email": {"type": "string", "description": "Filter by customer email"},
                "order_id": {"type": "string", "description": "Filter by order ID"},
            },
            "required": ["merchant_id"],
        },
    }

async def execute_query_payments(
    db: AsyncSession, merchant_id: str, limit: int = 10,
    status: str | None = None, customer_email: str | None = None,
    order_id: str | None = None, **kwargs: Any
) -> dict:
    stmt = select(Payment).where(Payment.merchant_id == merchant_id)
    
    if status:
        stmt = stmt.where(Payment.status == status)
    if customer_email:
        stmt = stmt.where(Payment.customer_email == customer_email)
    if order_id:
        stmt = stmt.where(Payment.order_id == order_id)
        
    stmt = stmt.order_by(Payment.payment_date.desc()).limit(limit)
    
    result = await db.execute(stmt)
    payments = result.scalars().all()
    
    records = []
    source_refs = []
    
    for p in payments:
        records.append({
            "amount": p.amount,
            "currency": p.currency,
            "status": p.status,
            "order_id": p.order_id,
            "method": p.method,
            "customer_email": p.customer_email,
            "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        })
        source_refs.append({
            "source_platform": p.source_platform,
            "entity_type": "payment",
            "source_row_id": p.source_row_id,
        })
        
    return {
        "data": {
            "summary": f"Found {len(records)} payments matching criteria.",
            "records": records,
        },
        "source_refs": source_refs,
    }
