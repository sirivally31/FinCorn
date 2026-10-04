"""
FinRecon AI - Backend entrypoint.
Serves both the REST API and the static frontend on a single port so the
whole app starts with one command: `python3 app.py`.
"""
import csv
import hmac
import io
import math
import os
import sqlite3
import datetime
import base64
import urllib.request
import urllib.error
from flask import Flask, jsonify, redirect, request, send_from_directory

from database import init_db, get_connection
import seed
import reconciliation
import cash
from ai_provider import get_provider

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
AI = get_provider()

CSV_SOURCES = {
    "payments": {
        "table": "payments",
        "columns": ("transaction_id", "payment_id", "merchant_id", "customer_id", "upi_id",
                    "amount", "currency", "payment_method", "status", "transaction_timestamp",
                    "settlement_date", "gateway_reference", "bank_reference", "fee", "tax",
                    "net_amount"),
        "required": ("transaction_id", "payment_id", "amount", "fee", "tax", "status",
                     "transaction_timestamp", "bank_reference"),
        "numbers": ("amount", "fee", "tax", "net_amount"),
        "key": "transaction_id",
    },
    "settlements": {
        "table": "settlements",
        "columns": ("settlement_id", "transaction_id", "merchant_id", "settlement_reference",
                    "gross_amount", "fee", "tax", "net_amount", "settlement_date",
                    "settlement_status", "bank_reference"),
        "required": ("settlement_id", "transaction_id", "gross_amount", "fee", "tax",
                     "net_amount", "settlement_date", "settlement_status", "bank_reference"),
        "numbers": ("gross_amount", "fee", "tax", "net_amount"),
        "key": "settlement_id",
    },
    "ledger": {
        "table": "ledger_entries",
        "columns": ("ledger_id", "transaction_id", "merchant_id", "debit", "credit",
                    "ledger_amount", "tax_amount", "fee_amount", "entry_date",
                    "ledger_status", "reference"),
        "required": ("ledger_id", "transaction_id", "ledger_amount"),
        "numbers": ("debit", "credit", "ledger_amount", "tax_amount", "fee_amount"),
        "key": "ledger_id",
    },
}


def error_response(status, message):
    return jsonify({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": status,
        "error": {400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}.get(status, "Error"),
        "message": message,
        "path": request.path,
    }), status


@app.before_request
def protect_financial_data():
    if request.path == "/api/health":
        return None

    username = os.environ.get("APP_USERNAME")
    password = os.environ.get("APP_PASSWORD")
    if bool(username) != bool(password):
        return error_response(503, "Configure both APP_USERNAME and APP_PASSWORD, or remove both.")
    if not username or not password:
        if request.path == "/api/import":
            return error_response(503, "CSV import requires authentication and persistent storage configuration.")
        return None

    credentials = request.authorization
    if credentials and hmac.compare_digest(credentials.username or "", username) \
            and hmac.compare_digest(credentials.password or "", password):
        return None

    response, status = error_response(401, "Authentication required")
    response.headers["WWW-Authenticate"] = 'Basic realm="FinRecon AI"'
    return response, status


def _read_csv_upload(upload, source):
    config = CSV_SOURCES[source]
    try:
        content = upload.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{source}: file must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError(f"{source}: CSV needs a header row")
    headers = [header.strip().lower().replace(" ", "_") for header in reader.fieldnames]
    if len(headers) != len(set(headers)):
        raise ValueError(f"{source}: duplicate column names are not allowed")
    missing = sorted(set(config["required"]) - set(headers))
    if missing:
        raise ValueError(f"{source}: missing required columns: {', '.join(missing)}")

    rows = []
    seen_keys = set()
    for row_number, values in enumerate(reader, start=2):
        row = {headers[index]: (value.strip() if value else None)
               for index, value in enumerate(values.values()) if index < len(headers)}
        if not any(row.values()):
            continue

        for column in config["required"]:
            if not row.get(column):
                raise ValueError(f"{source}: row {row_number} is missing {column}")
        for column in config["numbers"]:
            value = row.get(column)
            if value is None:
                row[column] = None
                continue
            try:
                parsed = float(value)
            except ValueError as exc:
                raise ValueError(f"{source}: row {row_number} has invalid {column}") from exc
            if not math.isfinite(parsed):
                raise ValueError(f"{source}: row {row_number} has invalid {column}")
            row[column] = parsed

        for column in ("transaction_timestamp", "settlement_date", "entry_date"):
            value = row.get(column)
            if value:
                try:
                    datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(f"{source}: row {row_number} has invalid {column}; use ISO 8601") from exc

        key = row[config["key"]]
        if key in seen_keys:
            raise ValueError(f"{source}: duplicate {config['key']} {key} in CSV")
        seen_keys.add(key)
        if source == "payments":
            row.setdefault("currency", "INR")
            row.setdefault("payment_method", "UNKNOWN")
        if source == "settlements":
            row["settlement_status"] = row["settlement_status"].upper()
        if source == "payments":
            row["status"] = row["status"].upper()
        rows.append(tuple(row.get(column) for column in config["columns"]))

    if source == "payments" and not rows:
        raise ValueError("payments: include at least one payment record")
    return rows


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return error_response(404, "Resource not found")
    return redirect("/app")


@app.errorhandler(500)
def server_error(e):
    return error_response(500, str(e))


# ---------------------------------------------------------------- Frontend
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "landing.html")


@app.route("/app")
@app.route("/app/<path:anything>")
def dashboard(anything=None):
    return send_from_directory(FRONTEND_DIR, "index.html")


# ---------------------------------------------------------------- Health
_RAZORPAY_STATUS = None

def _check_razorpay():
    global _RAZORPAY_STATUS
    if _RAZORPAY_STATUS is not None:
        return _RAZORPAY_STATUS
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        _RAZORPAY_STATUS = "Not Configured"
        return _RAZORPAY_STATUS
        
    if not key_id.startswith("rzp_test_"):
        _RAZORPAY_STATUS = "Invalid Key Type (Test Mode Required)"
        return _RAZORPAY_STATUS
        
    auth_str = f"{key_id}:{key_secret}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    req = urllib.request.Request("https://api.razorpay.com/v1/payments")
    req.add_header("Authorization", f"Basic {b64_auth}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            # Razorpay returns 200 for valid credentials
            _RAZORPAY_STATUS = "Connected (Test Mode)"
    except urllib.error.HTTPError as e:
        _RAZORPAY_STATUS = f"Invalid Credentials (HTTP {e.code})"
    except Exception as e:
        _RAZORPAY_STATUS = "Connection Failed"
    return _RAZORPAY_STATUS

@app.route("/api/health")
def health():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) c FROM payments").fetchone()["c"]
    conn.close()
    return jsonify({"status": "UP", "recordsLoaded": n, "recordsSeeded": n,
                     "aiProvider": os.environ.get("AI_PROVIDER", "mock"),
                     "razorpayStatus": _check_razorpay(),
                     "time": datetime.datetime.now(datetime.timezone.utc).isoformat()})


# ---------------------------------------------------------------- Dashboard
@app.route("/api/dashboard/summary")
def dashboard_summary():
    summary = reconciliation.compute_summary()
    cp = cash.compute_cash_position()
    fc = cash.compute_forecast()
    summary["currentCash"] = cp["currentCashPosition"]
    summary["pendingSettlements"] = cp["pendingSettlementAmount"]
    summary["forecastedCash7d"] = fc[-1]["projectedBalance"] if fc else None
    return jsonify(summary)


# ---------------------------------------------------------------- Reconciliation
@app.route("/api/reconciliation/run", methods=["POST"])
def run_reconciliation():
    steps = []
    init_db(reset=False)
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    conn.close()
    if not n:
        return error_response(400, "No payment records are loaded. Import CSV data before reconciling.")
    steps.append(f"{n} existing payments found")
    steps.append("Existing settlements and ledger records retained")
    summary = reconciliation.run_reconciliation(ai_provider=AI)
    steps.append("Records matched")
    steps.append("Exceptions classified")
    steps.append("AI analysis completed")
    cp = cash.compute_cash_position()
    steps.append("Cash position calculated")
    fc = cash.compute_forecast()
    steps.append("Forecast generated")
    return jsonify({"steps": steps, "summary": summary, "cashPosition": cp, "forecast": fc})


@app.route("/api/import", methods=["POST"])
def import_records():
    if os.environ.get("FINRECON_ALLOW_IMPORT", "").lower() != "true":
        return error_response(503, "Set FINRECON_ALLOW_IMPORT=true to explicitly enable CSV imports.")
    if not os.environ.get("FINRECON_DB_PATH"):
        return error_response(503, "Set FINRECON_DB_PATH to a persistent database location before importing.")

    try:
        imported = {}
        for source in CSV_SOURCES:
            upload = request.files.get(source)
            if upload is None or not upload.filename:
                raise ValueError(f"Select a {source} CSV file")
            imported[source] = _read_csv_upload(upload, source)
    except ValueError as exc:
        return error_response(400, str(exc))

    init_db(reset=False)
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for table in ("reconciliations", "exceptions", "audit_logs", "cash_snapshots",
                      "forecast_records", "settlements", "ledger_entries", "payments", "merchants"):
            conn.execute(f"DELETE FROM {table}")

        for source, rows in imported.items():
            config = CSV_SOURCES[source]
            columns = config["columns"]
            placeholders = ",".join("?" for _ in columns)
            conn.executemany(
                f"INSERT INTO {config['table']} ({','.join(columns)}) VALUES ({placeholders})",
                rows,
            )

        merchant_ids = sorted({row[2] for row in imported["payments"] if row[2]})
        conn.executemany(
            "INSERT INTO merchants (merchant_id, name, category) VALUES (?, ?, ?)",
            [(merchant_id, merchant_id, "Imported") for merchant_id in merchant_ids],
        )
        conn.commit()
    except (sqlite3.Error, ValueError) as exc:
        conn.rollback()
        conn.close()
        return error_response(400, f"Import rejected; existing records were preserved: {exc}")
    conn.close()

    summary = reconciliation.run_reconciliation(ai_provider=AI)
    forecast = cash.compute_forecast()
    return jsonify({
        "message": "Imported records and completed reconciliation.",
        "counts": {source: len(rows) for source, rows in imported.items()},
        "summary": summary,
        "forecast": forecast,
    }), 201


@app.route("/api/reconciliations")
def list_reconciliations():
    status = request.args.get("status")
    exception_type = request.args.get("exceptionType")
    merchant_id = request.args.get("merchantId")
    search = request.args.get("search")

    q = """SELECT r.*, p.merchant_id as merchant_id FROM reconciliations r
           LEFT JOIN payments p ON p.transaction_id = r.transaction_id WHERE 1=1"""
    params = []
    if status:
        q += " AND r.match_status = ?"
        params.append(status)
    if exception_type:
        q += " AND r.exception_type = ?"
        params.append(exception_type)
    if merchant_id:
        q += " AND p.merchant_id = ?"
        params.append(merchant_id)
    if search:
        q += " AND r.transaction_id LIKE ?"
        params.append(f"%{search}%")
    q += " ORDER BY r.reconciliation_id"

    conn = get_connection()
    rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    return jsonify({"count": len(rows), "results": rows})


@app.route("/api/reconciliations/<rid>")
def get_reconciliation(rid):
    conn = get_connection()
    row = conn.execute("SELECT * FROM reconciliations WHERE reconciliation_id = ?", (rid,)).fetchone()
    if not row:
        conn.close()
        return error_response(404, f"Reconciliation {rid} not found")
    txn_id = row["transaction_id"]
    payment = conn.execute("SELECT * FROM payments WHERE transaction_id = ?", (txn_id,)).fetchone()
    settlements = conn.execute("SELECT * FROM settlements WHERE transaction_id = ?", (txn_id,)).fetchall()
    ledgers = conn.execute("SELECT * FROM ledger_entries WHERE transaction_id = ?", (txn_id,)).fetchall()
    exceptions = conn.execute("SELECT * FROM exceptions WHERE transaction_id = ?", (txn_id,)).fetchall()
    conn.close()
    return jsonify({
        "reconciliation": dict(row),
        "payment": dict(payment) if payment else None,
        "settlements": [dict(s) for s in settlements],
        "ledgerEntries": [dict(l) for l in ledgers],
        "exceptions": [dict(e) for e in exceptions],
    })


# ---------------------------------------------------------------- Exceptions
@app.route("/api/exceptions")
def list_exceptions():
    status = request.args.get("status")
    severity = request.args.get("severity")
    q = "SELECT * FROM exceptions WHERE 1=1"
    params = []
    if status:
        q += " AND status = ?"
        params.append(status)
    if severity:
        q += " AND severity = ?"
        params.append(severity)
    q += " ORDER BY created_at DESC"
    conn = get_connection()
    rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    return jsonify({"count": len(rows), "results": rows})


@app.route("/api/exceptions/<eid>")
def get_exception(eid):
    conn = get_connection()
    row = conn.execute("SELECT * FROM exceptions WHERE exception_id = ?", (eid,)).fetchone()
    conn.close()
    if not row:
        return error_response(404, f"Exception {eid} not found")
    return jsonify(dict(row))


def _update_exception_status(eid, new_status, reason):
    conn = get_connection()
    row = conn.execute("SELECT * FROM exceptions WHERE exception_id = ?", (eid,)).fetchone()
    if not row:
        conn.close()
        return None
    old_status = row["status"]
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute("""UPDATE exceptions SET status = ?, resolved_at = ?, resolution_reason = ?
                     WHERE exception_id = ?""", (new_status, now, reason, eid))
    conn.execute("""INSERT INTO audit_logs (action, actor, transaction_id, old_status,
        new_status, reason, timestamp) VALUES (?,?,?,?,?,?,?)""",
        (new_status, "USER", row["transaction_id"], old_status, new_status, reason, now))
    conn.commit()
    updated = conn.execute("SELECT * FROM exceptions WHERE exception_id = ?", (eid,)).fetchone()
    conn.close()
    return dict(updated)


@app.route("/api/exceptions/<eid>/resolve", methods=["POST"])
def resolve_exception(eid):
    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "Manually resolved by finance operations user.")
    result = _update_exception_status(eid, "RESOLVED", reason)
    if result is None:
        return error_response(404, f"Exception {eid} not found")
    return jsonify(result)


@app.route("/api/exceptions/<eid>/escalate", methods=["POST"])
def escalate_exception(eid):
    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "Escalated for senior finance review.")
    result = _update_exception_status(eid, "ESCALATED", reason)
    if result is None:
        return error_response(404, f"Exception {eid} not found")
    return jsonify(result)


@app.route("/api/exceptions/<eid>/ignore", methods=["POST"])
def ignore_exception(eid):
    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "Ignored - not material.")
    result = _update_exception_status(eid, "IGNORED", reason)
    if result is None:
        return error_response(404, f"Exception {eid} not found")
    return jsonify(result)


@app.route("/api/exceptions/<eid>/mark-expected", methods=["POST"])
def mark_expected_exception(eid):
    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "Marked as expected business behaviour.")
    result = _update_exception_status(eid, "EXPECTED", reason)
    if result is None:
        return error_response(404, f"Exception {eid} not found")
    return jsonify(result)


# ---------------------------------------------------------------- Settlements
@app.route("/api/settlements")
def list_settlements():
    conn = get_connection()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM settlements ORDER BY settlement_id").fetchall()]
    conn.close()
    return jsonify({"count": len(rows), "results": rows})


# ---------------------------------------------------------------- Cash & forecast
@app.route("/api/cash-position")
def cash_position():
    return jsonify(cash.compute_cash_position())


@app.route("/api/cash-forecast")
def cash_forecast():
    return jsonify({"forecast": cash.compute_forecast()})


# ---------------------------------------------------------------- Merchants
@app.route("/api/merchants")
def list_merchants():
    conn = get_connection()
    merchants = conn.execute("SELECT * FROM merchants").fetchall()
    result = []
    for m in merchants:
        txns = conn.execute("SELECT COUNT(*) c FROM payments WHERE merchant_id = ?",
                             (m["merchant_id"],)).fetchone()["c"]
        settled = conn.execute("""SELECT COALESCE(SUM(net_amount),0) v FROM settlements
            WHERE merchant_id = ? AND settlement_status IN ('SETTLED','PARTIALLY_SETTLED')""",
            (m["merchant_id"],)).fetchone()["v"]
        exc = conn.execute("""SELECT COUNT(*) c, COALESCE(SUM(amount),0) v FROM exceptions
            WHERE transaction_id IN (SELECT transaction_id FROM payments WHERE merchant_id = ?)
            AND status = 'OPEN'""", (m["merchant_id"],)).fetchone()
        result.append({
            "merchantId": m["merchant_id"], "name": m["name"], "category": m["category"],
            "transactionCount": txns, "settledAmount": round(settled, 2),
            "exceptionCount": exc["c"], "exceptionValue": round(exc["v"], 2),
        })
    conn.close()
    result.sort(key=lambda x: -x["exceptionValue"])
    return jsonify({"count": len(result), "results": result})


# ---------------------------------------------------------------- Analytics
@app.route("/api/analytics/exceptions")
def analytics_exceptions():
    conn = get_connection()
    rows = conn.execute("""SELECT exception_type, COUNT(*) count, COALESCE(SUM(amount),0) value
        FROM exceptions WHERE status='OPEN' GROUP BY exception_type
        ORDER BY count DESC""").fetchall()
    conn.close()
    return jsonify({"results": [dict(r) for r in rows]})


# ---------------------------------------------------------------- AI
@app.route("/api/ai/analyze-exception", methods=["POST"])
def ai_analyze_exception():
    body = request.get_json(silent=True) or {}
    eid = body.get("exceptionId")
    conn = get_connection()
    row = conn.execute("SELECT * FROM exceptions WHERE exception_id = ?", (eid,)).fetchone()
    conn.close()
    if not row:
        return error_response(404, f"Exception {eid} not found")
    return jsonify({"exceptionId": eid, "explanation": row["ai_explanation"],
                     "recommendedAction": row["recommended_action"],
                     "severity": row["severity"], "rootCause": row["root_cause"]})


def _build_query_context():
    summary = reconciliation.compute_summary()
    conn = get_connection()
    top_exceptions = [dict(r) for r in conn.execute(
        """SELECT exception_type, COUNT(*) count, COALESCE(SUM(amount),0) value
           FROM exceptions WHERE status='OPEN' GROUP BY exception_type
           ORDER BY count DESC""").fetchall()]
    top_merchants_raw = conn.execute("SELECT merchant_id, name FROM merchants").fetchall()
    top_merchants = []
    for m in top_merchants_raw:
        r = conn.execute("""SELECT COUNT(*) c, COALESCE(SUM(amount),0) v FROM exceptions
            WHERE transaction_id IN (SELECT transaction_id FROM payments WHERE merchant_id=?)
            AND status='OPEN'""", (m["merchant_id"],)).fetchone()
        if r["c"] > 0:
            top_merchants.append({"name": m["name"], "count": r["c"], "value": round(r["v"], 2)})
    top_merchants.sort(key=lambda x: -x["count"])
    delay_count = conn.execute(
        "SELECT COUNT(*) c FROM reconciliations WHERE exception_type='SETTLEMENT_DELAY'").fetchone()["c"]
    tax_mismatch_count = conn.execute(
        "SELECT COUNT(*) c FROM reconciliations WHERE exception_type='TAX_MISMATCH'").fetchone()["c"]
    conn.close()

    cp = cash.compute_cash_position()
    fc = cash.compute_forecast()
    return {
        "summary": summary,
        "top_exceptions": top_exceptions,
        "top_merchants": top_merchants,
        "delay_count": delay_count,
        "tax_mismatch_count": tax_mismatch_count,
        "date_tolerance_hours": reconciliation.TOLERANCE_DATE_HOURS,
        "cash_position": cp,
        "forecast_horizons": fc,
        "forecast_1d": next((f for f in fc if f["horizonDays"] == 1), None),
        "forecast_7d": next((f for f in fc if f["horizonDays"] == 7), None),
    }


@app.route("/api/ai/query", methods=["POST"])
def ai_query():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    if not question:
        return error_response(400, "question is required")
    context = _build_query_context()
    answer = AI.answer_query(question, context)
    return jsonify({"question": question, "answer": answer})


# ---------------------------------------------------------------- Demo controls
@app.route("/api/demo/reset", methods=["POST"])
def demo_reset():
    if os.environ.get("FINRECON_ALLOW_IMPORT", "").lower() == "true":
        return error_response(410, "Demo reset is disabled while CSV imports are enabled.")
    init_db(reset=True)
    n = seed.generate_and_load()
    summary = reconciliation.run_reconciliation(ai_provider=AI)
    cash.compute_forecast()
    return jsonify({"message": f"Demo data reset and reconciliation re-run over {n} records.",
                     "summary": summary})


# ---------------------------------------------------------------- Audit
@app.route("/api/audit-logs")
def audit_logs():
    conn = get_connection()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM audit_logs ORDER BY id DESC LIMIT 200").fetchall()]
    conn.close()
    return jsonify({"count": len(rows), "results": rows})


def bootstrap():
    """Auto-seed + auto-reconcile on first run so the dashboard is never empty."""
    init_db(reset=False)
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) c FROM payments").fetchone()["c"]
    conn.close()
    if n == 0:
        seed.generate_and_load()
        reconciliation.run_reconciliation(ai_provider=AI)
        cash.compute_forecast()


if __name__ == "__main__":
    bootstrap()
    port = int(os.environ.get("PORT", 8080))
    print(f"FinRecon AI backend running: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
