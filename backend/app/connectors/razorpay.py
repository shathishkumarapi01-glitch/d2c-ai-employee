"""
Razorpay connector — fetches payments data.
Falls back to realistic mock data when keys are not configured.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.connectors.base import BaseConnector
from app.schemas.connector import ConnectorHealth, NormalizedRecord, SyncResult

logger = logging.getLogger(__name__)


class RazorpayConnector(BaseConnector):
    name = "razorpay"
    platform = "razorpay"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._mock_mode = True # Always mock for this demo
        self._last_sync: datetime | None = None

    async def fetch_data(self, merchant_id: str, params: dict[str, Any] | None = None) -> list[dict]:
        logger.info("Razorpay running in MOCK mode for merchant=%s", merchant_id)
        return self._generate_mock_data(merchant_id)

    def normalize(self, raw_data: list[dict]) -> list[NormalizedRecord]:
        records = []
        for item in raw_data:
            records.append(NormalizedRecord(
                entity_type="payment",
                source_platform="razorpay",
                source_row_id=str(item.get("id", "")),
                data={
                    "amount": float(item.get("amount", 0)) / 100, # convert paise to INR
                    "currency": item.get("currency", "INR"),
                    "status": item.get("status", "captured"),
                    "order_id": item.get("order_id", ""),
                    "method": item.get("method", ""),
                    "customer_email": item.get("customer_email", ""),
                    "payment_date": datetime.fromisoformat(item.get("created_at", datetime.now(timezone.utc).isoformat()).replace('Z', '+00:00')),
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
                connector="razorpay", merchant_id=merchant_id, status="success",
                records_fetched=len(raw_data), records_normalized=len(normalized),
                records_saved=len(normalized), duration_seconds=round(time.time() - start, 2),
            )
        except Exception as e:
            logger.error("Razorpay sync failed: %s", str(e))
            return SyncResult(
                connector="razorpay", merchant_id=merchant_id, status="error",
                errors=[str(e)], duration_seconds=round(time.time() - start, 2),
            )

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            name="razorpay", status="mock",
            mock_mode=True, last_sync=self._last_sync,
            records_synced=0,
        )

    def _generate_mock_data(self, merchant_id: str) -> list[dict]:
        return [
          {
            "id": "pay_Oa1B2c3D4e5F6g",
            "amount": 149900,
            "currency": "INR",
            "status": "captured",
            "order_id": "order_RzP1001",
            "method": "upi",
            "created_at": "2026-04-15T10:23:14Z",
            "customer_email": "rahul.sharma@gmail.com"
          },
          {
            "id": "pay_Ob2C3d4E5f6G7h",
            "amount": 89900,
            "currency": "INR",
            "status": "captured",
            "order_id": "order_RzP1002",
            "method": "card",
            "created_at": "2026-04-18T14:45:22Z",
            "customer_email": "priya.patel@hotmail.com"
          },
          {
            "id": "pay_Oc3D4e5F6g7H8i",
            "amount": 249900,
            "currency": "INR",
            "status": "refunded",
            "order_id": "order_RzP1003",
            "method": "upi",
            "created_at": "2026-04-20T09:12:05Z",
            "customer_email": "amit.singh@yahoo.in"
          },
          {
            "id": "pay_Od4E5f6G7h8I9j",
            "amount": 59900,
            "currency": "INR",
            "status": "captured",
            "order_id": "order_RzP1004",
            "method": "wallet",
            "created_at": "2026-04-22T16:30:45Z",
            "customer_email": "neha.gupta@gmail.com"
          },
          {
            "id": "pay_Oe5F6g7H8i9J0k",
            "amount": 129900,
            "currency": "INR",
            "status": "failed",
            "order_id": "order_RzP1005",
            "method": "card",
            "created_at": "2026-04-25T11:05:10Z",
            "customer_email": "vikram.reddy@outlook.com"
          },
          {
            "id": "pay_Of6G7h8I9j0K1l",
            "amount": 199900,
            "currency": "INR",
            "status": "captured",
            "order_id": "order_RzP1006",
            "method": "upi",
            "created_at": "2026-04-28T20:15:33Z",
            "customer_email": "anjali.desai@gmail.com"
          },
          {
            "id": "pay_Og7H8i9J0k1L2m",
            "amount": 149900,
            "currency": "INR",
            "status": "captured",
            "order_id": "order_RzP1007",
            "method": "upi",
            "created_at": "2026-05-01T13:40:19Z",
            "customer_email": "rohit.kumar@gmail.com"
          },
          {
            "id": "pay_Oh8I9j0K1l2M3n",
            "amount": 89900,
            "currency": "INR",
            "status": "refunded",
            "order_id": "order_RzP1008",
            "method": "wallet",
            "created_at": "2026-05-03T18:55:41Z",
            "customer_email": "sneha.iyer@gmail.com"
          },
          {
            "id": "pay_Oi9J0k1L2m3N4o",
            "amount": 219900,
            "currency": "INR",
            "status": "captured",
            "order_id": "order_RzP1009",
            "method": "card",
            "created_at": "2026-05-05T08:20:12Z",
            "customer_email": "karan.mehta@yahoo.com"
          },
          {
            "id": "pay_Oj0K1l2M3n4O5p",
            "amount": 49900,
            "currency": "INR",
            "status": "captured",
            "order_id": "order_RzP1010",
            "method": "upi",
            "created_at": "2026-05-08T15:10:05Z",
            "customer_email": "pooja.nair@gmail.com"
          }
        ]
