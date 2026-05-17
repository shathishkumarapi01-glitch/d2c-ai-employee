"""Model registry — imports all models so SQLAlchemy sees them."""

from app.models.base import Base
from app.models.merchant import Merchant
from app.models.product import Product
from app.models.order import Order
from app.models.inventory import Inventory
from app.models.ad_campaign import AdCampaign
from app.models.source_record import SourceRecord
from app.models.agent_log import AgentLog
from app.models.chat import ChatSession, ChatMessage
from app.models.payment import Payment

__all__ = [
    "Base",
    "Merchant",
    "Product",
    "Order",
    "Inventory",
    "AdCampaign",
    "SourceRecord",
    "AgentLog",
    "ChatSession",
    "ChatMessage",
    "Payment",
]
