# D2C AI Employee — v0

## 1. What I Built (5 lines)

FastAPI backend, SQLite warehouse, SQLAlchemy models, connector sync jobs, grounded chat, and autonomous agent runs in one deployable app.
Connectors ingest commerce, payment, ops, and marketing data, then normalize it into merchant-scoped tables with provenance on every row.
The chat layer uses OpenAI function calling over explicit analytical tools instead of letting the model invent business answers.
The frontend is a Next.js demo shell for dashboard metrics, connector status, merchant-scoped chat sessions, citations, and follow-up prompts.
I intentionally optimized for development speed and clarity over infrastructure complexity.

## 2. Connectors

- **Razorpay**: payment truth for Indian D2C. The live connector path is implemented; demo mode uses realistic captured, refunded, and failed payment rows so reviewers can run without Razorpay credentials.
- **Google Sheets**: founder/operator workspace truth. The live Sheets API path is implemented; demo mode returns campaign and ops rows because this is where early D2C teams actually track spend and inventory exceptions.
- **Shopify**: commerce truth for orders, products, and inventory. This is mocked in the current demo window; the abstraction is live-shaped, but OAuth and webhook ingestion are not built.
- **Meta Ads**: paid acquisition signal. Present as a mock/live-shaped connector so ROAS questions have campaign data; production auth and rate-limit handling are not complete.

Mocks are acceptable here because the product question is not whether an API can be called. The product question is whether raw connector rows can become grounded, cited operational decisions.

## 3. Schema

Data is normalized after ingestion because each source speaks a different shape, but the copilot needs stable entities: `orders`, `payments`, `products`, `inventory`, `ad_campaigns`, `source_records`, `agent_logs`, `chat_sessions`, and `chat_messages`.

Every normalized row carries a provenance block:

```text
source_platform
source_row_id
synced_at
raw_payload
```

That shape keeps the system debuggable. If the assistant says revenue was `₹2,698`, the app can point back to the exact Shopify order rows that produced it.

`merchant_id` is on every business table. Time-series queries are designed around `merchant_id + timestamp` because most useful D2C questions are scoped like “for this merchant, in this window, what changed?” Customer joins are not fully exploited yet, but the intended join key is `customer_id/email + timestamp` across orders, payments, refunds, and support/ops rows.

## 4. Chat

Tools exposed to the model:

- `query_orders`: order count, revenue, AOV, order detail, latest available fallback window.
- `query_campaigns`: campaign spend, revenue, ROAS, status-level summaries.
- `query_products`: catalog and pricing.
- `query_inventory`: stock levels and low-stock alerts.
- `query_payments`: Razorpay payment records by status/customer/order.
- `analyze_channel_roas`: channel-level spend, revenue, ROAS, and reallocation context.
- `analyze_refund_patterns`: refund rate, 7-day baseline, standard deviation, anomaly flag, affected revenue.

The citation contract is simple: every tool returns `source_refs`; every numerical answer must include `[source:platform.entity.id]`; the frontend renders the same full source token in message text, footer chips, and the citation sidebar.

Strategy questions do not get generic ChatGPT advice. For “How do I reduce marketing costs?”, the system calls `analyze_channel_roas` first and answers from channel-level ROAS. For “What was revenue last week?”, it calls `query_orders`; if the literal window has no synced rows, it says that and answers from the latest available equivalent window instead of pretending the data is current.

## 5. Agent

The main agent is the **Ad Spend Analyzer** because wasted paid spend is usually the fastest controllable leak in an early D2C business.

Run chain:

```text
trigger -> campaign query -> ROAS calculation -> underperformance decision -> recommended action -> logged reasoning
```

It flags campaigns with spend above threshold and ROAS below target, estimates avoidable spend, and writes the reasoning to `agent_logs`. The Refund Watcher uses the same idea for refunds: query payment/refund data, compare current rate against a 7-day baseline, then log whether the spike is anomalous.

Reasoning is explicit, not hidden in model prose. Agent run records include trigger, data summary, reasoning, proposed action, estimated savings, confidence, `would_execute=false`, and citations. Agents recommend; they do not mutate ad accounts, issue refunds, or change inventory.

## 6. Scale

Current system is a good single-founder MVP, not a production multi-tenant platform.

What works from 1 to maybe tens of merchants:

- Merchant-scoped SQL tables.
- Stateless connector classes.
- Async FastAPI/httpx/SQLAlchemy flow.
- Provenance stored with each row.
- Tool outputs small enough for grounded chat.

What breaks first:

- SQLite is single-node and file-locked. Concurrent writes from 10,000 merchants will deadlock.
- OpenAI calls will become the slowest user-facing dependency.
- Connector rate limits will need retry, backoff, and job state.
- Long-running syncs should not share request/response latency.

Migration path:

- Move SQLite/DuckDB-style local storage to PostgreSQL.
- Add read replicas for dashboard/chat reads.
- Add Celery + Redis for connector sync and scheduled agent runs.
- Shard by `merchant_id` only after PostgreSQL and queueing are exhausted.
- Keep the connector/tool contracts stable so the infra swap does not rewrite the product.

## 7. Eval

Known limitations:

- Shopify is mocked. The connector abstraction is real; Shopify OAuth, webhooks, and pagination are not.
- Razorpay and Google Sheets have live-shaped paths, but the default demo runs in mock mode so it can be reviewed without SaaS setup.
- Chat citations can still fail on vague questions or if the model cites shortened IDs. The backend now falls back to deterministic tool answers when citations are invalid.
- Agent thresholds are hardcoded. A real merchant needs learned baselines by category, margin, channel, and seasonality.
- No multi-tenant auth. `merchant_id` is trusted input, which is acceptable for a demo and unacceptable in production.
- No serious retry logic for Razorpay, Sheets, Shopify, or Meta rate limits.
- SQLite locking is mitigated for the demo, not solved for production.
- The frontend is good enough to prove the workflow; it is not the product moat.

## 8. Hours

~2 hours. 1 session.

The time went into the connector abstraction, seeded demo loop, grounded tools, citation enforcement, merchant-scoped chat persistence, and agent reasoning. I did not spend that time on infrastructure ceremony.

## 9. Another Week

Priority order:

1. Live Shopify OAuth, pagination, and webhooks.
2. Shiprocket connector for fulfillment, RTO, SLA, and delivery exceptions.
3. Meta Ads live connector with account selection and rate-limit backoff.
4. PostgreSQL migration with proper migrations and seed idempotency.
5. Celery + Redis for connector sync, agent scheduling, and retries.
6. Learned thresholds for ROAS and refunds instead of fixed `2σ` and static ROAS targets.
7. Multi-tenant auth with user-to-merchant access control.
8. Evaluation set for chat: citation precision, refusal accuracy, and tool-choice accuracy.
9. Better frontend charts for revenue, refunds, campaign efficiency, and inventory risk.

## AI Disclosure

LLM scaffolded parts of the Pydantic models, SQLAlchemy boilerplate, and OpenAI function-calling glue.

I wrote and/or materially directed the connector abstraction, normalized schema shape, provenance contract, citation enforcement behavior, merchant-scoped chat persistence, analytical tools, agent reasoning chain, and the demo operating flow.

## Setup

Recommended path for review is backend-first. The backend contains the core submission: connectors, normalized warehouse, grounded tools, citations, seed data, and agent reasoning.

Clone after the GitHub repo is created:

```bash
git clone https://github.com/shathishkumarapi01-glitch/d2c-ai-employee.git
cd d2c-ai-employee
```

Run backend:

```bash
cd d2c-ai-employee
python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt
cd backend
../venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 3005 --reload
```

Open:

```text
Backend docs: http://localhost:3005/docs
```

Seed demo data:

```bash
curl -X POST http://localhost:3005/api/v1/dashboard/seed
```

Ask the chat API:

```bash
curl -X POST http://localhost:3005/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"merchant_id":"merchant-001","message":"Which campaigns have low ROAS?"}'
```

### Optional Frontend

The Next.js frontend is included as a demo shell for reviewers who want to click through dashboard/chat flows. It is not the core artifact and may need local Node/npm cleanup depending on the machine.

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
Frontend: http://localhost:3001
```

Known frontend caveats:

- It assumes the backend is running on `http://localhost:3005`.
- It is a thin demo UI, not a production frontend.
- If install/build fails locally, use the backend API and `/docs`; the backend is the reliable review path.
