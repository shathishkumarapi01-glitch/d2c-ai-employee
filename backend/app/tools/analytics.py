"""
Analytical tools for higher-level D2C business insights.

These tools sit above raw entity queries and compute decision-ready metrics
that the chat system can use for strategic questions.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ad_campaign import AdCampaign
from app.models.payment import Payment


ANALYZE_CHANNEL_ROAS_SCHEMA = {
    "name": "analyze_channel_roas",
    "description": (
        "Analyze ROAS (Return on Ad Spend) by marketing channel across ALL campaign "
        "sources (Meta Ads, Google Sheets, etc.) for a merchant. Groups campaigns by "
        "channel/objective, computes spend vs revenue, and returns ROAS per channel. "
        "Use this for questions about marketing costs, channel efficiency, ad spend, "
        "budget reallocation, or reducing marketing costs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "merchant_id": {
                "type": "string",
                "description": "Merchant UUID",
            },
            "days": {
                "type": "integer",
                "description": "Number of trailing days to analyze. Default 30.",
                "default": 30,
            },
        },
        "required": ["merchant_id"],
    },
}

ANALYZE_REFUND_PATTERNS_SCHEMA = {
    "name": "analyze_refund_patterns",
    "description": (
        "Analyze refund behavior for a merchant over a trailing window, detect spikes "
        "against a 7-day baseline, and estimate affected revenue."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "merchant_id": {
                "type": "string",
                "description": "Merchant UUID",
            },
            "days": {
                "type": "integer",
                "description": "Number of trailing days to analyze. Default 30.",
                "default": 30,
            },
        },
        "required": ["merchant_id"],
    },
}


def _ref_string(source_platform: str, entity_type: str, source_row_id: str) -> str:
    return f"{source_platform}.{entity_type}.{source_row_id}"


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _derive_channel(campaign: AdCampaign) -> str:
    """
    Derive a human-readable channel name from a campaign row.

    Google Sheets connector stores the actual channel (meta, whatsapp, google,
    instagram) in the `objective` field.  Meta Ads connector stores the Facebook
    objective (REACH, CONVERSIONS, …) there instead, so we fall back to the
    source_platform name.
    """
    objective = (campaign.objective or "").strip().lower()

    # Google Sheets rows already have the real channel in `objective`
    if campaign.source_platform == "google_sheets" and objective:
        return objective

    # Meta Ads — use source_platform as the channel label
    if campaign.source_platform == "meta_ads":
        return "meta_ads"

    # Anything else — use whatever we have
    return objective or campaign.source_platform or "unknown"


async def analyze_channel_roas(
    db: AsyncSession,
    merchant_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """
    Calculate ROAS per channel from ALL ad_campaign rows for a merchant.

    Each campaign already carries its own `spend` and `revenue` columns
    (populated by the connector that synced it), so we aggregate directly
    instead of cross-referencing with the payments table.  This means the
    tool works regardless of which connectors are active (Meta Ads, Google
    Sheets, or both).
    """
    days = max(1, min(days, 365))
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()

    # ── Query ALL campaigns for the merchant (no source_platform filter) ──
    campaign_stmt = (
        select(AdCampaign)
        .where(
            and_(
                AdCampaign.merchant_id == merchant_id,
                or_(
                    AdCampaign.date_start.is_(None),
                    AdCampaign.date_start >= cutoff_date,
                ),
            )
        )
        .order_by(AdCampaign.date_start.asc(), AdCampaign.campaign_name.asc())
    )

    campaign_rows = (await db.execute(campaign_stmt)).scalars().all()

    result: dict[str, Any] = {"source_refs": [], "data": {}}

    if not campaign_rows:
        result["data"] = {
            "channels": [],
            "summary": f"No campaign data found for the last {days} days.",
        }
        return result

    # ── Aggregate by channel ──────────────────────────────────────────────
    channels: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "channel": "unknown",
            "spend": 0.0,
            "revenue": 0.0,
            "campaign_count": 0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "source_refs": [],
            "campaigns": [],
        }
    )
    all_source_refs: list[dict[str, Any]] = []

    for row in campaign_rows:
        channel = _derive_channel(row)
        bucket = channels[channel]
        bucket["channel"] = channel
        bucket["spend"] += _as_float(row.spend)
        bucket["revenue"] += _as_float(row.revenue)
        bucket["campaign_count"] += 1
        bucket["impressions"] += row.impressions or 0
        bucket["clicks"] += row.clicks or 0
        bucket["conversions"] += row.conversions or 0

        ref = _ref_string(row.source_platform, "ad_campaign", row.source_row_id)
        if ref not in bucket["source_refs"]:
            bucket["source_refs"].append(ref)

        bucket["campaigns"].append({
            "name": row.campaign_name,
            "spend": _as_float(row.spend),
            "revenue": _as_float(row.revenue),
            "roas": round(_as_float(row.revenue) / _as_float(row.spend), 2)
            if _as_float(row.spend) > 0
            else 0.0,
            "ref": ref,
        })

        all_source_refs.append({
            "source_platform": row.source_platform,
            "entity_type": "ad_campaign",
            "source_row_id": row.source_row_id,
            "field": "spend",
            "value": _as_float(row.spend),
        })

    # ── Build channel-level summary rows ──────────────────────────────────
    channel_rows: list[dict[str, Any]] = []
    for bucket in channels.values():
        spend = round(bucket["spend"], 2)
        revenue = round(bucket["revenue"], 2)
        roas = round(revenue / spend, 2) if spend > 0 else 0.0

        channel_rows.append({
            "channel": bucket["channel"],
            "spend": spend,
            "revenue": revenue,
            "roas": roas,
            "campaign_count": bucket["campaign_count"],
            "impressions": bucket["impressions"],
            "clicks": bucket["clicks"],
            "conversions": bucket["conversions"],
            "source_refs": bucket["source_refs"],
            "top_campaigns": sorted(
                bucket["campaigns"], key=lambda c: c["spend"], reverse=True
            )[:3],
        })

    channel_rows.sort(key=lambda r: (-r["roas"], -r["revenue"], r["channel"]))

    # ── Build human-readable summary ──────────────────────────────────────
    total_spend = sum(r["spend"] for r in channel_rows)
    total_revenue = sum(r["revenue"] for r in channel_rows)
    overall_roas = round(total_revenue / total_spend, 2) if total_spend > 0 else 0.0

    if channel_rows:
        best = channel_rows[0]
        worst = channel_rows[-1]
        summary = (
            f"Analyzed {len(campaign_rows)} campaigns across {len(channel_rows)} channels "
            f"over the last {days} days. "
            f"Overall ROAS: {overall_roas}x (₹{total_revenue:,.2f} revenue on ₹{total_spend:,.2f} spend). "
            f"Best channel: {best['channel']} at {best['roas']}x ROAS. "
            f"Worst channel: {worst['channel']} at {worst['roas']}x ROAS."
        )
    else:
        summary = f"No channel ROAS data found for the last {days} days."

    result["source_refs"] = all_source_refs
    result["data"] = {
        "channels": channel_rows,
        "summary": summary,
        "total_spend": total_spend,
        "total_revenue": total_revenue,
        "overall_roas": overall_roas,
    }
    return result


async def analyze_refund_patterns(
    db: AsyncSession,
    merchant_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """
    Analyze refund activity from Razorpay payments.

    The anomaly signal compares the most recent day's refund rate against a
    rolling 7-day baseline built from the preceding days in the same window.
    """
    days = max(8, min(days, 365))
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
    today = datetime.now(timezone.utc).date()
    current_day = today - timedelta(days=1)

    stmt = (
        select(Payment)
        .where(
            and_(
                Payment.merchant_id == merchant_id,
                Payment.source_platform == "razorpay",
                Payment.payment_date >= cutoff_dt,
            )
        )
        .order_by(Payment.payment_date.asc())
    )
    payment_rows = (await db.execute(stmt)).scalars().all()

    result: dict[str, Any] = {"source_refs": [], "data": {}}
    if not payment_rows:
        result["data"] = {
            "refund_rate": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "anomaly": False,
            "affected_revenue": 0.0,
            "summary": f"No Razorpay payment rows found for the last {days} days.",
            "source_refs": [],
        }
        return result

    daily_totals: dict[Any, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "refunds": 0.0, "refunded_amount": 0.0})
    source_refs: list[dict[str, Any]] = []

    for payment in payment_rows:
        payment_day = payment.payment_date.date() if payment.payment_date else current_day
        daily_totals[payment_day]["count"] += 1
        if payment.status == "refunded":
            daily_totals[payment_day]["refunds"] += 1
            daily_totals[payment_day]["refunded_amount"] += _as_float(payment.amount)

        source_refs.append({
            "source_platform": payment.source_platform,
            "entity_type": "payment",
            "source_row_id": payment.source_row_id,
            "field": "status",
            "value": payment.status,
        })

    baseline_days = [current_day - timedelta(days=offset) for offset in range(1, 8)]
    baseline_rates: list[float] = []
    for day in baseline_days:
        total = daily_totals[day]["count"]
        refunds = daily_totals[day]["refunds"]
        baseline_rates.append((refunds / total) if total > 0 else 0.0)

    current_total = daily_totals[current_day]["count"]
    current_refunds = daily_totals[current_day]["refunds"]
    current_refunded_amount = daily_totals[current_day]["refunded_amount"]
    current_rate = (current_refunds / current_total) if current_total > 0 else 0.0

    mean = sum(baseline_rates) / len(baseline_rates) if baseline_rates else 0.0
    variance = (
        sum((rate - mean) ** 2 for rate in baseline_rates) / len(baseline_rates)
        if baseline_rates else 0.0
    )
    std = variance ** 0.5
    anomaly = current_rate > (mean + 2 * std)

    result["source_refs"] = source_refs
    result["data"] = {
        "refund_rate": round(current_rate, 4),
        "mean": round(mean, 4),
        "std": round(std, 4),
        "anomaly": anomaly,
        "affected_revenue": round(current_refunded_amount, 2),
        "summary": (
            f"Current refund rate is {round(current_rate * 100, 2)}% on {current_day.isoformat()} "
            f"versus a 7-day baseline mean of {round(mean * 100, 2)}% and std of {round(std * 100, 2)}%."
        ),
        "source_refs": [
            f"{ref['source_platform']}.payments.{ref['source_row_id']}"
            for ref in source_refs[:10]
        ],
    }
    return result
