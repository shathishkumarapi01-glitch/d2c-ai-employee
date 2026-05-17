"""
Refund Watcher Agent — detects anomalous refund behavior and writes explicit run logs.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.models.agent_log import AgentLog
from app.tools.analytics import analyze_refund_patterns

logger = logging.getLogger(__name__)

RUN_LOG_PATH = Path("data/agent_runs.jsonl")


class AgentRun(BaseModel):
    agent_id: str
    triggered_at: datetime
    trigger: str
    data_query: str
    data_summary: str
    reasoning: str
    proposed_action: str
    estimated_savings_inr: float
    confidence: float
    would_execute: bool = False
    citations: list[str] = Field(default_factory=list)


class RefundWatcher(BaseAgent):
    """Detect refund anomalies from payment data and recommend merchant action."""

    name = "refund_watcher"
    description = "Monitors refund patterns and flags anomalous refund spikes"

    async def analyze(self, db: AsyncSession, merchant_id: str) -> list[dict[str, Any]]:
        analysis = await analyze_refund_patterns(db, str(merchant_id), days=30)
        return [analysis.get("data", {})]

    async def reason(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not findings:
            return []

        finding = findings[0]
        refund_rate = float(finding.get("refund_rate", 0.0))
        mean = float(finding.get("mean", 0.0))
        std = float(finding.get("std", 0.0))
        anomaly = bool(finding.get("anomaly", False))
        affected_revenue = float(finding.get("affected_revenue", 0.0))
        citations = list(finding.get("source_refs", []))

        reasoning = (
            f"Refund rate is {refund_rate * 100:.2f}% versus a 7-day baseline mean of "
            f"{mean * 100:.2f}% with standard deviation {std * 100:.2f}%."
        )

        if anomaly:
            reasoning += (
                f" This exceeds the mean + 2σ threshold, so the spike is anomalous. "
                f"Affected revenue is ₹{affected_revenue:,.2f}."
            )
            proposed_action = (
                "Audit the most recent refunded Razorpay orders, identify the dominant refund cause, "
                "and pause any campaign or fulfillment flow linked to the spike until the issue is contained."
            )
            confidence = 0.9
            estimated_savings = affected_revenue
        else:
            reasoning += " This is within the expected operating range."
            proposed_action = (
                "Continue monitoring refund volume and review customer support notes before taking operational action."
            )
            confidence = 0.68
            estimated_savings = 0.0

        return [{
            "reasoning": reasoning,
            "proposed_action": proposed_action,
            "estimated_savings_inr": round(estimated_savings, 2),
            "confidence": confidence,
            "would_execute": False,
            "citations": citations,
            "anomaly": anomaly,
            "data_summary": str(finding.get("summary", "")),
        }]

    async def run(
        self, db: AsyncSession, merchant_id: str, trigger: str = "scheduled"
    ) -> list[dict[str, Any]]:
        findings = await self.analyze(db, merchant_id)
        recommendations = await self.reason(findings)
        if not recommendations:
            return []

        finding = findings[0]
        recommendation = recommendations[0]
        run = AgentRun(
            agent_id=self.name,
            triggered_at=datetime.now(timezone.utc),
            trigger=trigger,
            data_query=(
                "analyze_refund_patterns(days=30, merchant_id=<merchant>) "
                "over Razorpay payment rows"
            ),
            data_summary=recommendation["data_summary"],
            reasoning=recommendation["reasoning"],
            proposed_action=recommendation["proposed_action"],
            estimated_savings_inr=recommendation["estimated_savings_inr"],
            confidence=recommendation["confidence"],
            would_execute=False,
            citations=recommendation["citations"],
        )

        await self._append_run_log(run)

        if recommendation.get("anomaly"):
            agent_log = AgentLog(
                merchant_id=merchant_id,
                agent_type=self.name,
                trigger=trigger,
                reasoning=run.reasoning,
                recommendation=run.proposed_action,
                estimated_savings=run.estimated_savings_inr,
                confidence_score=run.confidence,
                citations=run.citations,
                status="pending",
                metadata_extra={
                    "run_log_path": str(RUN_LOG_PATH),
                    "refund_rate": finding.get("refund_rate", 0.0),
                    "mean": finding.get("mean", 0.0),
                    "std": finding.get("std", 0.0),
                },
            )
            db.add(agent_log)
            await db.flush()

        logger.info("Refund watcher run completed for merchant %s", merchant_id)
        return [run.model_dump(mode="json")]

    async def _append_run_log(self, run: AgentRun) -> None:
        RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RUN_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(run.model_dump(mode="json"), ensure_ascii=True) + "\n")


refund_watcher = RefundWatcher()
