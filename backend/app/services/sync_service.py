"""
Sync service — orchestrates data synchronization from connectors into the database.
Handles the full pipeline: fetch → normalize → persist with provenance tracking.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import get_connector, get_all_connectors
from app.models.ad_campaign import AdCampaign
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.product import Product
from app.models.source_record import SourceRecord
from app.models.payment import Payment
from app.schemas.connector import NormalizedRecord, SyncResult

logger = logging.getLogger(__name__)

# Maps entity types to their ORM models
ENTITY_MODEL_MAP = {
    "product": Product,
    "order": Order,
    "inventory": Inventory,
    "ad_campaign": AdCampaign,
    "payment": Payment,
}


class SyncService:
    """Orchestrates connector synchronization with full provenance tracking."""

    async def sync_connector(
        self, db: AsyncSession, connector_name: str, merchant_id: str,
        params: dict[str, Any] | None = None,
    ) -> SyncResult:
        """Sync a single connector for a merchant."""
        connector = get_connector(connector_name)

        # Fetch and normalize
        raw_data = await connector.fetch_data(merchant_id, params)
        normalized = connector.normalize(raw_data)

        # Persist
        saved = 0
        errors = []
        for record in normalized:
            try:
                await self._persist_record(db, record, merchant_id)
                saved += 1
            except Exception as e:
                errors.append(f"{record.source_row_id}: {str(e)}")
                logger.error("Failed to persist record %s: %s", record.source_row_id, str(e))

        await db.flush()

        return SyncResult(
            connector=connector_name,
            merchant_id=merchant_id,
            status="success" if not errors else "partial",
            records_fetched=len(raw_data),
            records_normalized=len(normalized),
            records_saved=saved,
            errors=errors,
        )

    async def sync_all(
        self, db: AsyncSession, merchant_id: str
    ) -> list[SyncResult]:
        """Sync all connectors for a merchant."""
        results = []
        for connector in get_all_connectors():
            try:
                result = await self.sync_connector(db, connector.name, merchant_id)
                results.append(result)
            except Exception as e:
                logger.error("Sync failed for %s: %s", connector.name, str(e))
                results.append(SyncResult(
                    connector=connector.name,
                    merchant_id=merchant_id,
                    status="error",
                    errors=[str(e)],
                ))
        return results

    async def _persist_record(
        self, db: AsyncSession, record: NormalizedRecord, merchant_id: str
    ) -> None:
        """Persist a normalized record into the appropriate table."""
        model_cls = ENTITY_MODEL_MAP.get(record.entity_type)
        if not model_cls:
            raise ValueError(f"Unknown entity type: {record.entity_type}")

        # Check for existing record (upsert by source)
        existing = await db.execute(
            select(model_cls).where(
                model_cls.merchant_id == merchant_id,
                model_cls.source_platform == record.source_platform,
                model_cls.source_row_id == record.source_row_id,
            )
        )
        entity = existing.scalar_one_or_none()

        if entity:
            # Update existing record
            for key, value in record.data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            entity.synced_at = datetime.now(timezone.utc)
            entity.raw_payload = record.raw_payload
        else:
            # Create new record
            entity = model_cls(
                merchant_id=merchant_id,
                source_platform=record.source_platform,
                source_row_id=record.source_row_id,
                raw_payload=record.raw_payload,
                synced_at=datetime.now(timezone.utc),
                **record.data,
            )
            db.add(entity)

        # Append to source_records log (always)
        source_record = SourceRecord(
            merchant_id=merchant_id,
            source_platform=record.source_platform,
            entity_type=record.entity_type,
            source_row_id=record.source_row_id,
            raw_data=record.raw_payload,
            sync_status="normalized",
        )
        db.add(source_record)


# Singleton
sync_service = SyncService()
