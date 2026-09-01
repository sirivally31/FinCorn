# FinRecon AI — Pitch

**"FinRecon AI closes the reconciliation loop instead of merely
generating finance summaries."**

## Problem

Every payment platform generates three parallel records for the same
transaction — the payment/gateway record, the bank settlement, and the
merchant's ledger entry. These disagree constantly: fees drift, GST
rounds differently, settlements arrive late, records go missing or
duplicate. Finance operations teams reconcile this manually today,
transaction by transaction, in spreadsheets.

## Solution

FinRecon AI runs a **deterministic reconciliation engine** across
payment, settlement and ledger records, auto-resolves the discrepancies
that are safely explainable by policy (small fee/tax drift, short
settlement delays), and surfaces everything else as an **honest,
AI-explained exception queue** — plus a live cash position and a
transparent forward cash forecast.

## How it works

1. **Deterministic engine first.** Every match/mismatch decision is pure
   rule-based comparison against configurable tolerances — no LLM call
   decides whether two financial records match.
2. **AI second.** An AI layer sits on top purely to explain, classify
   severity, and recommend next actions — grounded only in the numbers
   the engine already computed. It runs in a fully deterministic mock
   mode by default (no API key needed) and can be swapped to a real LLM
   via a clean `AIProvider` interface.
3. **Measure everything.** Match rate, auto-resolution rate, exception
   rate, settlement gap, and cash position are all computed live from the
   database on every run — never hardcoded.

## Differentiation

Reconciliation is the unglamorous backbone of every payment business —
and it's where money actually gets lost or found. A system that can
process a batch, tell you exactly how accurate it was, and hand you a
short, honest list of what it *couldn't* fix, is immediately useful to a
finance operations team — unlike a chatbot that answers questions about
payments in the abstract.

## Measurable Results (this exact codebase, one real run)

- 152 records processed
- 86.18% match rate
- 8 auto-resolved (safe, policy-bound corrections only)
- 21 unresolved, honestly reported
- ₹1,10,900 settlement gap explained, not hidden
- 1/3/7-day cash forecast, methodology shown in the UI

## Architecture

Deliberately minimal-dependency Python/Flask + SQLite backend and a
vanilla JS dashboard, chosen so it starts with a single command
(`./start.sh`) and no Docker/Maven/npm install — see the README for the
full architecture and the straightforward porting path to Spring Boot +
React + PostgreSQL + Docker for production.

## Demo Flow

1. **Setup:** 50+ synthetic payment, settlement, and ledger records are deterministically seeded.
2. **Reconciliation:** The system automatically matches records based on exact terms, then safely auto-resolves minor discrepancies using business rules.
3. **Exceptions & AI:** Open the manual exception queue view; review AI analysis which grounds itself strictly in database facts.
4. **Action:** Human applies an auto-logged final resolution based on the AI recommendation.
5. **Cash Position & Forecast:** End by showing the updated live cash position and forecast (7-day projection).
6. **Finance Q&A:** Chat with the AI using the generated metrics (e.g., "What is our current cash position?").

## Limitations

- Uses synthetic deterministic data (not inherently connected to a live bank feed).
- Demo-focused backend architecture (SQLite/Flask) built for rapid, dependency-light execution.
- Cash position accounting model is simplified for demo clarity.
- No live real-world authentication is enforced.

## Future scope

- Production port to the Spring Boot/React/Postgres/Docker stack
  (porting table included in README).
- Real bank statement ingestion (MT940/CAMT.053).
- Per-merchant, per-payment-method configurable tolerance bands.
- Multi-currency reconciliation.
- Role-based access and real authentication for finance teams.
