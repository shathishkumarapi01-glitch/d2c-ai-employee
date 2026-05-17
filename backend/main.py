"""CLI demo — seed, run agent, chat queries. Run from backend/ directory."""

from __future__ import annotations

import asyncio
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("demo")


async def main() -> None:
    from app.database import engine
    from app.models.base import Base

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.database import async_session_factory
    from app.seed.seed_data import seed_demo_data, MERCHANT_1_ID
    from app.agents.ad_spend_analyzer import ad_spend_analyzer
    from app.agents.refund_watcher import refund_watcher

    async with async_session_factory() as db:
        # ── Step 1: Seed ──────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 1 — SEEDING DATA")
        print("=" * 60)
        result = await seed_demo_data(db)
        await db.commit()
        print(json.dumps(result, indent=2, default=str))

        # ── Step 2: Run Ad Spend Agent ────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 2 — AD SPEND ANALYZER AGENT")
        print("=" * 60)
        recs = await ad_spend_analyzer.run(db, MERCHANT_1_ID, trigger="manual_demo")
        await db.commit()
        print(f"Generated {len(recs)} recommendations")
        for rec in recs[:2]:
            print(f"  - {rec.get('recommendation', '')[:120]}...")

        # ── Step 3: Run Refund Watcher ────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 3 — REFUND WATCHER AGENT")
        print("=" * 60)
        refund_recs = await refund_watcher.run(db, MERCHANT_1_ID, trigger="manual_demo")
        await db.commit()
        print(f"Generated {len(refund_recs)} run logs")
        for rec in refund_recs[:1]:
            print(json.dumps(rec, indent=2, default=str))

        # ── Step 4 & 5: Chat (requires OpenAI key) ───────────────────
        from app.config import settings
        if not settings.openai_api_key:
            print("\n⚠️  OPENAI_API_KEY not set — skipping live chat demo.")
            print("The API server still works with mock responses.")
            print("\nTo start the API server:")
            print("  cd backend && python3 -m uvicorn app.main:app --port 3005 --reload")
            print("\nThen try:")
            print("  curl -X POST http://localhost:3005/api/v1/chat \\")
            print('    -H "Content-Type: application/json" \\')
            print(f'    -d \'{{"message": "What was my revenue?", "merchant_id": "{MERCHANT_1_ID}"}}\'')
        else:
            from app.services.chat_service import chat_service
            from app.schemas.chat import ChatRequest

            for i, question in enumerate(
                ["What was my revenue last week?", "How do I reduce marketing costs?"],
                start=4,
            ):
                print(f"\n{'=' * 60}")
                print(f'STEP {i} — CHAT: "{question}"')
                print("=" * 60)
                req = ChatRequest(message=question, merchant_id=MERCHANT_1_ID)
                resp = await chat_service.process_message(db, req)
                await db.commit()
                print(f"\nAnswer:\n{resp.message[:500]}")
                print(f"\nTools used: {resp.tool_calls_made}")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print(f"\nStart the API server:  cd backend && python3 -m uvicorn app.main:app --port 3005 --reload")
    print(f"API docs:              http://localhost:3005/docs")
    print(f"Demo merchant ID:      {MERCHANT_1_ID}")


if __name__ == "__main__":
    asyncio.run(main())
