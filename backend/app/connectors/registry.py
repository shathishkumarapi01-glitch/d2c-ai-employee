"""
Connector registry — factory pattern for discovering and instantiating connectors.
"""

from __future__ import annotations

from typing import Type

from app.config import settings
from app.connectors.base import BaseConnector
from app.connectors.shopify import ShopifyConnector
from app.connectors.meta_ads import MetaAdsConnector
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.razorpay import RazorpayConnector

# Registry mapping connector names to their classes
_CONNECTOR_REGISTRY: dict[str, Type[BaseConnector]] = {
    "shopify": ShopifyConnector,
    "meta_ads": MetaAdsConnector,
    "google_sheets": GoogleSheetsConnector,
    "razorpay": RazorpayConnector,
}

# Cache for instantiated connectors (singletons per type)
_connector_instances: dict[str, BaseConnector] = {}


def get_connector(name: str) -> BaseConnector:
    """
    Get or create a connector instance by name.
    Automatically sets mock mode based on available API keys.
    """
    if name not in _CONNECTOR_REGISTRY:
        raise ValueError(f"Unknown connector: {name}. Available: {list(_CONNECTOR_REGISTRY.keys())}")

    if name not in _connector_instances:
        connector_cls = _CONNECTOR_REGISTRY[name]
        instance = connector_cls()
        _connector_instances[name] = instance

    return _connector_instances[name]


def get_all_connectors() -> list[BaseConnector]:
    """Get instances of all registered connectors."""
    return [get_connector(name) for name in _CONNECTOR_REGISTRY]


def list_connector_names() -> list[str]:
    """List all registered connector names."""
    return list(_CONNECTOR_REGISTRY.keys())


def register_connector(name: str, connector_cls: Type[BaseConnector]) -> None:
    """Register a new connector type at runtime (for plugins)."""
    _CONNECTOR_REGISTRY[name] = connector_cls
    # Clear cached instance if replacing
    _connector_instances.pop(name, None)
