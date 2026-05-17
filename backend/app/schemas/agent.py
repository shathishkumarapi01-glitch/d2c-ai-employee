"""Pydantic schemas for AI agent operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    """Request to manually trigger an agent run."""
    merchant_id: str
    agent_type: str = "ad_spend_analyzer"


class AgentRecommendation(BaseModel):
    """A single agent recommendation."""
    id: str
    merchant_id: str
    agent_type: str
    trigger: str
    reasoning: str
    recommendation: str
    estimated_savings: float | None
    confidence_score: float
    citations: list[dict]
    status: str
    metadata_extra: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentRecommendationList(BaseModel):
    """List of agent recommendations."""
    recommendations: list[AgentRecommendation]
    total: int


class AgentRunResult(BaseModel):
    """Result of an agent run."""
    agent_type: str
    merchant_id: str
    recommendations_generated: int
    status: str
    duration_seconds: float
