# FinRecon AI: A Practical Project Guide

FinRecon AI compares payment, settlement, and ledger records and highlights discrepancies for review. It does not initiate or move money. It can work with operator-provided CSV exports; it is not a live bank feed.

## What happens when it runs

The app is one small Flask service. It serves the web dashboard and its API, while SQLite stores the records on disk. On a fresh start, the app creates a repeatable set of synthetic payment data and runs the reconciliation process so the dashboard has something to show.

The reconciliation rules compare payment, settlement, and ledger amounts and references. Small differences may be auto-resolved within configured tolerances; larger or ambiguous differences remain visible as exceptions. The AI provider can explain those findings, but it does not decide whether two financial records match.

The dashboard checks the currently open data view every 10 seconds. **Refresh Current View** reloads the selected view from the active database. **Run Reconciliation** recomputes matches from the currently stored records; it does not delete or recreate source records. **Import CSV Data** replaces the active dataset after validating payment, settlement, and ledger CSV files.

## Start the app

On Windows, open PowerShell in the project folder and run:

```powershell
.\start.bat
```

On macOS or Linux, run:

```sh
./start.sh
```

The dashboard is served at `http://localhost:8080`. The backend can also be started directly after installing its single dependency:

```sh
cd backend
python -m pip install -r requirements.txt
python app.py
```

The first run creates `data/finrecon.db` and seeds synthetic data for evaluation. CSV imports are disabled by default. Before importing financial records, set `APP_USERNAME`, `APP_PASSWORD`, `FINRECON_ALLOW_IMPORT=true`, and `FINRECON_DB_PATH` to a persistent database file. Configuring both credentials enables HTTP Basic Auth for the dashboard and API. `OPENING_CASH` configures the opening balance and defaults to zero.

## Deploy on Render

The repository includes a Render Blueprint in `render.yaml`. To deploy, open the Render dashboard, create a new **Blueprint** from `sirivally31/FinCorn`, and select the `main` branch. Render installs `backend/requirements.txt`, starts the app with Gunicorn, and checks `/api/health`.

The included service uses Render's free plan and SQLite on its temporary filesystem. It is only suitable for synthetic/public demo data. Do not enable imports or upload private financial records there: records can be lost on restart, and data must not be exposed publicly. To enable imports, use a private service with authentication configured and persistent storage (a paid Render disk mounted at `/var/data`, setting `FINRECON_DB_PATH=/var/data/finrecon.db`, or a production database adapter). Set `APP_USERNAME`, `APP_PASSWORD`, and `FINRECON_ALLOW_IMPORT=true` in Render's environment settings. Keep credentials out of Git and `render.yaml`.

## A normal walkthrough

1. Open the dashboard and review the reconciliation, cash, and exception totals.
2. Open **Reconciliation** to filter records and inspect the payment, settlement, and ledger details behind a result.
3. Open **Exceptions** to read the explanation and recommended action. Resolve, escalate, ignore, and expected-status actions are written to the audit log.
4. Review **Cash Position** and **Forecast** for the configured opening cash balance and transparent moving-average projection.
5. Use **AI Finance Assistant** to ask questions about the current dataset. The default mock provider works offline; the optional OpenAI provider requires server-side configuration.

## Main pieces

- `backend/app.py` serves the API and web files.
- `backend/database.py` creates and connects to the SQLite database.
- `backend/seed.py` creates the deterministic synthetic records.
- `backend/reconciliation.py` applies matching and exception rules.
- `backend/cash.py` calculates the demo cash position and forecast.
- `backend/ai_provider.py` contains the mock and optional OpenAI explanation providers.
- `frontend/` contains the HTML, CSS, and browser JavaScript; no frontend build step is needed.
- `backend/tests/` contains the reconciliation tests.

## Check the project

Run the backend tests from the backend directory:

```sh
cd backend
python -m unittest tests.test_reconciliation -v
```

The API health endpoint is `http://localhost:8080/api/health`. Other useful endpoints include `/api/dashboard/summary`, `/api/reconciliations`, `/api/exceptions`, `/api/cash-position`, and `/api/cash-forecast`. CSV import posts `payments`, `settlements`, and `ledger` CSV files to `/api/import`; it is disabled unless explicitly enabled with authentication and persistent storage configured.

## Before using real financial data

This build is designed for demonstration and evaluation with synthetic records. It has no enforced user login, and its SQLite setup and Flask development server are intended for local use. Do not put production credentials or real customer records into this demo. A production deployment needs authentication and authorization, secret management, a production WSGI server, backups and migrations, monitoring, and secure, tested integrations with the actual payment and banking systems.

The AI integration is optional. `AI_PROVIDER=mock` is the default. To use the OpenAI provider, configure `AI_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally `OPENAI_MODEL` in the server environment. Keep keys out of the browser and out of source control. Razorpay settings in this build are a test-mode connectivity check, not an automated payment or settlement importer.