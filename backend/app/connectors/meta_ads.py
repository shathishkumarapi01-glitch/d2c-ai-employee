"""
Meta Ads connector — fetches campaign performance data from the Meta Marketing API.
Falls back to realistic mock data when META_ACCESS_TOKEN is not configured.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings
from app.connectors.base import BaseConnector
from app.schemas.connector import ConnectorHealth, NormalizedRecord, SyncResult

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class MetaAdsConnector(BaseConnector):
    name = "meta_ads"
    platform = "meta_ads"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._mock_mode = settings.meta_mock
        self._access_token = settings.meta_access_token
        self._ad_account_id = settings.meta_ad_account_id
        self._last_sync: datetime | None = None

    async def fetch_data(self, merchant_id: str, params: dict[str, Any] | None = None) -> list[dict]:
        if self._mock_mode:
            logger.info("Meta Ads running in MOCK mode for merchant=%s", merchant_id)
            return self._generate_mock_data(merchant_id)

        url = f"{GRAPH_API_BASE}/act_{self._ad_account_id}/campaigns"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params={
                "access_token": self._access_token,
                "fields": "name,objective,status,insights{spend,impressions,clicks,actions}",
                "limit": 100,
            })
            response.raise_for_status()
            return response.json().get("data", [])

    def normalize(self, raw_data: list[dict]) -> list[NormalizedRecord]:
        records = []
        for item in raw_data:
            spend = float(item.get("spend", 0))
            impressions = int(item.get("impressions", 0))
            clicks = int(item.get("clicks", 0))
            conversions = int(item.get("conversions", 0))
            revenue = float(item.get("revenue", 0))

            cpc = round(spend / clicks, 2) if clicks > 0 else None
            ctr = round((clicks / impressions) * 100, 4) if impressions > 0 else None
            roas = round(revenue / spend, 2) if spend > 0 else None

            records.append(NormalizedRecord(
                entity_type="ad_campaign",
                source_platform="meta_ads",
                source_row_id=str(item.get("campaign_id", item.get("id", ""))),
                data={
                    "campaign_name": item.get("campaign_name", item.get("name", "")),
                    "campaign_id_external": str(item.get("campaign_id", "")),
                    "status": item.get("status", "active").lower(),
                    "objective": item.get("objective", ""),
                    "spend": spend,
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": conversions,
                    "revenue": revenue,
                    "cpc": cpc, "ctr": ctr, "roas": roas,
                    "currency": "INR",
                    "date_start": datetime.strptime(item["date_start"], "%Y-%m-%d").date() if item.get("date_start") else None,
                    "date_end": datetime.strptime(item["date_end"], "%Y-%m-%d").date() if item.get("date_end") else None,
                },
                raw_payload=item,
            ))
        return records

    async def sync(self, merchant_id: str, params: dict[str, Any] | None = None) -> SyncResult:
        start = time.time()
        try:
            raw_data = await self.fetch_data(merchant_id, params)
            normalized = self.normalize(raw_data)
            self._last_sync = datetime.now(timezone.utc)
            return SyncResult(
                connector="meta_ads", merchant_id=merchant_id, status="success",
                records_fetched=len(raw_data), records_normalized=len(normalized),
                records_saved=len(normalized), duration_seconds=round(time.time() - start, 2),
            )
        except Exception as e:
            logger.error("Meta Ads sync failed: %s", str(e))
            return SyncResult(
                connector="meta_ads", merchant_id=merchant_id, status="error",
                errors=[str(e)], duration_seconds=round(time.time() - start, 2),
            )

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            name="meta_ads", status="mock" if self._mock_mode else "healthy",
            mock_mode=self._mock_mode, last_sync=self._last_sync,
        )

    def _generate_mock_data(self, merchant_id: str) -> list[dict]:
        """Generate realistic Meta Ads campaign data."""
        now = datetime.now(timezone.utc)
        return [
            {"campaign_id": "meta_camp_1", "campaign_name": "Summer Collection - TOF Awareness",
             "objective": "REACH", "status": "ACTIVE", "spend": 15000,
             "impressions": 450000, "clicks": 6750, "conversions": 45, "revenue": 40500,
             "date_start": (now - timedelta(days=14)).strftime("%Y-%m-%d"),
             "date_end": now.strftime("%Y-%m-%d")},
            {"campaign_id": "meta_camp_2", "campaign_name": "Retargeting - Cart Abandoners",
             "objective": "CONVERSIONS", "status": "ACTIVE", "spend": 8000,
             "impressions": 120000, "clicks": 4800, "conversions": 96, "revenue": 86400,
             "date_start": (now - timedelta(days=14)).strftime("%Y-%m-%d"),
             "date_end": now.strftime("%Y-%m-%d")},
            {"campaign_id": "meta_camp_3", "campaign_name": "New Launch - Eco Sneakers",
             "objective": "CONVERSIONS", "status": "ACTIVE", "spend": 25000,
             "impressions": 380000, "clicks": 5700, "conversions": 28, "revenue": 18200,
             "date_start": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
             "date_end": now.strftime("%Y-%m-%d")},
            {"campaign_id": "meta_camp_4", "campaign_name": "Brand Awareness - Instagram Reels",
             "objective": "REACH", "status": "ACTIVE", "spend": 12000,
             "impressions": 890000, "clicks": 13350, "conversions": 22, "revenue": 13200,
             "date_start": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
             "date_end": now.strftime("%Y-%m-%d")},
            {"campaign_id": "meta_camp_5", "campaign_name": "Festive Sale - Diwali Collection",
             "objective": "CONVERSIONS", "status": "PAUSED", "spend": 35000,
             "impressions": 720000, "clicks": 14400, "conversions": 180, "revenue": 162000,
             "date_start": (now - timedelta(days=45)).strftime("%Y-%m-%d"),
             "date_end": (now - timedelta(days=15)).strftime("%Y-%m-%d")},
            {"campaign_id": "meta_camp_6", "campaign_name": "Lookalike - High LTV Customers",
             "objective": "CONVERSIONS", "status": "ACTIVE", "spend": 18000,
             "impressions": 250000, "clicks": 7500, "conversions": 60, "revenue": 72000,
             "date_start": (now - timedelta(days=10)).strftime("%Y-%m-%d"),
             "date_end": now.strftime("%Y-%m-%d")},
            {"campaign_id": "meta_camp_7", "campaign_name": "Video Views - Brand Story",
             "objective": "VIDEO_VIEWS", "status": "ACTIVE", "spend": 9500,
             "impressions": 650000, "clicks": 3250, "conversions": 8, "revenue": 4800,
             "date_start": (now - timedelta(days=21)).strftime("%Y-%m-%d"),
             "date_end": now.strftime("%Y-%m-%d")},
            {"campaign_id": "meta_camp_8", "campaign_name": "DPA - Product Catalog Retargeting",
             "objective": "PRODUCT_CATALOG_SALES", "status": "ACTIVE", "spend": 22000,
             "impressions": 180000, "clicks": 9000, "conversions": 135, "revenue": 148500,
             "date_start": (now - timedelta(days=14)).strftime("%Y-%m-%d"),
             "date_end": now.strftime("%Y-%m-%d")},
        ]
