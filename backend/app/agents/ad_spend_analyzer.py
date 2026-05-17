"""
Ad Spend Analyzer Agent — detects campaigns with high spend but low conversions/ROAS.
Generates actionable recommendations with estimated savings.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.config import settings
from app.models.ad_campaign import AdCampaign
from app.models.agent_log import AgentLog
from app.models.order import Order

logger = logging.getLogger(__name__)


class AdSpendAnalyzer(BaseAgent):
    """
    Detects ad campaigns where ad spend is high but conversion/sales are low.
    
    Logic:
    1. Find campaigns with spend > threshold
    2. Calculate effective ROAS (revenue / spend)
    3. Flag campaigns below minimum ROAS threshold
    4. Generate recommendations with estimated savings
    5. Store with full reasoning chain and citations
    """

    name = "ad_spend_analyzer"
    description = "Analyzes ad campaigns to detect inefficient spend patterns"

    def __init__(self):
        self.min_spend = settings.ad_spend_min_spend
        self.roas_threshold = settings.ad_spend_roas_threshold

    async def analyze(self, db: AsyncSession, merchant_id: str) -> list[dict[str, Any]]:
        """Find campaigns with high spend and low ROAS."""
        stmt = select(AdCampaign).where(
            and_(
                AdCampaign.merchant_id == merchant_id,
                AdCampaign.spend >= self.min_spend,
                AdCampaign.status == "active",
            )
        )
        result = await db.execute(stmt)
        campaigns = result.scalars().all()

        findings = []
        for campaign in campaigns:
            spend = float(campaign.spend)
            revenue = float(campaign.revenue)
            roas = revenue / spend if spend > 0 else 0

            if roas < self.roas_threshold:
                # Calculate what "good" would look like
                target_revenue = spend * self.roas_threshold
                revenue_gap = target_revenue - revenue

                # Estimate potential savings if we reallocated this budget
                potential_savings = spend * (1 - (roas / self.roas_threshold)) if roas < self.roas_threshold else 0

                findings.append({
                    "campaign_id": str(campaign.id),
                    "campaign_name": campaign.campaign_name,
                    "source_platform": campaign.source_platform,
                    "source_row_id": campaign.source_row_id,
                    "spend": spend,
                    "revenue": revenue,
                    "actual_roas": round(roas, 2),
                    "target_roas": self.roas_threshold,
                    "impressions": campaign.impressions,
                    "clicks": campaign.clicks,
                    "conversions": campaign.conversions,
                    "cpc": float(campaign.cpc) if campaign.cpc else None,
                    "ctr": float(campaign.ctr) if campaign.ctr else None,
                    "revenue_gap": round(revenue_gap, 2),
                    "potential_savings": round(potential_savings, 2),
                    "date_start": str(campaign.date_start) if campaign.date_start else None,
                    "date_end": str(campaign.date_end) if campaign.date_end else None,
                })

        logger.info(
            "Ad spend analysis for merchant %s: %d campaigns analyzed, %d flagged",
            merchant_id, len(campaigns), len(findings),
        )
        return findings

    async def reason(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate recommendations from findings."""
        recommendations = []

        for finding in findings:
            roas = finding["actual_roas"]
            spend = finding["spend"]
            revenue = finding["revenue"]
            name = finding["campaign_name"]

            # Determine severity and confidence
            if roas < 0.5:
                severity = "critical"
                confidence = 0.95
                action = "Immediately pause or significantly reduce budget"
            elif roas < 1.0:
                severity = "high"
                confidence = 0.85
                action = "Reduce budget by 50% and optimize targeting"
            elif roas < self.roas_threshold:
                severity = "medium"
                confidence = 0.70
                action = "Review targeting and creative, consider A/B testing"
            else:
                continue

            # Build reasoning chain
            reasoning = (
                f"Campaign '{name}' is underperforming with {roas}x ROAS "
                f"(target: {self.roas_threshold}x). "
                f"Current spend: ₹{spend:,.2f}, Revenue generated: ₹{revenue:,.2f}. "
                f"At current efficiency, for every ₹1 spent, only ₹{roas:.2f} is returned. "
            )

            if finding.get("ctr") and finding["ctr"] < 1.0:
                reasoning += (
                    f"Click-through rate ({finding['ctr']:.2f}%) is below industry average, "
                    f"suggesting poor ad creative or targeting. "
                )

            if finding.get("conversions", 0) < 10:
                reasoning += (
                    f"Only {finding['conversions']} conversions from {finding['clicks']} clicks "
                    f"({(finding['conversions']/max(finding['clicks'],1)*100):.1f}% conversion rate), "
                    f"indicating a landing page or offer issue. "
                )

            recommendation = (
                f"**{action}** for campaign '{name}'. "
                f"Estimated potential savings: ₹{finding['potential_savings']:,.2f}. "
                f"Consider reallocating budget to higher-performing campaigns. "
                f"If optimizing rather than pausing, focus on: "
                f"1) Narrowing audience targeting, "
                f"2) Refreshing ad creative, "
                f"3) Testing different ad placements."
            )

            citations = [{
                "source_platform": finding["source_platform"],
                "entity_type": "ad_campaign",
                "source_row_id": finding["source_row_id"],
                "metrics": {
                    "spend": spend,
                    "revenue": revenue,
                    "roas": roas,
                    "conversions": finding.get("conversions", 0),
                },
            }]

            recommendations.append({
                "severity": severity,
                "reasoning": reasoning,
                "recommendation": recommendation,
                "estimated_savings": finding["potential_savings"],
                "confidence_score": confidence,
                "citations": citations,
                "campaign_name": name,
            })

        # Sort by potential savings (highest first)
        recommendations.sort(key=lambda r: r["estimated_savings"], reverse=True)
        return recommendations

    async def run(
        self, db: AsyncSession, merchant_id: str, trigger: str = "scheduled"
    ) -> list[dict[str, Any]]:
        """Full agent lifecycle: analyze → reason → store."""
        findings = await self.analyze(db, merchant_id)

        if not findings:
            logger.info("No underperforming campaigns found for merchant %s", merchant_id)
            return []

        # Use OpenAI for enhanced reasoning if available, otherwise use rule-based
        if not settings.mock_mode:
            recommendations = await self._openai_enhanced_reasoning(findings)
        else:
            recommendations = await self.reason(findings)

        # Persist recommendations
        stored = []
        for rec in recommendations:
            agent_log = AgentLog(
                merchant_id=merchant_id,
                agent_type=self.name,
                trigger=trigger,
                reasoning=rec.get("reasoning", "AI detected inefficient spend patterns."),
                recommendation=rec.get("recommendation", "Review campaign targeting and creative."),
                estimated_savings=rec.get("estimated_savings", 0),
                confidence_score=rec.get("confidence_score", 0.75),
                citations=rec.get("citations", []),
                status="pending",
                metadata_extra={"severity": rec.get("severity", "medium")},
            )
            db.add(agent_log)
            stored.append(rec)

        await db.flush()
        logger.info(
            "Agent %s generated %d recommendations for merchant %s",
            self.name, len(stored), merchant_id,
        )
        return stored

    async def _openai_enhanced_reasoning(
        self, findings: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Use OpenAI for more nuanced reasoning (when API key is available)."""
        import openai

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        prompt = (
            "You are an expert D2C marketing analyst. Analyze these underperforming ad campaigns "
            "and provide actionable recommendations. For each campaign, provide:\n"
            "1. Clear reasoning for why it's underperforming\n"
            "2. Specific recommendation\n"
            "3. Estimated savings if recommendation is followed\n"
            "4. Confidence score (0-1)\n\n"
            "IMPORTANT: Reference specific data points and cite sources.\n\n"
            f"Campaign Data:\n{json.dumps(findings, indent=2, default=str)}\n\n"
            "Respond in JSON format as a list of objects with keys: "
            "reasoning, recommendation, estimated_savings, confidence_score, severity"
        )

        try:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            recs = result if isinstance(result, list) else result.get("recommendations", [result])

            # Merge with original citations
            for i, rec in enumerate(recs):
                if i < len(findings):
                    rec["citations"] = [{
                        "source_platform": findings[i]["source_platform"],
                        "entity_type": "ad_campaign",
                        "source_row_id": findings[i]["source_row_id"],
                    }]
                    rec.setdefault("estimated_savings", findings[i]["potential_savings"])
                    rec.setdefault("confidence_score", 0.75)
                    rec.setdefault("severity", "medium")

            return recs

        except Exception as e:
            logger.warning("OpenAI reasoning failed, falling back to rules: %s", str(e))
            return await self.reason(findings)


# Singleton
ad_spend_analyzer = AdSpendAnalyzer()
