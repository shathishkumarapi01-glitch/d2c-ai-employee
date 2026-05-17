"""
Shopify connector — fetches orders, products, and inventory from the Shopify REST API.
Falls back to realistic mock data when SHOPIFY_API_KEY is not configured.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings
from app.connectors.base import BaseConnector
from app.schemas.connector import ConnectorHealth, NormalizedRecord, SyncResult

logger = logging.getLogger(__name__)


class ShopifyConnector(BaseConnector):
    name = "shopify"
    platform = "shopify"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._mock_mode = settings.shopify_mock
        self._base_url = f"https://{settings.shopify_store_domain}/admin/api/2024-01"
        self._headers = {
            "X-Shopify-Access-Token": settings.shopify_api_key,
            "Content-Type": "application/json",
        }
        self._last_sync: datetime | None = None

    async def fetch_data(self, merchant_id: str, params: dict[str, Any] | None = None) -> list[dict]:
        if self._mock_mode:
            logger.info("Shopify running in MOCK mode for merchant=%s", merchant_id)
            return self._generate_mock_data(merchant_id)

        entity_type = (params or {}).get("entity_type", "orders")
        all_records = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            endpoint = f"{self._base_url}/{entity_type}.json"
            response = await client.get(endpoint, headers=self._headers, params={"limit": 250})
            response.raise_for_status()
            data = response.json()
            all_records.extend(data.get(entity_type, []))

        return all_records

    def normalize(self, raw_data: list[dict]) -> list[NormalizedRecord]:
        records = []
        for item in raw_data:
            entity_type = item.get("_entity_type", "order")

            if entity_type == "product":
                records.append(NormalizedRecord(
                    entity_type="product",
                    source_platform="shopify",
                    source_row_id=str(item.get("id", "")),
                    data={
                        "title": item.get("title", ""),
                        "sku": item.get("variants", [{}])[0].get("sku", "") if item.get("variants") else "",
                        "price": float(item.get("variants", [{}])[0].get("price", 0)) if item.get("variants") else 0,
                        "currency": "INR",
                        "status": item.get("status", "active"),
                        "category": item.get("product_type", ""),
                        "image_url": item.get("image", {}).get("src", "") if item.get("image") else "",
                    },
                    raw_payload=item,
                ))
            elif entity_type == "order":
                records.append(NormalizedRecord(
                    entity_type="order",
                    source_platform="shopify",
                    source_row_id=str(item.get("id", "")),
                    data={
                        "order_number": str(item.get("order_number", item.get("name", ""))),
                        "total_amount": float(item.get("total_price", 0)),
                        "currency": item.get("currency", "INR"),
                        "financial_status": item.get("financial_status", "pending"),
                        "fulfillment_status": item.get("fulfillment_status", "unfulfilled") or "unfulfilled",
                        "customer_email": item.get("email", ""),
                        "order_date": datetime.fromisoformat(item.get("created_at", datetime.now(timezone.utc).isoformat()).replace('Z', '+00:00')),
                        "line_items": item.get("line_items", []),
                        "shipping_address": item.get("shipping_address"),
                        "tags": item.get("tags", ""),
                    },
                    raw_payload=item,
                ))
            elif entity_type == "inventory":
                records.append(NormalizedRecord(
                    entity_type="inventory",
                    source_platform="shopify",
                    source_row_id=str(item.get("inventory_item_id", item.get("id", ""))),
                    data={
                        "sku": item.get("sku", ""),
                        "product_title": item.get("product_title", ""),
                        "quantity": int(item.get("available", item.get("quantity", 0))),
                        "location": item.get("location", "default"),
                    },
                    raw_payload=item,
                ))

        return records

    async def sync(self, merchant_id: str, params: dict[str, Any] | None = None) -> SyncResult:
        start = time.time()
        errors = []

        try:
            raw_data = await self.fetch_data(merchant_id, params)
            normalized = self.normalize(raw_data)
            self._last_sync = datetime.now(timezone.utc)

            return SyncResult(
                connector="shopify",
                merchant_id=merchant_id,
                status="success",
                records_fetched=len(raw_data),
                records_normalized=len(normalized),
                records_saved=len(normalized),
                errors=errors,
                duration_seconds=round(time.time() - start, 2),
            )
        except Exception as e:
            logger.error("Shopify sync failed: %s", str(e))
            return SyncResult(
                connector="shopify",
                merchant_id=merchant_id,
                status="error",
                errors=[str(e)],
                duration_seconds=round(time.time() - start, 2),
            )

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            name="shopify",
            status="mock" if self._mock_mode else "healthy",
            mock_mode=self._mock_mode,
            last_sync=self._last_sync,
            records_synced=0,
        )

    def _generate_mock_data(self, merchant_id: str) -> list[dict]:
        """Generate realistic Shopify-style mock data for ThreadCraft."""
        products = [
            {"id": "shp_prod_1", "_entity_type": "product", "title": "Classic Black Hoodie", "product_type": "Apparel", "status": "active", "variants": [{"sku": "CBH-01", "price": "1499.00", "inventory_quantity": 40}], "image": {"src": ""}},
            {"id": "shp_prod_2", "_entity_type": "product", "title": "Oversized Graphic T-Shirt", "product_type": "Apparel", "status": "active", "variants": [{"sku": "OGT-02", "price": "899.00", "inventory_quantity": 25}], "image": {"src": ""}},
            {"id": "shp_prod_3", "_entity_type": "product", "title": "Premium Zip-Up Hoodie", "product_type": "Apparel", "status": "active", "variants": [{"sku": "PZH-03", "price": "1999.00", "inventory_quantity": 10}], "image": {"src": ""}},
            {"id": "shp_prod_4", "_entity_type": "product", "title": "Basic White Crewneck", "product_type": "Apparel", "status": "active", "variants": [{"sku": "BWC-04", "price": "699.00", "inventory_quantity": 80}], "image": {"src": ""}},
            {"id": "shp_prod_5", "_entity_type": "product", "title": "Summer V-Neck Tee", "product_type": "Apparel", "status": "active", "variants": [{"sku": "SVT-05", "price": "599.00", "inventory_quantity": 100}], "image": {"src": ""}},
            {"id": "shp_prod_6", "_entity_type": "product", "title": "Streetwear Cargo Joggers", "product_type": "Apparel", "status": "active", "variants": [{"sku": "SCJ-06", "price": "1299.00", "inventory_quantity": 35}], "image": {"src": ""}},
            {"id": "shp_prod_7", "_entity_type": "product", "title": "Essential Sweatpants", "product_type": "Apparel", "status": "active", "variants": [{"sku": "ES-07", "price": "999.00", "inventory_quantity": 60}], "image": {"src": ""}},
            {"id": "shp_prod_8", "_entity_type": "product", "title": "Heavyweight Hoodie", "product_type": "Apparel", "status": "active", "variants": [{"sku": "HH-08", "price": "1000.00", "inventory_quantity": 45}], "image": {"src": ""}},
            {"id": "shp_prod_9", "_entity_type": "product", "title": "Denim Jacket", "product_type": "Apparel", "status": "active", "variants": [{"sku": "DJ-09", "price": "1500.00", "inventory_quantity": 15}], "image": {"src": ""}},
            {"id": "shp_prod_10", "_entity_type": "product", "title": "Gym Stringer Vest", "product_type": "Apparel", "status": "active", "variants": [{"sku": "GSV-10", "price": "499.00", "inventory_quantity": 120}], "image": {"src": ""}}
        ]

        inventory = [
            {"id": f"shp_inv_{p['id']}", "_entity_type": "inventory", "inventory_item_id": f"shp_inv_{p['id']}", "sku": p["variants"][0]["sku"], "product_title": p["title"], "available": p["variants"][0]["inventory_quantity"], "location": "Primary Warehouse"}
            for p in products
        ]

        orders = [
          {
            "id": "gid://shopify/Order/82098231001", "_entity_type": "order", "name": "#1001", "order_number": "1001", "total_price": "1499.00", "currency": "INR", "financial_status": "paid", "fulfillment_status": "fulfilled", "created_at": "2026-04-15T10:23:20Z",
            "line_items": [{ "title": "Classic Black Hoodie", "quantity": 1, "price": "1499.00" }],
            "email": "rahul.sharma@gmail.com", "shipping_address": {"city": "Delhi", "country": "India"}
          },
          {
            "id": "gid://shopify/Order/82098231002", "_entity_type": "order", "name": "#1002", "order_number": "1002", "total_price": "899.00", "currency": "INR", "financial_status": "paid", "fulfillment_status": "fulfilled", "created_at": "2026-04-18T14:45:30Z",
            "line_items": [{ "title": "Oversized Graphic T-Shirt", "quantity": 1, "price": "899.00" }],
            "email": "priya.patel@hotmail.com", "shipping_address": {"city": "Mumbai", "country": "India"}
          },
          {
            "id": "gid://shopify/Order/82098231003", "_entity_type": "order", "name": "#1003", "order_number": "1003", "total_price": "2499.00", "currency": "INR", "financial_status": "refunded", "fulfillment_status": "unfulfilled", "created_at": "2026-04-20T09:12:15Z",
            "line_items": [{ "title": "Premium Zip-Up Hoodie", "quantity": 1, "price": "1999.00" }, { "title": "Basic White Crewneck", "quantity": 1, "price": "500.00" }],
            "email": "amit.singh@yahoo.in", "shipping_address": {"city": "Bangalore", "country": "India"}
          },
          {
            "id": "gid://shopify/Order/82098231004", "_entity_type": "order", "name": "#1004", "order_number": "1004", "total_price": "599.00", "currency": "INR", "financial_status": "paid", "fulfillment_status": "fulfilled", "created_at": "2026-04-22T16:30:50Z",
            "line_items": [{ "title": "Summer V-Neck Tee", "quantity": 1, "price": "599.00" }],
            "email": "neha.gupta@gmail.com", "shipping_address": {"city": "Chennai", "country": "India"}
          },
          {
            "id": "gid://shopify/Order/82098231005", "_entity_type": "order", "name": "#1005", "order_number": "1005", "total_price": "1299.00", "currency": "INR", "financial_status": "voided", "fulfillment_status": "unfulfilled", "created_at": "2026-04-25T11:05:15Z",
            "line_items": [{ "title": "Streetwear Cargo Joggers", "quantity": 1, "price": "1299.00" }],
            "email": "vikram.reddy@outlook.com", "shipping_address": {"city": "Pune", "country": "India"}
          },
          {
            "id": "gid://shopify/Order/82098231006", "_entity_type": "order", "name": "#1006", "order_number": "1006", "total_price": "1999.00", "currency": "INR", "financial_status": "paid", "fulfillment_status": "partial", "created_at": "2026-04-28T20:15:40Z",
            "line_items": [{ "title": "Essential Sweatpants", "quantity": 1, "price": "999.00" }, { "title": "Heavyweight Hoodie", "quantity": 1, "price": "1000.00" }],
            "email": "anjali.desai@gmail.com", "shipping_address": {"city": "Delhi", "country": "India"}
          },
          {
            "id": "gid://shopify/Order/82098231007", "_entity_type": "order", "name": "#1007", "order_number": "1007", "total_price": "1499.00", "currency": "INR", "financial_status": "paid", "fulfillment_status": "fulfilled", "created_at": "2026-05-01T13:40:25Z",
            "line_items": [{ "title": "Classic Black Hoodie", "quantity": 1, "price": "1499.00" }],
            "email": "rohit.kumar@gmail.com", "shipping_address": {"city": "Mumbai", "country": "India"}
          },
          {
            "id": "gid://shopify/Order/82098231008", "_entity_type": "order", "name": "#1008", "order_number": "1008", "total_price": "899.00", "currency": "INR", "financial_status": "refunded", "fulfillment_status": "restocked", "created_at": "2026-05-03T18:55:50Z",
            "line_items": [{ "title": "Oversized Graphic T-Shirt", "quantity": 1, "price": "899.00" }],
            "email": "sneha.iyer@gmail.com", "shipping_address": {"city": "Bangalore", "country": "India"}
          },
          {
            "id": "gid://shopify/Order/82098231009", "_entity_type": "order", "name": "#1009", "order_number": "1009", "total_price": "2199.00", "currency": "INR", "financial_status": "paid", "fulfillment_status": "partial", "created_at": "2026-05-05T08:20:20Z",
            "line_items": [{ "title": "Denim Jacket", "quantity": 1, "price": "1500.00" }, { "title": "Basic White Crewneck", "quantity": 1, "price": "699.00" }],
            "email": "karan.mehta@yahoo.com", "shipping_address": {"city": "Chennai", "country": "India"}
          },
          {
            "id": "gid://shopify/Order/82098231010", "_entity_type": "order", "name": "#1010", "order_number": "1010", "total_price": "499.00", "currency": "INR", "financial_status": "paid", "fulfillment_status": "fulfilled", "created_at": "2026-05-08T15:10:10Z",
            "line_items": [{ "title": "Gym Stringer Vest", "quantity": 1, "price": "499.00" }],
            "email": "pooja.nair@gmail.com", "shipping_address": {"city": "Pune", "country": "India"}
          }
        ]

        return products + inventory + orders
