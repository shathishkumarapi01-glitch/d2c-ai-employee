"""
Tool registry — maps tool names to their implementations and OpenAI function schemas.
Central registry for all tools available to the LLM during chat.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.query_orders import query_orders, QUERY_ORDERS_SCHEMA
from app.tools.query_campaigns import query_campaigns, QUERY_CAMPAIGNS_SCHEMA
from app.tools.query_products import query_products, QUERY_PRODUCTS_SCHEMA
from app.tools.query_inventory import query_inventory, QUERY_INVENTORY_SCHEMA
from app.tools.query_payments import execute_query_payments, get_query_payments_schema
from app.tools.analytics import (
    analyze_channel_roas,
    analyze_refund_patterns,
    ANALYZE_CHANNEL_ROAS_SCHEMA,
    ANALYZE_REFUND_PATTERNS_SCHEMA,
)

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Manages available tools for LLM function calling.
    Each tool has a schema (for OpenAI) and an implementation (for execution).
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}
        self._implementations: dict[str, Callable[..., Awaitable[dict]]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register all built-in tools."""
        self.register("query_orders", QUERY_ORDERS_SCHEMA, query_orders)
        self.register("query_campaigns", QUERY_CAMPAIGNS_SCHEMA, query_campaigns)
        self.register("query_products", QUERY_PRODUCTS_SCHEMA, query_products)
        self.register("query_inventory", QUERY_INVENTORY_SCHEMA, query_inventory)
        self.register("query_payments", get_query_payments_schema(), execute_query_payments)
        self.register("analyze_channel_roas", ANALYZE_CHANNEL_ROAS_SCHEMA, analyze_channel_roas)
        self.register("analyze_refund_patterns", ANALYZE_REFUND_PATTERNS_SCHEMA, analyze_refund_patterns)

    def register(self, name: str, schema: dict, implementation: Callable) -> None:
        """Register a new tool with its schema and implementation."""
        self._tools[name] = {
            "type": "function",
            "function": schema,
        }
        self._implementations[name] = implementation
        logger.info("Registered tool: %s", name)

    def get_schemas(self) -> list[dict]:
        """Get all tool schemas in OpenAI function calling format."""
        return list(self._tools.values())

    def get_llm_schemas(self) -> list[dict]:
        """
        Get tool schemas tailored for the LLM.
        The runtime injects merchant context, so the model should never see or fill it.
        """
        schemas = deepcopy(self.get_schemas())
        for tool in schemas:
            fn = tool.get("function", {})
            params = fn.get("parameters", {})
            properties = params.get("properties", {})
            properties.pop("merchant_id", None)

            required = params.get("required", [])
            if required:
                params["required"] = [item for item in required if item != "merchant_id"]

            description = fn.get("description", "")
            if description:
                fn["description"] = (
                    f"{description} Merchant context is injected automatically at runtime."
                )

        return schemas

    async def execute(self, name: str, db: AsyncSession, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool by name with given arguments.
        Returns the tool result including source_refs for citation tracking.
        """
        if name not in self._implementations:
            return {"error": f"Unknown tool: {name}", "source_refs": []}

        impl = self._implementations[name]
        try:
            result = await impl(db=db, **arguments)
            logger.info("Tool %s executed successfully", name)
            return result
        except Exception as e:
            logger.error("Tool %s failed: %s", name, str(e))
            return {"error": str(e), "source_refs": []}

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())


# Singleton
tool_registry = ToolRegistry()
