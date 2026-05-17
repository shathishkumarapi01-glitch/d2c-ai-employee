"""
Chat service — orchestrates AI chat with tool use and citation enforcement.
Handles the full flow: user message → tool selection → execution → grounded response.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionSummary,
    Citation,
)
from app.services.citation_engine import citation_engine
from app.services.tool_registry import tool_registry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a D2C AI analyst. You answer using ONLY tool results.

RULES:
1. ALWAYS call a tool before answering. Never answer from memory.
2. NEVER fabricate numbers. Only report what tools return.
3. EVERY number MUST cite its source: [source:platform.entity.id]
4. For revenue, order, sales, GMV, or AOV questions, FIRST call query_orders. Use days_back=7 for "last week" or "this week", days_back=30 for monthly questions.
5. If query_orders returns data_coverage.used_latest_available_window=true, explain that no rows were found in the requested period, then answer using the latest available window. Do NOT say "I don't have enough data" when historical order data exists.
6. For refund questions, FIRST call analyze_refund_patterns.
7. For strategy/ad cost questions, FIRST call analyze_channel_roas. If it returns empty, call query_campaigns. Do NOT give generic advice.
8. Format currency in INR (₹).
9. Merchant ID is auto-injected.
10. If ALL tools return no data, say "I don't have enough data to answer that."
11. NEVER give generic marketing advice like "focus on high-performing channels" or "leverage organic marketing." Only use computed data from tools.

TOOLS:
- query_orders(days_back, financial_status, aggregation): Orders, revenue, GMV, AOV, sales, and recent order details.
- query_campaigns(status, aggregation): Campaign spend, revenue, and ROAS details.
- query_inventory(): Inventory, stock, low-stock SKUs.
- query_products(): Product catalog and pricing.
- query_payments(): Razorpay payments, failed payments, captured payments, and refunds.
- analyze_channel_roas(days): Marketing efficiency and budget reallocation.
- analyze_refund_patterns(days): Refund anomalies.

CITATION FORMAT: [source:shopify.order.123] [source:razorpay.payment.456]
"""

OUT_OF_SCOPE_RESPONSE = (
    "I can only help with merchant business intelligence questions about orders, revenue, "
    "refunds, campaigns, inventory, payments, and operational performance. "
    "Ask me something about your store data and I’ll ground the answer in synced records."
)

GREETING_RESPONSE = (
    "Hi, I’m your AI business copilot for this merchant. I can help analyze revenue, "
    "campaigns, inventory, refunds, payments, and operational performance using synced data."
)

DEFAULT_SUGGESTIONS = [
    "Which campaigns have low ROAS?",
    "Show refund trends",
    "Which products are low on inventory?",
]


class ChatService:
    """Orchestrates the AI chat pipeline with tool use and citation enforcement."""

    DOMAIN_KEYWORDS = {
        "order", "orders", "sales", "revenue", "aov", "gmv", "refund", "refunds",
        "campaign", "campaigns", "ads", "ad", "roas", "spend", "meta", "marketing",
        "inventory", "stock", "warehouse", "sku", "product", "products", "catalog",
        "payment", "payments", "razorpay", "conversion", "conversions", "merchant",
        "shopify", "operations", "operational", "analytics", "trend", "trends",
        "margin", "profit", "customer", "customers", "fulfillment", "cohort",
        "channel", "channels", "cost", "costs", "cac", "efficiency",
    }

    async def process_message(
        self, db: AsyncSession, request: ChatRequest
    ) -> ChatResponse:
        """
        Full chat pipeline:
        1. Get or create session
        2. Build message history
        3. Send to LLM with tool definitions
        4. Execute any tool calls
        5. Get final response with citations
        6. Enforce citation grounding
        7. Persist messages
        """
        # Step 1: Get or create session
        session_id = request.session_id or f"chat-session-{secrets.token_hex(8)}"
        session = await self._get_or_create_session(db, session_id, request.merchant_id)

        if self._is_greeting(request.message):
            await self._save_message(db, session.id, "user", request.message)
            await self._save_message(db, session.id, "assistant", GREETING_RESPONSE)
            await db.flush()
            return ChatResponse(
                session_id=session.id,
                message=GREETING_RESPONSE,
                citations=[],
                tool_calls_made=[],
                has_uncited_numbers=False,
                suggestions=DEFAULT_SUGGESTIONS,
            )

        if not await self._is_in_domain(db, session.id, request.message):
            await self._save_message(db, session.id, "user", request.message)
            await self._save_message(db, session.id, "assistant", OUT_OF_SCOPE_RESPONSE)
            return ChatResponse(
                session_id=session.id,
                message=OUT_OF_SCOPE_RESPONSE,
                citations=[],
                tool_calls_made=[],
                has_uncited_numbers=False,
                suggestions=DEFAULT_SUGGESTIONS,
            )

        # Step 2: Build conversation history
        messages = await self._build_messages(db, session.id, request.message)

        # Step 3-5: LLM interaction with tool use
        if settings.mock_mode:
            response_text, citations, tool_calls_made = await self._mock_response(
                db, request.message, str(request.merchant_id)
            )
        else:
            response_text, citations, tool_calls_made = await self._openai_chat(
                db, messages, str(request.merchant_id)
            )

        fallback = await self._business_fallback_if_needed(
            db,
            request.message,
            str(request.merchant_id),
            response_text,
            tool_calls_made,
            citations,
        )
        if fallback:
            response_text, citations, fallback_tool_calls = fallback
            tool_calls_made = fallback_tool_calls

        # Step 6: Citation enforcement
        response_text, has_uncited = citation_engine.enforce_citations(
            response_text, citations
        )
        citations = citation_engine.filter_citations_for_response(response_text, citations)

        # Step 7: Persist messages
        await self._save_message(db, session.id, "user", request.message)
        await self._save_message(
            db, session.id, "assistant", response_text,
            citations=[c.model_dump() for c in citations],
            tool_calls=tool_calls_made,
        )
        await db.flush()

        # Step 8: Generate contextual follow-up suggestions
        suggestions = self._generate_followups(
            request.message,
            response_text,
            tool_calls_made,
        )

        return ChatResponse(
            session_id=session.id,
            message=response_text,
            citations=citations,
            tool_calls_made=tool_calls_made,
            has_uncited_numbers=has_uncited,
            suggestions=suggestions,
        )

    async def _openai_chat(
        self, db: AsyncSession, messages: list[dict], merchant_id: str
    ) -> tuple[str, list[Citation], list[dict]]:
        """Execute OpenAI chat completion with function calling."""
        import openai

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        tools = tool_registry.get_llm_schemas()
        all_tool_results: list[dict] = []
        tool_calls_made: list[dict] = []

        # First call — let LLM decide what tools to use
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0.1,
        )

        message = response.choices[0].message

        # Handle tool calls (may be multiple rounds)
        max_rounds = 3
        round_count = 0
        while message.tool_calls and round_count < max_rounds:
            round_count += 1
            messages.append(message.model_dump())

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments or "{}")

                # Force inject the correct merchant_id
                fn_args["merchant_id"] = merchant_id

                logger.info("Executing tool: %s with args: %s", fn_name, fn_args)
                result = await tool_registry.execute(fn_name, db, fn_args)
                all_tool_results.append(result)
                tool_calls_made.append({"tool": fn_name, "args": fn_args})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result.get("data", {}), default=str),
                })

            # Add citation context from tool results
            citations = citation_engine.extract_source_refs(all_tool_results)
            citation_context = citation_engine.build_citation_context(citations)
            if citation_context:
                messages.append({"role": "system", "content": citation_context})

            # Next round
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                temperature=0.1,
            )
            message = response.choices[0].message

        # If the loop ended with tool calls still pending (max_rounds hit),
        # force one final call WITHOUT tools so the LLM produces text.
        if not message.content and all_tool_results:
            messages.append(message.model_dump())
            # Execute any remaining tool calls from the last round
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments or "{}")
                    fn_args["merchant_id"] = merchant_id
                    result = await tool_registry.execute(fn_name, db, fn_args)
                    all_tool_results.append(result)
                    tool_calls_made.append({"tool": fn_name, "args": fn_args})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result.get("data", {}), default=str),
                    })

            # Final call with NO tools — forces a text answer
            final = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                temperature=0.2,
            )
            message = final.choices[0].message

        response_text = message.content or "I couldn't generate a response."
        citations = citation_engine.extract_source_refs(all_tool_results)

        return response_text, citations, tool_calls_made

    async def _mock_response(
        self, db: AsyncSession, user_message: str, merchant_id: str
    ) -> tuple[str, list[Citation], list[dict]]:
        """Generate a mock response when OpenAI is not configured."""
        msg_lower = user_message.lower()
        tool_results: list[dict] = []
        tool_calls_made: list[dict] = []

        # Detect intent and run appropriate tool
        if any(w in msg_lower for w in ["refund spike", "refund pattern", "refund anomaly", "refund risk"]):
            result = await tool_registry.execute(
                "analyze_refund_patterns", db, {"merchant_id": merchant_id, "days": 30}
            )
            tool_results.append(result)
            tool_calls_made.append({
                "tool": "analyze_refund_patterns",
                "args": {"merchant_id": merchant_id, "days": 30},
            })

            data = result.get("data", {})
            citations = citation_engine.extract_source_refs(tool_results)
            refs = " ".join(f"[source:{ref}]" for ref in data.get("source_refs", [])[:3])
            response = (
                f"{data.get('summary', 'Refund analysis is available.')}\n\n"
                f"- **Current Refund Rate:** {data.get('refund_rate', 0) * 100:.2f}% {refs}\n"
                f"- **7-Day Mean:** {data.get('mean', 0) * 100:.2f}% {refs}\n"
                f"- **7-Day Std Dev:** {data.get('std', 0) * 100:.2f}% {refs}\n"
                f"- **Affected Revenue:** ₹{data.get('affected_revenue', 0):,.2f} {refs}\n"
                f"- **Anomaly Flag:** {'Yes' if data.get('anomaly') else 'No'} {refs}\n"
            )
            return response, citations, tool_calls_made

        if any(w in msg_lower for w in ["revenue", "order", "sales", "sell", "refund"]):
            result = await tool_registry.execute(
                "query_orders", db, {"merchant_id": merchant_id, "days_back": 30}
            )
            tool_results.append(result)
            tool_calls_made.append({"tool": "query_orders", "args": {"merchant_id": merchant_id, "days_back": 30}})

            summary = result.get("data", {}).get("summary", {})
            orders = result.get("data", {}).get("orders", [])
            citations = citation_engine.extract_source_refs(tool_results)
            cited_orders = orders[: min(3, len(orders))]
            ref_strs = " ".join(
                f"[source:{o['source_platform']}.order.{o['source_row_id']}]"
                for o in cited_orders
            )
            refunded_orders = [o for o in orders if o.get("financial_status") == "refunded"]
            response = (
                f"Here’s your order summary for the last 30 days:\n\n"
                f"- **Total Orders:** {summary.get('total_orders', 0)} {ref_strs}\n"
                f"- **Total Revenue:** ₹{summary.get('total_revenue', 0):,.2f} {ref_strs}\n"
                f"- **Average Order Value:** ₹{summary.get('avg_order_value', 0):,.2f} {ref_strs}\n"
            )

            if refunded_orders:
                response += (
                    f"- **Refunded Orders:** {len(refunded_orders)} "
                    + " ".join(
                        f"[source:{o['source_platform']}.order.{o['source_row_id']}]"
                        for o in refunded_orders[:3]
                    )
                    + "\n\n"
                )
            else:
                response += "\n"

            if orders:
                response += "**Recent Orders:**\n"
                for o in orders[:3]:
                    response += (
                        f"- #{o['order_number']}: ₹{o['total_amount']:,.2f} "
                        f"({o['financial_status']}) "
                        f"[source:{o['source_platform']}.order.{o['source_row_id']}]\n"
                    )

            return response, citations, tool_calls_made

        elif any(w in msg_lower for w in [
            "channel roas", "channel", "channels", "roas",
            "reduce", "cut", "lower", "optimiz", "efficien",
            "marketing cost", "ad spend", "budget",
        ]) or (
            any(w in msg_lower for w in ["cost", "costs", "spend", "budget", "reduce", "marketing"])
            and any(w in msg_lower for w in ["how", "can", "should", "way", "help", "reduce", "cut", "lower"])
        ):
            result = await tool_registry.execute(
                "analyze_channel_roas", db, {"merchant_id": merchant_id, "days": 30}
            )
            tool_results.append(result)
            tool_calls_made.append({
                "tool": "analyze_channel_roas",
                "args": {"merchant_id": merchant_id, "days": 30},
            })

            channels = result.get("data", {}).get("channels", [])
            summary = result.get("data", {}).get("summary", "")
            citations = citation_engine.extract_source_refs(tool_results)

            response = f"{summary}\n\n"
            if channels:
                response += "**Channel ROAS:**\n"
                for row in channels[:4]:
                    refs = " ".join(f"[source:{ref}]" for ref in row.get("source_refs", [])[:2])
                    response += (
                        f"- **{row['channel']}**: Spend ₹{row['spend']:,.2f}, "
                        f"Revenue ₹{row['revenue']:,.2f}, ROAS {row['roas']}x {refs}\n"
                    )

                weakest = sorted(channels, key=lambda item: item["roas"])[0]
                response += (
                    f"\nTo reduce Meta ad costs, start by cutting or tightening budget on lower-efficiency "
                    f"channels like **{weakest['channel']}** if that matches your active mix."
                )

            return response, citations, tool_calls_made

        elif any(w in msg_lower for w in ["campaign", "ad", "ads", "roas", "spend", "meta"]):
            result = await tool_registry.execute("query_campaigns", db, {"merchant_id": merchant_id})
            tool_results.append(result)
            tool_calls_made.append({"tool": "query_campaigns", "args": {"merchant_id": merchant_id}})

            summary = result.get("data", {}).get("summary", {})
            campaigns = result.get("data", {}).get("campaigns", [])
            citations = citation_engine.extract_source_refs(tool_results)
            focus_campaigns = campaigns[:3]
            ref_strs = " ".join(
                f"[source:{c['source_platform']}.ad_campaign.{c['source_row_id']}]"
                for c in focus_campaigns
            )

            response = (
                f"Here’s your campaign performance snapshot:\n\n"
                f"- **Total Campaigns:** {summary.get('total_campaigns', 0)} {ref_strs}\n"
                f"- **Total Spend:** ₹{summary.get('total_spend', 0):,.2f} {ref_strs}\n"
                f"- **Total Revenue:** ₹{summary.get('total_revenue', 0):,.2f} {ref_strs}\n"
                f"- **Overall ROAS:** {summary.get('overall_roas', 0)}x {ref_strs}\n\n"
            )

            if focus_campaigns:
                response += "**Campaign Breakdown:**\n"
                for c in focus_campaigns:
                    response += (
                        f"- **{c['campaign_name']}**: Spend ₹{c['spend']:,.2f}, "
                        f"Revenue ₹{c['revenue']:,.2f}, ROAS {c['roas']}x "
                        f"[source:{c['source_platform']}.ad_campaign.{c['source_row_id']}]\n"
                    )

            return response, citations, tool_calls_made

        elif any(w in msg_lower for w in ["inventory", "stock", "warehouse", "low"]):
            result = await tool_registry.execute("query_inventory", db, {"merchant_id": merchant_id})
            tool_results.append(result)
            tool_calls_made.append({"tool": "query_inventory", "args": {"merchant_id": merchant_id}})

            summary = result.get("data", {}).get("summary", {})
            items = result.get("data", {}).get("inventory", [])
            citations = citation_engine.extract_source_refs(tool_results)
            low_items = [i for i in items if i.get("is_low_stock")]
            ref_strs = " ".join(
                f"[source:{i['source_platform']}.inventory.{i['source_row_id']}]"
                for i in low_items[:3]
            )

            response = (
                f"Inventory overview:\n\n"
                f"- **Total SKUs:** {summary.get('total_items', 0)} {ref_strs}\n"
                f"- **Total Units:** {summary.get('total_quantity', 0)} {ref_strs}\n"
                f"- **Low Stock Alerts:** {summary.get('low_stock_count', 0)} {ref_strs}\n\n"
            )

            if low_items:
                response += "**Low Stock Items:**\n"
                for i in low_items[:3]:
                    response += (
                        f"- **{i['product_title']}** ({i['sku']}): {i['quantity']} units "
                        f"(reorder at {i['reorder_point']}) "
                        f"[source:{i['source_platform']}.inventory.{i['source_row_id']}]\n"
                    )

            return response, citations, tool_calls_made

        elif any(w in msg_lower for w in ["product", "catalog", "sku"]):
            result = await tool_registry.execute("query_products", db, {"merchant_id": merchant_id})
            tool_results.append(result)
            tool_calls_made.append({"tool": "query_products", "args": {"merchant_id": merchant_id}})

            summary = result.get("data", {}).get("summary", {})
            products = result.get("data", {}).get("products", [])
            citations = citation_engine.extract_source_refs(tool_results)
            ref_strs = " ".join(
                f"[source:{p['source_platform']}.product.{p['source_row_id']}]"
                for p in products[:3]
            )

            response = (
                f"Product catalog summary:\n\n"
                f"- **Total Products:** {summary.get('total_products', 0)} {ref_strs}\n"
                f"- **Average Price:** ₹{summary.get('avg_price', 0):,.2f} {ref_strs}\n"
                f"- **Price Range:** ₹{summary.get('min_price', 0):,.2f} — ₹{summary.get('max_price', 0):,.2f} {ref_strs}\n"
            )

            return response, citations, tool_calls_made

        # Default response
        return (
            "I can help with merchant operations questions about:\n"
            "- Orders, revenue, refunds, and payments\n"
            "- Campaign performance, spend, and ROAS\n"
            "- Inventory, low-stock issues, and products\n\n"
            "Try asking: *\"Which campaigns have low ROAS?\"* or *\"Show refund trends.\"*"
        ), [], []

    async def _get_or_create_session(
        self, db: AsyncSession, session_id: str, merchant_id: str
    ) -> ChatSession:
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session and session.merchant_id != merchant_id:
            raise HTTPException(status_code=400, detail="Session does not belong to the selected merchant.")
        if not session:
            session = ChatSession(id=session_id, merchant_id=merchant_id)
            db.add(session)
            await db.flush()
        return session

    async def _build_messages(
        self, db: AsyncSession, session_id: str, current_message: str
    ) -> list[dict]:
        """Build OpenAI messages array from session history."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .limit(20)  # Keep context window manageable
        )
        history = result.scalars().all()

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": current_message})
        return messages

    async def _save_message(
        self, db: AsyncSession, session_id: str, role: str,
        content: str, citations: list | None = None, tool_calls: list | None = None,
    ) -> ChatMessage:
        session = await db.get(ChatSession, session_id)
        if session:
            session.updated_at = datetime.now(timezone.utc)
            if not session.title and role == "user":
                session.title = content[:80]
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            citations=citations,
            tool_calls=tool_calls,
        )
        db.add(msg)
        return msg

    async def get_history(
        self, db: AsyncSession, session_id: str, merchant_id: str
    ) -> ChatHistoryResponse:
        session = await self._require_session(db, session_id, merchant_id)
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        return ChatHistoryResponse(
            session_id=session.id,
            merchant_id=session.merchant_id,
            messages=[
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "citations": m.citations,
                    "tool_calls": m.tool_calls,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        )

    async def get_latest_session(
        self, db: AsyncSession, merchant_id: str
    ) -> ChatSessionSummary | None:
        result = await db.execute(
            select(ChatSession, func.count(ChatMessage.id).label("message_count"))
            .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.merchant_id == merchant_id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.updated_at.desc())
            .limit(1)
        )
        row = result.first()
        if not row:
            return None

        session, message_count = row
        return ChatSessionSummary(
            session_id=session.id,
            merchant_id=session.merchant_id,
            title=session.title,
            updated_at=session.updated_at,
            message_count=message_count or 0,
        )

    async def get_active_session(
        self, db: AsyncSession, merchant_id: str
    ) -> ChatSessionSummary:
        """
        Return the most recent session for a merchant.
        Create one silently if the merchant has no sessions yet.
        """
        latest = await self.get_latest_session(db, merchant_id)
        if latest:
            return latest
        return await self.create_session(db, merchant_id)

    async def create_session(
        self, db: AsyncSession, merchant_id: str
    ) -> ChatSessionSummary:
        """Create a new empty chat session for a merchant."""
        session = ChatSession(
            merchant_id=merchant_id,
            title="New conversation",
        )
        db.add(session)
        await db.flush()
        return ChatSessionSummary(
            session_id=session.id,
            merchant_id=session.merchant_id,
            title=session.title,
            updated_at=session.updated_at,
            message_count=0,
        )

    async def _require_session(
        self, db: AsyncSession, session_id: str, merchant_id: str
    ) -> ChatSession:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.merchant_id == merchant_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found for this merchant.")
        return session

    async def _is_in_domain(
        self, db: AsyncSession, session_id: str, message: str
    ) -> bool:
        normalized = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in message)
        tokens = set(normalized.split())
        if tokens & self.DOMAIN_KEYWORDS:
            return True

        if len(tokens) <= 6:
            result = await db.execute(
                select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
            )
            prior_messages = result.scalar() or 0
            return prior_messages > 0

        return False

    def _is_greeting(self, message: str) -> bool:
        normalized = " ".join(
            "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in message).split()
        )
        if not normalized:
            return False

        tokens = set(normalized.split())
        if tokens & self.DOMAIN_KEYWORDS:
            return False

        greeting_phrases = {
            "hi",
            "hello",
            "hey",
            "hey there",
            "hi there",
            "good morning",
            "good afternoon",
            "good evening",
            "namaste",
            "thanks",
            "thank you",
        }
        if normalized in greeting_phrases:
            return True

        return len(tokens) <= 4 and tokens <= {
            "hi", "hello", "hey", "there", "good", "morning", "afternoon",
            "evening", "namaste", "thanks", "thank", "you",
        }

    async def _business_fallback_if_needed(
        self,
        db: AsyncSession,
        user_message: str,
        merchant_id: str,
        response_text: str,
        tool_calls_made: list[dict],
        available_citations: list[Citation] | None = None,
    ) -> tuple[str, list[Citation], list[dict]] | None:
        """
        Deterministic rescue path for valid business questions.

        The LLM is still used for most chat turns, but common operational
        questions should never end in a generic refusal if our tools can compute
        a grounded answer.
        """
        if not self._should_use_business_fallback(
            user_message,
            response_text,
            tool_calls_made,
            available_citations or [],
        ):
            return None

        msg_lower = user_message.lower()
        days = self._infer_days_back(user_message)

        if any(word in msg_lower for word in ["revenue", "sales", "order", "orders", "gmv", "aov"]):
            paid_revenue_question = (
                any(word in msg_lower for word in ["revenue", "sales", "gmv", "aov"])
                and "refund" not in msg_lower
            )
            args = {
                "merchant_id": merchant_id,
                "days_back": days,
                "financial_status": "paid" if paid_revenue_question else "",
                "aggregation": "both",
            }
            result = await tool_registry.execute("query_orders", db, args)
            citations = citation_engine.extract_source_refs([result])
            response = self._format_order_answer(user_message, result, citations)
            return response, citations, [{"tool": "query_orders", "args": args}]

        if "refund" in msg_lower or "returned" in msg_lower:
            args = {"merchant_id": merchant_id, "days": max(days, 8)}
            result = await tool_registry.execute("analyze_refund_patterns", db, args)
            citations = citation_engine.extract_source_refs([result])
            data = result.get("data", {})
            refs = self._citation_refs(citations)
            response = (
                f"Refund trend for the last {args['days']} days: current refund rate is "
                f"{data.get('refund_rate', 0) * 100:.2f}%, versus a 7-day baseline mean of "
                f"{data.get('mean', 0) * 100:.2f}% and standard deviation of "
                f"{data.get('std', 0) * 100:.2f}%. Affected refunded revenue is "
                f"₹{data.get('affected_revenue', 0):,.2f}. "
                f"Anomaly detected: {'yes' if data.get('anomaly') else 'no'}. {refs}"
            )
            return response, citations, [{"tool": "analyze_refund_patterns", "args": args}]

        if "payment" in msg_lower or "payments" in msg_lower or "razorpay" in msg_lower:
            status = None
            if "failed" in msg_lower:
                status = "failed"
            elif "captured" in msg_lower or "paid" in msg_lower:
                status = "captured"
            elif "refunded" in msg_lower:
                status = "refunded"

            args = {"merchant_id": merchant_id, "limit": 10}
            if status:
                args["status"] = status
            result = await tool_registry.execute("query_payments", db, args)
            citations = citation_engine.extract_source_refs([result])
            records = result.get("data", {}).get("records", [])
            refs = self._citation_refs(citations)
            total_amount = sum(float(record.get("amount") or 0) for record in records)
            label = f"{status} " if status else ""
            response = (
                f"I found {len(records)} recent {label}payment records totaling "
                f"₹{total_amount:,.2f}. {refs}"
            )
            if records:
                response += "\n" + "\n".join(
                    f"- {record.get('status', 'unknown')}: ₹{float(record.get('amount') or 0):,.2f} "
                    f"via {record.get('method', 'unknown')}"
                    for record in records[:3]
                )
            return response, citations, [{"tool": "query_payments", "args": args}]

        if any(word in msg_lower for word in ["campaign", "campaigns", "roas", "ad", "ads", "spend", "marketing", "cost", "costs"]):
            args = {"merchant_id": merchant_id, "days": days}
            result = await tool_registry.execute("analyze_channel_roas", db, args)
            citations = citation_engine.extract_source_refs([result])
            data = result.get("data", {})
            channels = data.get("channels", [])
            if not channels:
                return None

            lines = [
                (
                    f"Channel performance over the last {days} days: overall ROAS is "
                    f"{data.get('overall_roas', 0)}x on ₹{data.get('total_spend', 0):,.2f} "
                    f"spend and ₹{data.get('total_revenue', 0):,.2f} revenue."
                )
            ]
            for row in channels[:3]:
                refs = " ".join(f"[source:{ref}]" for ref in row.get("source_refs", [])[:2])
                lines.append(
                    f"- {row['channel']}: ROAS {row['roas']}x, spend ₹{row['spend']:,.2f}, "
                    f"revenue ₹{row['revenue']:,.2f}. {refs}"
                )
            return "\n".join(lines), citations, [{"tool": "analyze_channel_roas", "args": args}]

        if any(word in msg_lower for word in ["inventory", "stock", "sku", "reorder"]):
            args = {"merchant_id": merchant_id}
            result = await tool_registry.execute("query_inventory", db, args)
            citations = citation_engine.extract_source_refs([result])
            data = result.get("data", {})
            summary = data.get("summary", {})
            items = data.get("inventory", [])
            refs = self._citation_refs(citations)
            response = (
                f"Inventory snapshot: {summary.get('total_items', 0)} SKUs, "
                f"{summary.get('total_quantity', 0)} total units, and "
                f"{summary.get('low_stock_count', 0)} low-stock alerts. {refs}"
            )
            low_items = [item for item in items if item.get("is_low_stock")]
            if low_items:
                response += "\n" + "\n".join(
                    f"- {item['product_title']} ({item['sku']}): {item['quantity']} units"
                    for item in low_items[:3]
                )
            return response, citations, [{"tool": "query_inventory", "args": args}]

        return None

    def _should_use_business_fallback(
        self,
        user_message: str,
        response_text: str,
        tool_calls_made: list[dict],
        available_citations: list[Citation],
    ) -> bool:
        msg_lower = user_message.lower()
        business_terms = {
            "revenue", "sales", "order", "orders", "gmv", "aov", "refund",
            "campaign", "campaigns", "roas", "ad", "ads", "spend", "marketing",
            "cost", "costs", "inventory", "stock", "sku", "payment", "payments",
        }
        if not any(term in msg_lower for term in business_terms):
            return False

        weak_answer_phrases = [
            "i don't have enough data",
            "i do not have enough data",
            "not enough data to answer",
            "couldn't generate a response",
            "i can only provide insights",
            "i can only help",
        ]
        response_lower = response_text.lower()
        if not tool_calls_made or any(phrase in response_lower for phrase in weak_answer_phrases):
            return True

        return self._has_invalid_or_missing_citations(response_text, available_citations)

    def _has_invalid_or_missing_citations(
        self,
        response_text: str,
        available_citations: list[Citation],
    ) -> bool:
        if not available_citations:
            return False

        allowed_refs = {citation.ref_string for citation in available_citations}
        cited_refs = set(re.findall(r"\[source:([^\]]+)\]", response_text))

        if cited_refs:
            return not any(ref in allowed_refs for ref in cited_refs)

        has_numeric_claim = bool(
            re.search(r"(?:₹|Rs\.?|INR\s*)\s*[\d,]+(?:\.\d+)?|\b\d{2,}(?:\.\d+)?\b", response_text)
        )
        return has_numeric_claim

    def _infer_days_back(self, user_message: str) -> int:
        msg_lower = user_message.lower()

        explicit_days = re.search(r"(?:last|past|previous)?\s*(\d{1,3})\s*days?", msg_lower)
        if explicit_days:
            return max(1, min(int(explicit_days.group(1)), 365))

        if "quarter" in msg_lower:
            return 90
        if "month" in msg_lower:
            return 30
        if "week" in msg_lower:
            return 7
        if "yesterday" in msg_lower or "today" in msg_lower:
            return 1
        return 30

    def _format_order_answer(
        self,
        user_message: str,
        tool_result: dict[str, Any],
        citations: list[Citation],
    ) -> str:
        data = tool_result.get("data", {})
        summary = data.get("summary", {})
        orders = data.get("orders", [])
        coverage = data.get("data_coverage", {})
        refs = self._citation_refs(citations)
        days = int(summary.get("period_days") or coverage.get("requested_period_days") or self._infer_days_back(user_message))
        period_label = self._period_label(user_message, days)

        total_orders = int(summary.get("total_orders", 0) or 0)
        total_revenue = float(summary.get("total_revenue", 0) or 0)
        avg_order_value = float(summary.get("avg_order_value", 0) or 0)
        status_scope = summary.get("financial_status", "all")
        order_label = "paid orders" if status_scope == "paid" else "orders"
        data_label = "paid order" if status_scope == "paid" else "order"

        if total_orders == 0:
            return (
                f"I don't see synced {order_label} for {period_label} yet, so recorded revenue "
                f"for that period is ₹0.00. Once Shopify sync includes that period, I can "
                f"break it down by orders, products, and AOV."
            )

        if coverage.get("used_latest_available_window"):
            latest = self._format_date(coverage.get("latest_order_date"))
            start = self._format_date(coverage.get("analysis_start"))
            end = self._format_date(coverage.get("analysis_end"))
            response = (
                f"I don't see synced {order_label} in the requested {period_label}. The latest synced "
                f"{data_label} data is from {latest}. In the latest available {days}-day window "
                f"({start} to {end}), recorded revenue was ₹{total_revenue:,.2f} from "
                f"{total_orders} {order_label}, with AOV of ₹{avg_order_value:,.2f}. {refs}"
            )
        else:
            response = (
                f"Recorded revenue for {period_label} was ₹{total_revenue:,.2f} from "
                f"{total_orders} {order_label}, with AOV of ₹{avg_order_value:,.2f}. {refs}"
            )

        if orders:
            response += "\n\nRecent orders used:\n"
            for order in orders[:3]:
                response += (
                    f"- #{order['order_number']}: ₹{order['total_amount']:,.2f} "
                    f"({order['financial_status']}) "
                    f"[source:{order['source_platform']}.order.{order['source_row_id']}]\n"
                )
        return response.strip()

    def _period_label(self, user_message: str, days: int) -> str:
        msg_lower = user_message.lower()
        if "last week" in msg_lower:
            return "last week"
        if "this week" in msg_lower:
            return "this week"
        if "last month" in msg_lower or "this month" in msg_lower:
            return "the last month"
        if "yesterday" in msg_lower:
            return "yesterday"
        if "today" in msg_lower:
            return "today"
        return f"the last {days} days"

    def _format_date(self, value: Any) -> str:
        if not value:
            return "the latest synced date"
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y").replace(" 0", " ")
        except ValueError:
            return str(value)

    def _citation_refs(self, citations: list[Citation], limit: int = 3) -> str:
        return " ".join(f"[source:{citation.ref_string}]" for citation in citations[:limit])

    def _generate_followups(
        self, user_message: str, response_text: str, tool_calls_made: list[dict]
    ) -> list[str]:
        tools_used = [tc.get("tool") for tc in tool_calls_made if tc.get("tool")]
        msg_lower = user_message.lower()
        response_lower = response_text.lower()

        suggestions: list[str] = []

        if any(word in msg_lower for word in ["refund", "returned", "failed payment"]) or "refunded orders" in response_lower:
            suggestions.extend([
                "Compare refunds against captured payments",
                "Which orders were refunded most recently?",
                "Is the refund rate anomalous this week?",
                "Show failed or refunded payments",
            ])

        if "analyze_channel_roas" in tools_used or "channel" in msg_lower:
            suggestions.extend([
                "Compare campaign ROAS by channel",
                "Which channel is least efficient right now?",
                "How much revenue is each channel driving?",
            ])
        if "query_campaigns" in tools_used or any(word in msg_lower for word in ["campaign", "roas", "spend"]):
            suggestions.extend([
                "Which campaigns are underperforming right now?",
                "Compare campaign ROAS by channel",
                "Show my best ROAS campaigns",
            ])
        if "query_inventory" in tools_used or any(word in msg_lower for word in ["inventory", "stock", "sku"]):
            suggestions.extend([
                "Which products are low on inventory?",
                "Show all out-of-stock items",
                "What should we reorder first?",
            ])
        if "query_orders" in tools_used or any(word in msg_lower for word in ["order", "revenue", "refund", "sales"]):
            suggestions.extend([
                "Show refund trends",
                "Which products are driving the most revenue?",
                "What is my average order value?",
            ])
        if "query_payments" in tools_used or "payment" in msg_lower:
            suggestions.extend([
                "Show refunded payments",
                "Which payments failed recently?",
                "Cross-check payments against recent orders",
            ])

        if not suggestions and "campaign" in response_lower:
            suggestions.extend([
                "Which campaigns have low ROAS?",
                "Compare campaign ROAS by channel",
                "Show ad spend vs revenue",
            ])

        if not suggestions and "inventory" in response_lower:
            suggestions.extend([
                "Which products are low on inventory?",
                "Show low stock items by SKU",
                "What should we reorder first?",
            ])

        if not suggestions:
            suggestions.extend([
                "Which campaigns have low ROAS?",
                "Show refund trends",
                "Which products are low on inventory?",
            ])

        deduped: list[str] = []
        for suggestion in suggestions:
            if suggestion not in deduped:
                deduped.append(suggestion)
            if len(deduped) == 3:
                break

        return deduped


# Singleton
chat_service = ChatService()
