"""Agent API routes — view recommendations and trigger agent runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.agents.ad_spend_analyzer import ad_spend_analyzer
from app.agents.refund_watcher import refund_watcher
from app.models.agent_log import AgentLog
from app.schemas.agent import AgentRecommendation, AgentRecommendationList, AgentRunRequest, AgentRunResult

router = APIRouter()


@router.get("/recommendations", response_model=AgentRecommendationList)
async def list_recommendations(
    merchant_id: str | None = Query(None),
    status: str = Query(""),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if merchant_id:
        conditions.append(AgentLog.merchant_id == merchant_id)
    if status:
        conditions.append(AgentLog.status == status)

    stmt = select(AgentLog).order_by(AgentLog.created_at.desc()).limit(limit)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt)
    logs = result.scalars().all()

    return AgentRecommendationList(
        recommendations=[AgentRecommendation.model_validate(log) for log in logs],
        total=len(logs),
    )


@router.post("/run/{agent_type}", response_model=AgentRunResult)
async def run_agent(agent_type: str, request: AgentRunRequest, db: AsyncSession = Depends(get_db)):
    import time

    agents = {
        "ad_spend_analyzer": ad_spend_analyzer,
        "refund_watcher": refund_watcher,
    }

    if agent_type not in agents:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent: {agent_type}. Available: {list(agents.keys())}",
        )

    agent = agents[agent_type]
    start = time.time()

    try:
        recommendations = await agent.run(db, str(request.merchant_id), trigger="manual")
        return AgentRunResult(
            agent_type=agent_type,
            merchant_id=str(request.merchant_id),
            recommendations_generated=len(recommendations),
            status="success",
            duration_seconds=round(time.time() - start, 2),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent run failed: {str(e)}")


@router.patch("/recommendations/{rec_id}/status")
async def update_recommendation_status(
    rec_id: str, status: str = Query(...), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentLog).where(AgentLog.id == rec_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    valid_statuses = {"pending", "reviewed", "accepted", "dismissed"}
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {valid_statuses}")

    log.status = status
    await db.flush()
    return {"id": str(rec_id), "status": status}
