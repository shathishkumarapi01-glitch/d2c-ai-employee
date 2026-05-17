"""
Google Sheets connector — reads structured data from Google Sheets.
Falls back to mock data when credentials are not configured.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.connectors.base import BaseConnector
from app.schemas.connector import ConnectorHealth, NormalizedRecord, SyncResult

logger = logging.getLogger(__name__)


class GoogleSheetsConnector(BaseConnector):
    name = "google_sheets"
    platform = "google_sheets"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._mock_mode = settings.gsheets_mock
        self._last_sync: datetime | None = None

    async def fetch_data(self, merchant_id: str, params: dict[str, Any] | None = None) -> list[dict]:
        if self._mock_mode:
            logger.info("Google Sheets running in MOCK mode for merchant=%s", merchant_id)
            return self._generate_mock_data(merchant_id)

        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            settings.google_sheets_credentials_file,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        spreadsheet_id = settings.google_sheets_spreadsheet_id
        range_name = (params or {}).get("range", "Sheet1!A1:Z1000")

        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get("values", [])

        if not values:
            return []

        headers = values[0]
        records = []
        for i, row in enumerate(values[1:], start=2):
            record = {"_row_number": i}
            for j, header in enumerate(headers):
                record[header.strip().lower().replace(" ", "_")] = row[j] if j < len(row) else ""
            records.append(record)

        return records

    def normalize(self, raw_data: list[dict]) -> list[NormalizedRecord]:
        records = []
        for item in raw_data:
            entity_type = item.get("_entity_type", "inventory")
            row_id = str(item.get("_row_number", item.get("id", "")))

            if entity_type == "product":
                records.append(NormalizedRecord(
                    entity_type="product",
                    source_platform="google_sheets",
                    source_row_id=f"gsheet_row_{row_id}",
                    data={
                        "title": item.get("product_name", item.get("title", "")),
                        "sku": item.get("sku", ""),
                        "price": float(item.get("price", 0)),
                        "currency": "INR",
                        "status": item.get("status", "active"),
                        "category": item.get("category", ""),
                    },
                    raw_payload=item,
                ))
            elif entity_type == "inventory":
                records.append(NormalizedRecord(
                    entity_type="inventory",
                    source_platform="google_sheets",
                    source_row_id=f"gsheet_row_{row_id}",
                    data={
                        "sku": item.get("sku", ""),
                        "product_title": item.get("product_name", item.get("title", "")),
                        "quantity": int(item.get("stock", item.get("quantity", 0))),
                        "location": item.get("warehouse", item.get("location", "Sheet Import")),
                        "reorder_point": int(item.get("reorder_point", 10)),
                    },
                    raw_payload=item,
                ))
            elif entity_type == "ad_campaign":
                spend = float(item.get("spend_inr", 0))
                revenue = float(item.get("revenue_inr", 0))
                clicks = int(item.get("clicks", 0))
                cpc = round(spend / clicks, 2) if clicks > 0 else None
                roas = round(revenue / spend, 2) if spend > 0 else None
                records.append(NormalizedRecord(
                    entity_type="ad_campaign",
                    source_platform="google_sheets",
                    source_row_id=f"gsheet_row_{row_id}",
                    data={
                        "campaign_name": item.get("campaign_name", ""),
                        "campaign_id_external": f"gsheet_camp_{row_id}",
                        "status": "active",
                        "objective": item.get("channel", ""),
                        "spend": spend,
                        "impressions": clicks * 100, # Fake impressions
                        "clicks": clicks,
                        "conversions": int(item.get("orders", 0)),
                        "revenue": revenue,
                        "cpc": cpc, "ctr": 1.0, "roas": roas,
                        "currency": "INR",
                        "date_start": datetime.strptime(item["date"], "%Y-%m-%d").date() if item.get("date") else None,
                        "date_end": datetime.strptime(item["date"], "%Y-%m-%d").date() if item.get("date") else None,
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
                connector="google_sheets",
                merchant_id=merchant_id,
                status="success",
                records_fetched=len(raw_data),
                records_normalized=len(normalized),
                records_saved=len(normalized),
                duration_seconds=round(time.time() - start, 2),
            )
        except Exception as e:
            logger.error("Google Sheets sync failed: %s", str(e))
            return SyncResult(
                connector="google_sheets",
                merchant_id=merchant_id,
                status="error",
                errors=[str(e)],
                duration_seconds=round(time.time() - start, 2),
            )

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            name="google_sheets",
            status="mock" if self._mock_mode else "healthy",
            mock_mode=self._mock_mode,
            last_sync=self._last_sync,
        )

    def _generate_mock_data(self, merchant_id: str) -> list[dict]:
        """Mock data representing a Google Sheets campaign tracker."""
        items = [
          {"_row_number": 2, "_entity_type": "ad_campaign", "date": "2026-04-15", "campaign_name": "Summer_Hoodies_Retargeting", "channel": "meta", "spend_inr": "2500.00", "clicks": 450, "orders": 8, "revenue_inr": "11992.00"},
          {"_row_number": 3, "_entity_type": "ad_campaign", "date": "2026-04-18", "campaign_name": "Graphic_Tees_Lookalike", "channel": "instagram", "spend_inr": "4000.00", "clicks": 820, "orders": 12, "revenue_inr": "10788.00"},
          {"_row_number": 4, "_entity_type": "ad_campaign", "date": "2026-04-20", "campaign_name": "Cart_Abandonment_Promo", "channel": "whatsapp", "spend_inr": "300.00", "clicks": 150, "orders": 5, "revenue_inr": "6245.00"},
          {"_row_number": 5, "_entity_type": "ad_campaign", "date": "2026-04-25", "campaign_name": "Brand_Awareness_Broad", "channel": "google", "spend_inr": "8500.00", "clicks": 120, "orders": 0, "revenue_inr": "0.00"},
          {"_row_number": 6, "_entity_type": "ad_campaign", "date": "2026-04-28", "campaign_name": "Streetwear_Drop_1", "channel": "meta", "spend_inr": "5000.00", "clicks": 950, "orders": 15, "revenue_inr": "22485.00"},
          {"_row_number": 7, "_entity_type": "ad_campaign", "date": "2026-05-01", "campaign_name": "Summer_Hoodies_Retargeting", "channel": "meta", "spend_inr": "2800.00", "clicks": 510, "orders": 9, "revenue_inr": "13491.00"},
          {"_row_number": 8, "_entity_type": "ad_campaign", "date": "2026-05-05", "campaign_name": "Denim_Launch_VIP", "channel": "whatsapp", "spend_inr": "500.00", "clicks": 320, "orders": 18, "revenue_inr": "39582.00"},
          {"_row_number": 9, "_entity_type": "ad_campaign", "date": "2026-05-08", "campaign_name": "Gym_Wear_Search", "channel": "google", "spend_inr": "3500.00", "clicks": 280, "orders": 4, "revenue_inr": "1996.00"}
        ]
        return items
