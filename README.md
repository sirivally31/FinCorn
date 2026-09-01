# FinRecon AI

**Autonomous reconciliation and cash intelligence for payment operations.**

Built for the Razorpay Buildathon — **AI Finance Controller** track
("Run the books and the cash position").

> This project uses synthetic data for demonstration purposes and does not
> process real financial transactions.

---

## 1. Problem

Payment operations generate financial records in at least three places —
the payment gateway, the bank/settlement file, and the merchant's ledger.
These records routinely disagree: fees drift, settlements arrive late,
amounts don't match, records go missing. Finance teams currently reconcile
this by hand, in spreadsheets, transaction by transaction.

## 2. Solution

## 3. Why AI Finance Controller
The AI Finance Controller track asks to 'run the books and the cash position'. FinRecon AI directly addresses this by ensuring no payments are blindly marked as 'resolved' by LLMs. It focuses on closing the gap between raw unstructured payment trails and the actual cash ledger, generating the necessary insights for real finance operations.

## 5. Data flow


FinRecon AI closes the loop automatically:

```
Payment Records
      ↓
Settlement Records
      ↓
Ledger Records
      ↓
Deterministic Reconciliation Engine   (pure business rules, no LLM)
      ↓
Exception Detection
      ↓
AI Investigation                       (explains, never decides matches)
      ↓
Safe Auto-Resolution                   (only within configured tolerance bands)
      ↓
Human Exception Queue                  (everything else, honestly reported)
      ↓
Cash Position
      ↓
Cash Forecast
```

The differentiator: **the system doesn't just generate AI summaries — it
processes a batch and measures its own performance.**

## 8. Evaluation methodology
Evaluation evaluates match rate, accuracy, and processing throughput using identical deterministic seeded synthetic constraints. The ground-truth exception list allows us to objectively categorize each AI explanation and verify zero false-positive resolutions.

## 9. Exact measured results from the latest run

These numbers come from a real, tested run of this exact codebase — see
"How these numbers were produced" below.

| Metric | Value |
|---|---|
| Records processed | **152** (150 seeded transactions + 1 injected duplicate + 1 orphan settlement) |
| Matched | 123 |
| Auto-resolved | 8 |
| Unresolved exceptions | 21 |
| Match rate | **86.18%** |
| Auto-resolution rate | 5.26% |
| Total payment value | ₹20,07,395.00 |
| Total settlement value | ₹18,96,495.00 |
| Settlement gap | ₹1,10,900.00 |
| Unresolved exception value | ₹1,82,002.50 |
| Current cash position | ₹11,10,071.20 |
| 7-day forecasted cash | ₹12,10,263.93 |

Re-running `POST /api/demo/reset` reproduces **exactly** these numbers,
because the synthetic dataset and its injected exceptions are generated
with a fixed random seed and a fixed exception recipe (see
`backend/seed.py`).

### How these numbers were produced

This is not a claim taken on faith — it's the actual output of:
```
python3 -m unittest tests.test_reconciliation -v   # 20/20 tests pass
curl -X POST http://localhost:8080/api/demo/reset
curl http://localhost:8080/api/dashboard/summary
```
run against this codebase before it was packaged.

---

## 4. Architecture

**Deliberately dependency-light** so it starts with one command and no
Docker/Maven/npm install is required:

- **Backend:** Python 3 + Flask (the only external dependency) + SQLite.
  Clean modules: `database.py` (schema), `seed.py` (synthetic data),
  `reconciliation.py` (deterministic engine — **zero LLM calls**),
  `cash.py` (cash position + forecast), `ai_provider.py` (AI abstraction),
  `app.py` (REST API + static file serving).
- **Frontend:** a single-page vanilla JS/HTML/CSS dashboard (no build step,
  no bundler) + Chart.js via CDN, served by the same Flask process on the
  same port.
- **Database:** SQLite file at `data/finrecon.db`. Schema mirrors what a
  PostgreSQL production schema would look like (see "Production notes"
  below for the translation).

This means: **`python3 app.py` starts the entire product — API and UI —
on `http://localhost:8080`.** No separate frontend server, no database
server to install, no network access required at runtime.

### Why not the originally-specified Java/Spring/React/Postgres/Docker stack?

That stack is exactly what a production version of this should be built
in (see "Production notes"), and the code here is organized so the port
is straightforward — controllers ↔ Flask routes, services ↔
`reconciliation.py`/`cash.py`, entities ↔ the SQLite schema, repository
methods ↔ the SQL in `database.py`. But the environment this project was
generated in has **no network access** (no Maven Central, no npm
registry, no Docker registry), so Spring Boot, React tooling, and
PostgreSQL/Docker images could not actually be downloaded, compiled, or
tested there. Rather than hand over hundreds of files that were never
compiled or run, this build uses only what could be installed and
executed **and verified** in that environment: Flask (already present
locally) and stdlib SQLite. Every number and endpoint in this README was
produced by actually running this code.

## 17. Production architecture

| This demo | Production equivalent |
|---|---|
| `database.py` SQLite schema | Flyway migration → same tables in PostgreSQL, add proper FKs |
| `seed.py` | A `DataSeeder`/`CommandLineRunner` bean, or a separate seeding service |
| `reconciliation.py` | `ReconciliationService` + `ReconciliationEngine` (pure Java, unit-testable) |
| `cash.py` | `CashPositionService` / `ForecastService` |
| `ai_provider.py` | `AIProvider` interface, `OpenAIProvider` / `MockAIProvider` beans, exactly as specified |
| `app.py` routes | Spring `@RestController`s, one per resource, same URL paths |
| `frontend/` vanilla JS | React + TypeScript + Vite + Tailwind + Recharts, same page structure |
| Single Flask process | `docker-compose.yml` with `frontend`, `backend`, `postgres` services |

---

## 5. Synthetic dataset

Generated deterministically (`random.seed(42)` + a fixed exception
recipe) in `backend/seed.py`:

- **150 payment transactions** (INR, realistic Indian merchant/customer/
  UPI data — **all synthetic, no real customer data**)
- **146 settlement records** (some payments deliberately have none —
  `MISSING_SETTLEMENT`)
- **150 ledger entries**
- **10 merchants** across Electronics, Grocery, Travel, Fashion, F&B,
  Retail, Fitness, Home, Transport, Healthcare
- **29 deliberately injected exceptions** across all 12 required categories:
  `AMOUNT_MISMATCH`, `MISSING_SETTLEMENT`, `FEE_MISMATCH`, `TAX_MISMATCH`,
  `SETTLEMENT_DELAY`, `PARTIAL_SETTLEMENT`, `REFERENCE_MISMATCH`,
  `LEDGER_MISMATCH`, `DUPLICATE_RECORD` (duplicate transaction and
  duplicate settlement both roll up to this), `UNKNOWN_TRANSACTION`,
  `STATUS_MISMATCH`.

Every fresh `POST /api/demo/reset` regenerates the **exact same** dataset
and the **exact same** reconciliation results — this is intentional, so
the demo is reproducible on stage.

## 6. Reconciliation methodology

`backend/reconciliation.py` — **pure, deterministic, rule-based.** It
never asks an LLM whether two records match. It walks every payment,
finds its settlement and ledger records by `transaction_id`, and applies
configurable tolerances:

- Amount tolerance: ₹5
- Fee tolerance: ₹5 (auto-resolve up to ₹50 drift)
- Tax tolerance: ₹2 (auto-resolve up to ₹15 drift)
- Date/settlement-delay tolerance: 48 hours (auto-resolve up to 7 days)

States: `MATCHED`, `AUTO_RESOLVED`, `UNRESOLVED`. **An exception is only
ever marked `AUTO_RESOLVED` if it falls inside these explicit business-
rule bands** (e.g. a small fee drift, a short settlement delay). Amount
mismatches, missing settlements, partial settlements, duplicates, unknown
transactions and reference mismatches are never auto-resolved — they stay
`UNRESOLVED` and visible, exactly as the brief requires ("honest exception
list").

## 7. AI methodology

`backend/ai_provider.py` implements the `AIProvider` interface with two
implementations:

- **`MockAIProvider`** (default, `AI_PROVIDER=mock`): rule-based, natural-
  language explanations built **only** from the actual payment/settlement/
  ledger numbers the deterministic engine already computed. No network,
  no API key, never breaks.
- **`OpenAIProvider`** (`AI_PROVIDER=openai` + `OPENAI_API_KEY`): calls
  `POST https://api.openai.com/v1/chat/completions`, with a system prompt
  that restricts it to the facts supplied and forbids inventing numbers.

The AI **only explains and classifies** what the deterministic engine
already decided — it never decides whether records match, and never
silently marks anything resolved.

## 8. Finance Q&A

`POST /api/ai/query` answers grounded questions using live data — try:
"What is our current cash position?", "How many transactions failed
reconciliation?", "Why is settlement lower than expected?", "Which
merchants have the highest reconciliation exceptions?", "What is the
expected cash position tomorrow?". See the "AI Finance Assistant" page
in the UI for the full suggested-question list.

## 9. Cash position & forecast

See `backend/cash.py` for the fully documented, simplified demo
accounting assumptions (opening cash constant, inflows = successful
payments, outflows = settlements + fees + tax). The forecast uses a
transparent moving-average model over 1/3/7-day horizons with confidence
that decreases with horizon length — methodology is shown in the UI, not
hidden.

---

## 10. Known unresolved exceptions
The demo intentionally creates unresolved exceptions covering issues that require real human intervention: missing settlements from the bank, unknown transactions that never reached the payment layer, partial settlements, massive reference/status mismatch, etc.

## 11. Razorpay Test Mode integration
FinRecon AI features a secure backend-only validation for Razorpay keys restricted specifically to Test Mode logic (checking the `rzp_test_` prefix). If credentials are authenticated, they are used strictly offline.

## 12. Environment variables
- `RAZORPAY_KEY_ID`: Razorpay Test Mode Key IF (must start with `rzp_test_`)
- `RAZORPAY_KEY_SECRET`: Razorpay Test Mode Secret
- `AI_PROVIDER`: `mock` (default) or `openai`
- `OPENAI_API_KEY`: Required only if `openai` provider is used.
- `OPENAI_MODEL`: Model name (default `gpt-4o-mini`)

## 13. Local setup

### Requirements
- Python 3.9+ (Flask is the only pip dependency; everything else is
  stdlib)
- A modern browser (for Chart.js, loaded from a CDN — this needs internet
  access in *your* browser, not on the machine running the server)

### Start (Linux/Mac)
```bash
./start.sh
```
### Start (Windows)
```
start.bat
```
### Or directly
```bash
cd backend
pip install -r requirements.txt
python3 app.py
```
Then open **http://localhost:8080**

Health check: **http://localhost:8080/api/health**

The database auto-seeds and auto-reconciles on first run — the dashboard
is populated immediately, no manual steps needed.

### Automated quality check
```bash
./verify.sh
```
Compiles every backend module, runs the full test suite, checks frontend
JS syntax, boots the server, and hits every core endpoint.

## 14. Demo instructions
To reset the demo to its ground-truth standard state, click **"Reset Demo"** in the UI, or:
Click **"Reset Demo"** in the UI, or:
```bash
curl -X POST http://localhost:8080/api/demo/reset
```

---

## 15. API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health + seed status |
| GET | `/api/dashboard/summary` | All headline metrics |
| POST | `/api/reconciliation/run` | Re-seed + re-run the full pipeline (Demo Mode) |
| GET | `/api/reconciliations` | List, filterable by `status`, `exceptionType`, `merchantId`, `search` |
| GET | `/api/reconciliations/{id}` | Full detail incl. payment/settlement/ledger/exceptions |
| GET | `/api/exceptions` | List, filterable by `status`, `severity` |
| GET | `/api/exceptions/{id}` | Detail |
| POST | `/api/exceptions/{id}/resolve` | Mark resolved (audited) |
| POST | `/api/exceptions/{id}/escalate` | Escalate (audited) |
| POST | `/api/exceptions/{id}/ignore` | Ignore (audited) |
| POST | `/api/exceptions/{id}/mark-expected` | Mark expected (audited) |
| GET | `/api/settlements` | All settlement records |
| GET | `/api/cash-position` | Live cash position |
| GET | `/api/cash-forecast` | 1/3/7-day forecast |
| GET | `/api/merchants` | Per-merchant analytics |
| GET | `/api/analytics/exceptions` | Exception counts/value by type |
| POST | `/api/ai/analyze-exception` | Returns the stored AI explanation for one exception |
| POST | `/api/ai/query` | Finance Q&A |
| POST | `/api/demo/reset` | Wipe + reseed + re-reconcile |
| GET | `/api/audit-logs` | Full audit trail |

All errors return structured JSON: `{timestamp, status, error, message, path}`.

---

## 12. Testing

`backend/tests/test_reconciliation.py` — **20 tests, all passing** (see
output below), covering: exact match, amount mismatch, missing
settlement, duplicate transaction, fee mismatch, tax mismatch, partial
settlement, unknown transaction, cash calculation, forecast calculation,
exception resolution workflow, AI grounding (explanations always mention
the actual transaction ID), and the integration-level checks required by
the brief (≥100 records seeded, matched+auto_resolved+unresolved ==
processed, match rate in [0,100], unresolved exceptions exist, metrics
computed from the database rather than hardcoded).

```
Ran 20 tests in 0.024s
OK
```

## 16. Limitations

- **Not the Java/Spring/React/Postgres/Docker stack originally specified**
  — see "Why not the originally-specified stack" above. This is a
  functional substitute built and verified in an environment with no
  network access; porting notes are provided.
- **SQLite, not PostgreSQL** — fine for a single-process demo; a real
  deployment should use the Postgres schema translation notes above.
- **No authentication is enforced** — demo credentials are shown in
  Settings but not checked against any login flow, per the brief's
  request not to over-engineer auth for the demo.
- **Cash position model is intentionally simplified** — clearly labelled
  as such in the UI and in `cash.py`; not GAAP-complete accounting.
- **OpenAI provider is untested against a live API key** in this
  environment (no network access) — the mock provider is fully tested and
  is the default; the OpenAI code path follows the same interface and
  should work with a valid key, but that specific path was not exercised
  end-to-end here.
- **Single Flask dev server** — fine for a demo; a production deployment
  should sit behind a WSGI server (gunicorn) and a reverse proxy.

## 18. Security notes
- Secrets are never committed (`.env` is gitignored).
- Razorpay and OpenAI integrations operate 100% backend-side.
- No keys are exposed in the frontend or REST API payloads.
- Test mode is strictly enforced for real keys.
- No database credentials exist (SQLite runs locally mode).

## Future improvements

- Port to the originally-specified Spring Boot + React + PostgreSQL +
  Docker stack (this codebase is structured to make that port
  mechanical — see the table in "Architecture").
- Multi-currency support.
- Real bank statement (MT940/CAMT.053) ingestion.
- Configurable tolerance bands per merchant/payment method.
- Role-based access control and real authentication.
