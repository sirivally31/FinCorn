"""
FinRecon AI - Deterministic Reconciliation Engine

This module NEVER calls an LLM. Every match/mismatch decision is pure,
rule-based, and reproducible. The AI layer (ai_provider.py) sits on top
and only explains/classifies what this engine already decided.
"""
import datetime
import time
import seed
from database import get_connection

# ---- Configurable tolerances (business rules) ----
TOLERANCE_AMOUNT = 5.0        # INR
TOLERANCE_FEE = 5.0           # INR
TOLERANCE_TAX = 2.0           # INR
TOLERANCE_DATE_HOURS = 48     # hours

AUTO_RESOLVE_FEE_MAX = 50.0       # fee drift auto-resolvable up to this
AUTO_RESOLVE_TAX_MAX = 15.0       # tax drift auto-resolvable up to this
AUTO_RESOLVE_DELAY_DAYS_MAX = 7   # settlement delay auto-resolvable up to this


def _parse(ts):
    return datetime.datetime.fromisoformat(ts)


def _hours_between(a, b):
    return abs((_parse(a) - _parse(b)).total_seconds()) / 3600.0


def _severity_for(exc_type):
    return {
        "AMOUNT_MISMATCH": "HIGH",
        "MISSING_SETTLEMENT": "HIGH",
        "PARTIAL_SETTLEMENT": "HIGH",
        "UNKNOWN_TRANSACTION": "HIGH",
        "STATUS_MISMATCH": "HIGH",
        "LEDGER_MISMATCH": "MEDIUM",
        "REFERENCE_MISMATCH": "MEDIUM",
        "DUPLICATE_RECORD": "MEDIUM",
        "FEE_MISMATCH": "LOW",
        "TAX_MISMATCH": "LOW",
        "SETTLEMENT_DELAY": "LOW",
    }.get(exc_type, "MEDIUM")


def run_reconciliation(ai_provider=None):
    """
    Runs the full deterministic reconciliation pass over every payment
    and every orphan settlement in the database, writes results to the
    `reconciliations` and `exceptions` tables, and returns summary metrics.
    """
    start_time = time.perf_counter()
    
    conn = get_connection()
    cur = conn.cursor()

    # Clear previous run's derived data (idempotent re-run)
    cur.execute("DELETE FROM reconciliations")
    cur.execute("DELETE FROM exceptions")
    cur.execute("DELETE FROM audit_logs WHERE actor = 'SYSTEM'")

    payments = cur.execute("SELECT * FROM payments").fetchall()
    settlements = cur.execute("SELECT * FROM settlements").fetchall()
    ledgers = cur.execute("SELECT * FROM ledger_entries").fetchall()

    settlements_by_txn = {}
    for s in settlements:
        settlements_by_txn.setdefault(s["transaction_id"], []).append(s)

    ledgers_by_txn = {}
    for l in ledgers:
        ledgers_by_txn.setdefault(l["transaction_id"], []).append(l)

    payment_txn_ids = {p["transaction_id"] for p in payments}

    # Track duplicate payment_ids (same payment_id, different transaction_id)
    seen_payment_ids = {}

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    recon_seq = 1
    results = []

    def make_result(txn_id, payment, settlement, ledger, match_status,
                     exception_type, reason, confidence):
        nonlocal recon_seq
        p_amt = payment["amount"] if payment else None
        s_amt = settlement["gross_amount"] if settlement else None
        l_amt = ledger["ledger_amount"] if ledger else None
        diff = None
        diff_pct = None
        if p_amt is not None and s_amt is not None:
            diff = round(p_amt - s_amt, 2)
            diff_pct = round((diff / p_amt) * 100, 2) if p_amt else 0.0

        rid = f"RCN-{6000 + recon_seq}"
        recon_seq += 1
        row = dict(
            reconciliation_id=rid, transaction_id=txn_id,
            payment_id=payment["payment_id"] if payment else None,
            settlement_id=settlement["settlement_id"] if settlement else None,
            ledger_id=ledger["ledger_id"] if ledger else None,
            match_status=match_status, exception_type=exception_type,
            confidence=confidence, payment_amount=p_amt, settlement_amount=s_amt,
            ledger_amount=l_amt, difference_amount=diff, difference_percentage=diff_pct,
            reason=reason, created_at=now,
        )
        cur.execute("""INSERT INTO reconciliations (reconciliation_id, transaction_id,
            payment_id, settlement_id, ledger_id, match_status, exception_type, confidence,
            payment_amount, settlement_amount, ledger_amount, difference_amount,
            difference_percentage, reason, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, txn_id, row["payment_id"], row["settlement_id"], row["ledger_id"],
             match_status, exception_type, confidence, p_amt, s_amt, l_amt, diff,
             diff_pct, reason, now))

        if match_status in ("UNRESOLVED", "AUTO_RESOLVED"):
            if exception_type == "LEDGER_MISMATCH" and ledger and settlement:
                amount_at_risk = abs(round(ledger["ledger_amount"] - settlement["net_amount"], 2))
            elif diff:
                amount_at_risk = abs(diff)
            else:
                amount_at_risk = p_amt or s_amt or 0.0
            severity = _severity_for(exception_type)
            explanation, action = _explain(ai_provider, txn_id, exception_type, payment,
                                            settlement, ledger, diff, reason)
            exc_id = f"EXC-{7000 + recon_seq}"
            exc_status = "AUTO_RESOLVED" if match_status == "AUTO_RESOLVED" else "OPEN"
            resolved_at = now if match_status == "AUTO_RESOLVED" else None
            cur.execute("""INSERT INTO exceptions (exception_id, transaction_id, exception_type,
                severity, amount, root_cause, ai_explanation, recommended_action, status,
                created_at, resolved_at, resolution_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (exc_id, txn_id, exception_type, severity, amount_at_risk, reason,
                 explanation, action, exc_status, now, resolved_at,
                 reason if match_status == "AUTO_RESOLVED" else None))
            if match_status == "AUTO_RESOLVED":
                cur.execute("""INSERT INTO audit_logs (action, actor, transaction_id, old_status,
                    new_status, reason, timestamp) VALUES (?,?,?,?,?,?,?)""",
                    ("AUTO_RESOLVE", "SYSTEM", txn_id, "EXCEPTION", "AUTO_RESOLVED", reason, now))

        results.append(row)
        return row

    # ---- 1. Walk every payment transaction ----
    for p in payments:
        txn_id = p["transaction_id"]
        pay_id = p["payment_id"]

        dup_of = seen_payment_ids.get(pay_id)
        seen_payment_ids[pay_id] = txn_id
        if dup_of is not None:
            make_result(txn_id, p, None, None, "UNRESOLVED", "DUPLICATE_RECORD",
                        f"Transaction {txn_id} shares payment_id {pay_id} with {dup_of}; "
                        f"likely a duplicate submission.", 0.55)
            continue

        s_list = settlements_by_txn.get(txn_id, [])
        l_list = ledgers_by_txn.get(txn_id, [])
        ledger = l_list[0] if l_list else None

        if not s_list:
            make_result(txn_id, p, None, ledger, "UNRESOLVED", "MISSING_SETTLEMENT",
                        f"No settlement record found for {txn_id}. Payment amount "
                        f"₹{p['amount']:.2f} has no matching bank settlement reference.", 0.30)
            continue

        if len(s_list) > 1:
            make_result(txn_id, p, s_list[0], ledger, "UNRESOLVED", "DUPLICATE_RECORD",
                        f"{len(s_list)} settlement records found for single transaction "
                        f"{txn_id}; expected exactly one.", 0.50)
            continue

        s = s_list[0]

        if p["status"] == "SUCCESS" and s["settlement_status"] == "FAILED":
            make_result(txn_id, p, s, ledger, "UNRESOLVED", "STATUS_MISMATCH",
                        f"Payment status is SUCCESS but settlement status is FAILED "
                        f"for {txn_id}.", 0.40)
            continue

        amt_diff = round(p["amount"] - s["gross_amount"], 2)
        fee_diff = round(s["fee"] - p["fee"], 2)
        tax_diff = round(s["tax"] - p["tax"], 2)

        try:
            hrs = _hours_between(p["transaction_timestamp"], s["settlement_date"])
        except Exception:
            hrs = 0.0

        ref_match = (p["bank_reference"] == s["bank_reference"])

        if abs(amt_diff) > (p["amount"] * 0.15):
            make_result(txn_id, p, s, ledger, "UNRESOLVED", "PARTIAL_SETTLEMENT",
                        f"Settlement (₹{s['gross_amount']:.2f}) covers only "
                        f"{100*s['gross_amount']/p['amount']:.0f}% of payment "
                        f"(₹{p['amount']:.2f}) for {txn_id}.", 0.35)
            continue

        if abs(amt_diff) > TOLERANCE_AMOUNT:
            make_result(txn_id, p, s, ledger, "UNRESOLVED", "AMOUNT_MISMATCH",
                        f"Payment amount ₹{p['amount']:.2f} does not match settlement "
                        f"amount ₹{s['gross_amount']:.2f} (diff ₹{amt_diff:.2f}), "
                        f"beyond the ₹{TOLERANCE_AMOUNT:.0f} tolerance.", 0.45)
            continue

        if not ref_match:
            make_result(txn_id, p, s, ledger, "UNRESOLVED", "REFERENCE_MISMATCH",
                        f"Bank reference on payment ({p['bank_reference']}) does not "
                        f"match settlement ({s['bank_reference']}) for {txn_id}.", 0.50)
            continue

        if hrs > TOLERANCE_DATE_HOURS:
            delay_days = hrs / 24.0
            if delay_days <= AUTO_RESOLVE_DELAY_DAYS_MAX:
                make_result(txn_id, p, s, ledger, "AUTO_RESOLVED", "SETTLEMENT_DELAY",
                            f"Settlement for {txn_id} arrived {delay_days:.1f} days after "
                            f"the transaction (beyond the {TOLERANCE_DATE_HOURS}h SLA) but "
                            f"amounts match and the delay is within the "
                            f"{AUTO_RESOLVE_DELAY_DAYS_MAX}-day acceptable settlement window.",
                            0.80)
            else:
                make_result(txn_id, p, s, ledger, "UNRESOLVED", "SETTLEMENT_DELAY",
                            f"Settlement for {txn_id} is delayed {delay_days:.1f} days, "
                            f"beyond the {AUTO_RESOLVE_DELAY_DAYS_MAX}-day auto-resolve window.",
                            0.40)
            continue

        if abs(fee_diff) > TOLERANCE_FEE:
            if abs(fee_diff) <= AUTO_RESOLVE_FEE_MAX:
                make_result(txn_id, p, s, ledger, "AUTO_RESOLVED", "FEE_MISMATCH",
                            f"Settlement fee (₹{s['fee']:.2f}) differs from expected fee "
                            f"(₹{p['fee']:.2f}) by ₹{fee_diff:.2f} for {txn_id}, within the "
                            f"₹{AUTO_RESOLVE_FEE_MAX:.0f} auto-resolve band for processor "
                            f"fee adjustments.", 0.75)
            else:
                make_result(txn_id, p, s, ledger, "UNRESOLVED", "FEE_MISMATCH",
                            f"Settlement fee differs from expected fee by ₹{fee_diff:.2f} "
                            f"for {txn_id}, beyond the auto-resolve band.", 0.40)
            continue

        if abs(tax_diff) > TOLERANCE_TAX:
            if abs(tax_diff) <= AUTO_RESOLVE_TAX_MAX:
                make_result(txn_id, p, s, ledger, "AUTO_RESOLVED", "TAX_MISMATCH",
                            f"Settlement tax (₹{s['tax']:.2f}) differs from expected tax "
                            f"(₹{p['tax']:.2f}) by ₹{tax_diff:.2f} for {txn_id}, within the "
                            f"₹{AUTO_RESOLVE_TAX_MAX:.0f} auto-resolve band for GST rounding.",
                            0.75)
            else:
                make_result(txn_id, p, s, ledger, "UNRESOLVED", "TAX_MISMATCH",
                            f"Settlement tax differs from expected tax by ₹{tax_diff:.2f} "
                            f"for {txn_id}, beyond the auto-resolve band.", 0.40)
            continue

        # Ledger cross-check
        if ledger is not None and abs(round(ledger["ledger_amount"] - s["net_amount"], 2)) > TOLERANCE_AMOUNT:
            make_result(txn_id, p, s, ledger, "UNRESOLVED", "LEDGER_MISMATCH",
                        f"Ledger amount ₹{ledger['ledger_amount']:.2f} does not match "
                        f"settlement net amount ₹{s['net_amount']:.2f} for {txn_id}.", 0.45)
            continue

        # Everything agrees
        make_result(txn_id, p, s, ledger, "MATCHED", None,
                    "Payment, settlement and ledger amounts, fees, tax, references and "
                    "dates all agree within tolerance.", 0.99)

    # ---- 2. Orphan settlements (settlement exists, no matching payment) ----
    for s in settlements:
        if s["transaction_id"] not in payment_txn_ids:
            make_result(s["transaction_id"], None, s, None, "UNRESOLVED", "UNKNOWN_TRANSACTION",
                        f"Settlement {s['settlement_id']} (₹{s['gross_amount']:.2f}) references "
                        f"transaction {s['transaction_id']}, which has no corresponding payment "
                        f"record in the system.", 0.20)

    conn.commit()
    conn.close()
    
    end_time = time.perf_counter()
    processing_time_ms = max(0, round((end_time - start_time) * 1000))
    return compute_summary(processing_time_ms)


def _explain(ai_provider, txn_id, exc_type, payment, settlement, ledger, diff, reason):
    if ai_provider is not None:
        try:
            return ai_provider.explain_exception(txn_id, exc_type, payment, settlement,
                                                  ledger, diff, reason)
        except Exception:
            pass
    # Fallback deterministic explanation (should not normally trigger; ai_provider
    # always supplies at least the mock provider).
    return reason, "Route to finance operations for manual review."


def compute_summary(processing_time_ms=None):
    import evaluation
    conn = get_connection()
    cur = conn.cursor()

    pay_val = cur.execute("SELECT COALESCE(SUM(payment_amount),0) v FROM reconciliations").fetchone()["v"]
    stl_val = cur.execute("SELECT COALESCE(SUM(settlement_amount),0) v FROM reconciliations").fetchone()["v"]
    led_val = cur.execute("SELECT COALESCE(SUM(ledger_amount),0) v FROM reconciliations").fetchone()["v"]
    unresolved_val = cur.execute(
        "SELECT COALESCE(SUM(amount),0) v FROM exceptions WHERE status='OPEN'").fetchone()["v"]
    conn.close()

    eval_metrics = evaluation.run_evaluation()
    total = eval_metrics["totalRecords"]

    eval_metrics["processingTimeMs"] = processing_time_ms
    eval_metrics["throughput"] = round(total / (processing_time_ms / 1000.0), 2) if total and processing_time_ms else 0.0
    eval_metrics["totalPaymentValue"] = round(pay_val, 2)
    eval_metrics["totalSettlementValue"] = round(stl_val, 2)
    eval_metrics["totalLedgerValue"] = round(led_val, 2)
    eval_metrics["settlementDifference"] = round(pay_val - stl_val, 2)
    eval_metrics["unresolvedExceptionValue"] = round(unresolved_val, 2)

    eval_metrics["recordsProcessed"] = total
    eval_metrics["exceptionRecords"] = eval_metrics["unresolvedExceptions"] + eval_metrics["autoResolvedRecords"]
    eval_metrics["unresolvedRecords"] = eval_metrics["unresolvedExceptions"]
    eval_metrics["exceptionRate"] = round((eval_metrics["unresolvedExceptions"]) / total * 100, 2) if total else 0.0
    eval_metrics["autoResolutionRate"] = round(eval_metrics["autoResolvedRecords"] / total * 100, 2) if total else 0.0

    return eval_metrics
