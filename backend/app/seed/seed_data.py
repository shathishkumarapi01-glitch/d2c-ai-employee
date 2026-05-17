"""
Seed data — populates the database with realistic demo data.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ad_campaign import AdCampaign
from app.models.agent_log import AgentLog
from app.models.chat import ChatMessage, ChatSession
from app.models.inventory import Inventory
from app.models.merchant import Merchant
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.source_record import SourceRecord

logger = logging.getLogger(__name__)

MERCHANT_1_ID = "merchant-001"
MERCHANT_2_ID = "merchant-002"


async def seed_demo_data(db: AsyncSession) -> dict:
    """Seed the database with demo data."""
    demo_ids = [MERCHANT_1_ID, MERCHANT_2_ID]
    await _reset_demo_merchants(db, demo_ids)

    merchants = [
        Merchant(
            id=MERCHANT_1_ID,
            name="ThreadCraft",
            domain="threadcraft.in",
            plan="growth",
            settings={"currency": "INR", "timezone": "Asia/Kolkata"},
        ),
        Merchant(
            id=MERCHANT_2_ID,
            name="GreenLeaf Organics",
            domain="greenleaf.co.in",
            plan="starter",
            settings={"currency": "INR", "timezone": "Asia/Kolkata"},
        ),
    ]

    for m in merchants:
        db.add(m)
    await db.flush()

    from app.services.sync_service import sync_service

    results = []
    for merchant in merchants:
        sync_results = await sync_service.sync_all(db, str(merchant.id))
        results.extend(sync_results)

    await db.flush()
    await db.commit()

    from app.agents.ad_spend_analyzer import ad_spend_analyzer

    agent_results = []
    for merchant in merchants:
        try:
            recs = await ad_spend_analyzer.run(db, merchant.id, trigger="seed")
            agent_results.extend(recs)
        except Exception:
            logger.exception(
                "Agent recommendations failed during seed for merchant=%s",
                merchant.id,
            )

    await db.flush()
    await db.commit()

    summary = {
        "status": "seeded",
        "merchants_created": len(merchants),
        "merchant_ids": [str(m.id) for m in merchants],
        "sync_results": [
            {"connector": r.connector, "records": r.records_saved, "status": r.status}
            for r in results
        ],
        "agent_recommendations": len(agent_results),
    }

    logger.info("Database seeded: %s", summary)
    return summary


async def _reset_demo_merchants(db: AsyncSession, merchant_ids: list[str]) -> None:
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(
        select(ChatSession.id).where(ChatSession.merchant_id.in_(merchant_ids))
    )))
    await db.execute(delete(ChatSession).where(ChatSession.merchant_id.in_(merchant_ids)))
    await db.execute(delete(AgentLog).where(AgentLog.merchant_id.in_(merchant_ids)))
    await db.execute(delete(SourceRecord).where(SourceRecord.merchant_id.in_(merchant_ids)))
    await db.execute(delete(Payment).where(Payment.merchant_id.in_(merchant_ids)))
    await db.execute(delete(Inventory).where(Inventory.merchant_id.in_(merchant_ids)))
    await db.execute(delete(Order).where(Order.merchant_id.in_(merchant_ids)))
    await db.execute(delete(Product).where(Product.merchant_id.in_(merchant_ids)))
    await db.execute(delete(AdCampaign).where(AdCampaign.merchant_id.in_(merchant_ids)))
    await db.execute(delete(Merchant).where(Merchant.id.in_(merchant_ids)))
    await db.flush()
