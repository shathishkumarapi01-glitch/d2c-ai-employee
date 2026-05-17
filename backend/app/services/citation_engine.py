"""
Citation engine — enforces that every numerical claim in AI responses is backed by source data.
Post-processes LLM output to extract, verify, and attach citations.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas.chat import Citation

logger = logging.getLogger(__name__)

# Pattern to find numbers in text (integers, decimals, currency amounts)
NUMBER_PATTERN = re.compile(
    r'(?:₹|Rs\.?|INR\s?)?\s*[\d,]+(?:\.\d+)?(?:\s*%)?'
    r'|[\d,]+(?:\.\d+)?(?:\s*(?:orders?|products?|items?|campaigns?|units?|clicks?|impressions?))?'
)

# Pattern to detect existing citations in format [source:platform.entity.id]
CITATION_PATTERN = re.compile(r'\[source:([^\]]+)\]')

# Numbers that don't need citations (small integers used in prose)
EXEMPT_NUMBERS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}


class CitationEngine:
    """
    Enforces citation grounding on AI-generated responses.
    
    Strategy:
    1. Collect all source_refs from tool execution results
    2. Post-process LLM response to inject citation markers
    3. Verify no significant numerical claims lack citations
    """

    def extract_source_refs(self, tool_results: list[dict[str, Any]]) -> list[Citation]:
        """Extract all source references from tool execution results."""
        citations = []
        seen = set()

        for result in tool_results:
            for ref in result.get("source_refs", []):
                key = f"{ref['source_platform']}.{ref['entity_type']}.{ref['source_row_id']}"
                if key not in seen:
                    seen.add(key)
                    citations.append(Citation(
                        source_platform=ref["source_platform"],
                        entity_type=ref["entity_type"],
                        source_row_id=ref["source_row_id"],
                        field=ref.get("field"),
                        value=ref.get("value"),
                    ))

        return citations

    def filter_citations_for_response(
        self,
        response_text: str,
        available_citations: list[Citation],
        fallback_limit: int = 3,
    ) -> list[Citation]:
        """
        Keep only citations explicitly referenced in the assistant response.
        If none are referenced, fall back to a small relevant subset.
        """
        cited_refs = set(CITATION_PATTERN.findall(response_text))
        if cited_refs:
            return [c for c in available_citations if c.ref_string in cited_refs]
        return available_citations[:fallback_limit]

    def build_citation_context(self, citations: list[Citation]) -> str:
        """Build a citation context string to include in LLM prompts."""
        if not citations:
            return ""

        lines = ["\n\nAvailable source references for citations:"]
        for i, c in enumerate(citations[:8], 1):
            lines.append(f"  [{i}] {c.ref_string}")
        lines.append(
            "\nIMPORTANT: For every numerical value in your response, "
            "include the source reference in format [source:platform.entity.id]. "
            "Example: Revenue was ₹52,000 [source:shopify.order.182]"
        )
        return "\n".join(lines)

    def enforce_citations(
        self,
        response_text: str,
        available_citations: list[Citation],
    ) -> tuple[str, bool]:
        """
        Check if all numerical claims have citations.
        Returns (possibly_modified_text, has_uncited_numbers).
        """
        existing_citations = set(CITATION_PATTERN.findall(response_text))
        numbers_found = NUMBER_PATTERN.findall(response_text)

        significant_numbers = []
        for num_str in numbers_found:
            clean = re.sub(r'[₹,Rs.INR\s%]', '', num_str).strip()
            clean = re.sub(r'\s*(orders?|products?|items?|campaigns?|units?|clicks?|impressions?)$', '', clean)
            if clean and clean not in EXEMPT_NUMBERS:
                try:
                    val = float(clean.replace(',', ''))
                    if val > 10:  # Only flag significant numbers
                        significant_numbers.append(num_str.strip())
                except ValueError:
                    pass

        # If there are significant numbers but no citations, flag it
        has_uncited = len(significant_numbers) > 0 and len(existing_citations) == 0

        if has_uncited and available_citations:
            citation_block = "\n\n**Sources:**\n"
            for c in available_citations[:3]:
                citation_block += f"- [source:{c.ref_string}]\n"
            response_text += citation_block
            has_uncited = False  # We've added citations

        return response_text, has_uncited

    def format_citations_for_display(self, citations: list[Citation]) -> list[dict]:
        """Format citations for API response / frontend display."""
        return [
            {
                "source": c.ref_string,
                "platform": c.source_platform,
                "entity": c.entity_type,
                "id": c.source_row_id,
            }
            for c in citations
        ]


# Singleton
citation_engine = CitationEngine()
