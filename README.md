# FinRecon AI

**Autonomous reconciliation and cash intelligence for payment operations.**

FinRecon AI compares payment, settlement, and ledger records, identifies discrepancies, and gives finance teams a reviewable exception queue and cash outlook. It analyzes records; it does not initiate payments or move money.

> The public deployment currently uses synthetic data. Do not upload private or customer financial data to the free Render instance.

## Live Demo

- Landing page: [finrecon-ai-aya7.onrender.com](https://finrecon-ai-aya7.onrender.com)
- Dashboard: [finrecon-ai-aya7.onrender.com/app](https://finrecon-ai-aya7.onrender.com/app)
- Health: [finrecon-ai-aya7.onrender.com/api/health](https://finrecon-ai-aya7.onrender.com/api/health)

Render's free instance can sleep when idle and uses ephemeral storage. Its SQLite data can be lost on restart or redeploy.

## How It Works

1. Load payment, settlement, and ledger records. The app seeds reproducible synthetic records on a fresh database; validated CSV replacement imports are also supported when explicitly configured.
2. Run deterministic reconciliation using amount, fee, tax, date, reference, and status rules.
3. Keep material or ambiguous discrepancies in a human-review queue. Only defined tolerance cases can be auto-resolved.
4. Use grounded AI explanations to understand detected exceptions. AI does not decide matches or resolve records.
5. Review the calculated cash position, moving-average forecast, and audited exception actions.

**Refresh Current View** re-reads the active database view. **Run Reconciliation** recalculates results from stored source records without deleting or reseeding them. **Import CSV Data** replaces the active dataset after validating all three CSV files.

## Technology

- **Python 3, Flask:** REST API and static-file server.
- **SQLite:** simple local persistence for the single-process demo.
- **HTML, CSS, vanilla JavaScript:** dashboard and landing page without a frontend build step.
- **Gunicorn:** production WSGI server used by Render.
- **unittest:** deterministic reconciliation and import-workflow tests.
- **Render:** deployment from the repository's `main` branch using `render.yaml`.

This lightweight stack keeps the demo easy to run and verify. SQLite and the free Render configuration are not the recommended foundation for private production financial records. See [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) for stack trade-offs, architecture, limitations, and interview-ready explanations.

## Run Locally

Requirements: Python 3.9+.

Windows:

```powershell
.\start.bat
```

macOS/Linux:

```sh
./start.sh
```

Then open `http://localhost:8080`. To install dependencies and run the backend tests:

```sh
cd backend
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The latest verified suite contains **27 passing tests**.

## CSV Imports and Data Safety

The importer expects one CSV each for payments, settlements, and ledger entries. Required headers are shown in the dashboard's **Import CSV Data** dialog. Import validates all files before replacing the active dataset; malformed input leaves the existing dataset intact.

Imports are disabled unless the server has all of the following configured:

- `APP_USERNAME` and `APP_PASSWORD` to enable HTTP Basic Auth for dashboard and API routes.
- `FINRECON_ALLOW_IMPORT=true` as explicit import opt-in.
- `FINRECON_DB_PATH` pointing to a persistent SQLite file.

The current public free Render service has ephemeral storage and is not suitable for confidential financial records. Do not enable imports there. A persistent private deployment needs durable storage, restricted access, backups, and operational controls before loading sensitive data.

Optional settings:

- `OPENING_CASH`: opening balance for cash calculations; defaults to `0`.
- `AI_PROVIDER`: `mock` by default, or `openai`.
- `OPENAI_API_KEY` and `OPENAI_MODEL`: server-side configuration for the optional OpenAI explanation provider.
- `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`: optional Test Mode connectivity check only; they do not import records or execute payments.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health and loaded payment count |
| `GET` | `/api/dashboard/summary` | Dashboard reconciliation and cash metrics |
| `POST` | `/api/reconciliation/run` | Reconcile records currently stored |
| `POST` | `/api/import` | Validated replacement import; requires explicit secure configuration |
| `GET` | `/api/reconciliations` | List and filter reconciliation results |
| `GET` | `/api/exceptions` | Review discrepancy queue |
| `GET` | `/api/cash-position` | Current calculated cash position |
| `GET` | `/api/cash-forecast` | 1-, 3-, and 7-day forecast |
| `GET` | `/api/audit-logs` | Exception action history |

## Synthetic Evaluation Snapshot

The reproducible synthetic dataset contains 150 seeded payments, an injected duplicate, and an orphan settlement. In the latest documented evaluation it produced 152 processed records, 123 matched, 8 auto-resolved, and 21 unresolved, for an 86.18% match rate. These are evaluation results, not live financial account metrics. With `OPENING_CASH` unset, the sample's calculated current cash is ₹1,10,071.20 and the seven-day projection is ₹2,10,263.93.

Run `POST /api/demo/reset` only to regenerate the local synthetic evaluation dataset. The dashboard intentionally has no destructive reset button.

## Project and Interview Guide

See [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) for the problem statement, data flow, technology rationale and trade-offs, differentiators, current deployment condition, interview pitches, common questions, and resume bullet.
