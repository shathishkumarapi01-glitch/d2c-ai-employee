"""Connector API routes — manage connectors and trigger syncs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.connectors.registry import get_connector, get_all_connectors
from app.models.source_record import SourceRecord
from app.schemas.connector import ConnectorHealth, ConnectorListResponse, SyncRequest, SyncResult
from app.services.sync_service import sync_service

router = APIRouter()


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    merchant_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    connectors = get_all_connectors()
    records_by_platform: dict[str, tuple[int, object | None]] = {}

    conditions = []
    if merchant_id:
        conditions.append(SourceRecord.merchant_id == merchant_id)

    stmt = select(
        SourceRecord.source_platform,
        func.count(SourceRecord.id).label("records"),
        func.max(SourceRecord.ingested_at).label("last_sync"),
    ).group_by(SourceRecord.source_platform)
    if conditions:
        stmt = stmt.where(*conditions)

    rows = (await db.execute(stmt)).all()
    records_by_platform = {
        row.source_platform: (int(row.records or 0), row.last_sync) for row in rows
    }

    connector_health = []
    for connector in connectors:
        health = connector.health_check()
        records, last_sync = records_by_platform.get(connector.platform, (0, None))
        health.records_synced = records
        health.last_sync = last_sync or health.last_sync
        connector_health.append(health)

    return ConnectorListResponse(connectors=connector_health)


@router.get("/{name}/status", response_model=ConnectorHealth)
async def get_connector_status(name: str):
    try:
        connector = get_connector(name)
        return connector.health_check()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{name}/sync", response_model=SyncResult)
async def sync_connector(name: str, request: SyncRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await sync_service.sync_connector(db, name, request.merchant_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/sync-all", response_model=list[SyncResult])
async def sync_all_connectors(request: SyncRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await sync_service.sync_all(db, request.merchant_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
