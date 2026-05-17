"""
Celery application configuration.
Handles background job processing and periodic scheduling.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "shiprocket_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Rate limiting
    task_default_rate_limit="10/m",
    # Result expiration
    result_expires=3600,
)

# Periodic task schedule
celery_app.conf.beat_schedule = {
    "sync-all-connectors": {
        "task": "worker.tasks.sync_all_merchants",
        "schedule": crontab(minute=0, hour="*/4"),  # Every 4 hours
    },
    "run-ad-spend-analyzer": {
        "task": "worker.tasks.run_ad_spend_analyzer_all",
        "schedule": crontab(minute=0, hour=f"*/{settings.agent_schedule_hours}"),
    },
}
