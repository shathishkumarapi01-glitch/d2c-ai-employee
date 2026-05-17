"""
FastAPI application entry point.
Initializes the app, registers routers, and sets up lifespan events.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, init_db
from app.routers import agents, chat, connectors, dashboard, merchants

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create tables on startup, cleanup on shutdown."""
    logger.info("Starting ShipRocket AI Platform — environment=%s", settings.environment)

    await init_db()
    logger.info("Database tables created.")

    if settings.mock_mode:
        logger.warning("Running in MOCK MODE — no OpenAI key configured.")

    yield

    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="ShipRocket AI Employee Platform",
    description="Multi-tenant AI platform for D2C brands — connectors, citation-grounded chat, autonomous agents.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(connectors.router, prefix="/api/v1/connectors", tags=["Connectors"])
app.include_router(merchants.router, prefix="/api/v1/merchants", tags=["Merchants"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "environment": settings.environment,
        "mock_mode": settings.mock_mode,
    }
