"""
Celery tasks — background jobs for sync and agent operations.
Uses synchronous SQLAlchemy sessions since Celery workers run in sync context.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worker.celery_app import celery_app
from app.database import async_session_factory

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run an async coroutine in a sync context (for Celery)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_connector_task(self, connector_name: str, merchant_id: str):
    """Background task: sync a single connector for a merchant."""
    async def _sync():
        from app.services.sync_service import sync_service
        async with async_session_factory() as db:
            try:
                result = await sync_service.sync_connector(db, connector_name, merchant_id)
                await db.commit()
                logger.info("Sync complete: %s for %s — %s", connector_name, merchant_id, result.status)
                return {"status": result.status, "records_saved": result.records_saved}
            except Exception as e:
                await db.rollback()
                logger.error("Sync failed: %s", str(e))
                raise

    try:
        return run_async(_sync())
    except Exception as e:
        logger.error("Task failed, retrying: %s", str(e))
        raise self.retry(exc=e)


@celery_app.task
def sync_all_merchants():
    """Periodic task: sync all connectors for all active merchants."""
    async def _sync_all():
        from app.services.sync_service import sync_service
        from app.models.merchant import Merchant

        async with async_session_factory() as db:
            result = await db.execute(
                select(Merchant).where(Merchant.is_active == True)
            )
            merchants = result.scalars().all()

            for merchant in merchants:
                for connector_name in ["shopify", "meta_ads", "google_sheets"]:
                    # Queue individual sync tasks
                    sync_connector_task.delay(connector_name, str(merchant.id))

            logger.info("Queued sync for %d merchants", len(merchants))

    run_async(_sync_all())


@celery_app.task
def run_ad_spend_analyzer(merchant_id: str):
    """Background task: run ad spend analyzer for a merchant."""
    async def _analyze():
        from app.agents.ad_spend_analyzer import ad_spend_analyzer
        from uuid import UUID

        async with async_session_factory() as db:
            try:
                recs = await ad_spend_analyzer.run(db, UUID(merchant_id), trigger="scheduled")
                await db.commit()
                logger.info("Agent generated %d recommendations for %s", len(recs), merchant_id)
                return {"recommendations": len(recs)}
            except Exception as e:
                await db.rollback()
                logger.error("Agent failed: %s", str(e))
                raise

    return run_async(_analyze())


@celery_app.task
def run_ad_spend_analyzer_all():
    """Periodic task: run ad spend analyzer for all active merchants."""
    async def _run_all():
        from app.models.merchant import Merchant

        async with async_session_factory() as db:
            result = await db.execute(
                select(Merchant).where(Merchant.is_active == True)
            )
            merchants = result.scalars().all()

            for merchant in merchants:
                run_ad_spend_analyzer.delay(str(merchant.id))

            logger.info("Queued ad spend analysis for %d merchants", len(merchants))

    run_async(_run_all())
