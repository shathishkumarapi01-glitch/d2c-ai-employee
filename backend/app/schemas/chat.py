"""Pydantic schemas for the chat system."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message from the user."""
    message: str = Field(..., min_length=1, max_length=4096)
    merchant_id: str
    session_id: str | None = None


class ChatSessionRequest(BaseModel):
    """Request to create a fresh merchant-scoped session."""
    merchant_id: str


class Citation(BaseModel):
    """A single source reference backing a numerical claim."""
    source_platform: str
    entity_type: str
    source_row_id: str
    field: str | None = None
    value: Any = None

    @property
    def ref_string(self) -> str:
        return f"{self.source_platform}.{self.entity_type}.{self.source_row_id}"


class ChatResponse(BaseModel):
    """Response from the AI chat system."""
    session_id: str
    message: str
    citations: list[Citation] = Field(default_factory=list)
    tool_calls_made: list[dict] | None = None
    has_uncited_numbers: bool = False
    suggestions: list[str] = Field(default_factory=list)


class ChatHistoryMessage(BaseModel):
    """A single message in chat history."""
    id: str
    role: str
    content: str
    citations: list[Citation] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Full chat session history."""
    session_id: str
    merchant_id: str
    messages: list[dict]


class ChatSessionSummary(BaseModel):
    """Lightweight chat session metadata for restoration."""
    session_id: str
    merchant_id: str
    title: str | None = None
    updated_at: datetime
    message_count: int = 0
