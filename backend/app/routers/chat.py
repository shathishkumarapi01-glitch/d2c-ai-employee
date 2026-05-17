"""Chat API routes — handles AI chat with tool use and citations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionRequest,
    ChatSessionSummary,
)
from app.services.chat_service import chat_service

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def send_message(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    try:
        return await chat_service.process_message(db, request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    merchant_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await chat_service.get_history(db, session_id, merchant_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/latest/{merchant_id}", response_model=ChatSessionSummary | None)
async def get_latest_chat_session(merchant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await chat_service.get_latest_session(db, merchant_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/active/{merchant_id}", response_model=ChatSessionSummary)
async def get_active_chat_session(merchant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await chat_service.get_active_session(db, merchant_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions", response_model=ChatSessionSummary)
async def create_chat_session(
    request: ChatSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await chat_service.create_session(db, request.merchant_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
