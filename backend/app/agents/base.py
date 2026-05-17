"""
Abstract base agent — defines the lifecycle for autonomous AI agents.
All agents follow: analyze → reason → recommend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class BaseAgent(ABC):
    """
    Base class for autonomous AI agents.
    Each agent runs periodically, analyzes data, and generates recommendations.
    Agents NEVER execute actions — they only recommend.
    """

    name: str = "base_agent"
    description: str = "Base agent"

    @abstractmethod
    async def analyze(self, db: AsyncSession, merchant_id: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def reason(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def run(self, db: AsyncSession, merchant_id: str, trigger: str = "scheduled") -> list[dict[str, Any]]:
        ...
