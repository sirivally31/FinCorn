"""
FinRecon AI - Cash position and cash forecast engine.

SIMPLIFIED DEMO ACCOUNTING ASSUMPTIONS (documented, not hidden):
    - Opening cash balance is configured with OPENING_CASH (defaults to zero).
  - Inflows  = successful payment amounts collected from customers.
  - Outflows = settlement net amounts actually paid out to merchants,
               plus gateway fees and taxes remitted.
  - Refunds  = 0 in this synthetic dataset (field is modeled for realism;
               no REFUNDED status exists in the seed data).
  - Current cash = Opening + Inflows - Outflows - Refunds.
  - Pending settlement = money collected from customers that has not yet
    been paid out to merchants (payments with MISSING_SETTLEMENT / unresolved
    settlement gaps).

Forecast methodology (explained in UI): a transparent moving-average model.
Average daily inflow/outflow is computed from the actual synthetic
transaction history's date range, then projected forward. Confidence
decreases with horizon length to reflect growing uncertainty.
"""
import datetime
import os
from database import get_connection

OPENING_CASH = float(os.environ.get("OPENING_CASH", "0"))


def compute_cash_position():
    conn = get_connection()
    cur = conn.cursor()

    total_payment_inflow = cur.execute(
        "SELECT COALESCE(SUM(amount),0) v FROM payments WHERE status='SUCCESS'").fetchone()["v"]
    total_fees = cur.execute("SELECT COALESCE(SUM(fee),0) v FROM payments").fetchone()["v"]
    total_tax = cur.execute("SELECT COALESCE(SUM(tax),0) v FROM payments").fetchone()["v"]
    total_settled_out = cur.execute(
        "SELECT COALESCE(SUM(net_amount),0) v FROM settlements "
        "WHERE settlement_status IN ('SETTLED','PARTIALLY_SETTLED')").fetchone()["v"]
    total_refunds = cur.execute(
        "SELECT COALESCE(SUM(amount),0) v FROM payments WHERE status='REFUNDED'").fetchone()["v"]

    current_cash = OPENING_CASH + total_payment_inflow - total_settled_out - total_fees - total_tax - total_refunds

    pending_settlement = round(
        max(0.0, total_payment_inflow - total_fees - total_tax - total_settled_out), 2)

    conn.close()
    return {
        "openingCash": round(OPENING_CASH, 2),
        "totalPaymentInflow": round(total_payment_inflow, 2),
        "expectedSettlementInflow": pending_settlement,  # for a merchant-side view
        "pendingSettlementAmount": pending_settlement,
        "fees": round(total_fees, 2),
        "taxes": round(total_tax, 2),
        "refunds": round(total_refunds, 2),
        "totalSettledOut": round(total_settled_out, 2),
        "currentCashPosition": round(current_cash, 2),
        "netPosition": round(current_cash - OPENING_CASH, 2),
        "assumptions": (
            "Opening cash is configured by OPENING_CASH (zero if unset). Inflows are successful customer "
            "payments; outflows are merchant settlements plus fees and tax. This is a "
            "simplified operating-cash model for demo purposes, not full GAAP accounting."
        ),
    }


def _daily_series():
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT substr(transaction_timestamp,1,10) d, SUM(amount) inflow "
        "FROM payments WHERE status='SUCCESS' GROUP BY d ORDER BY d").fetchall()
    out_rows = cur.execute(
        "SELECT substr(settlement_date,1,10) d, SUM(net_amount) outflow "
        "FROM settlements WHERE settlement_status IN ('SETTLED','PARTIALLY_SETTLED') "
        "GROUP BY d ORDER BY d").fetchall()
    conn.close()
    inflows = [r["inflow"] for r in rows] or [0.0]
    outflows = [r["outflow"] for r in out_rows] or [0.0]
    return inflows, outflows


def compute_forecast():
    inflows, outflows = _daily_series()
    avg_daily_inflow = sum(inflows) / len(inflows)
    avg_daily_outflow = sum(outflows) / len(outflows)

    cash = compute_cash_position()
    current = cash["currentCashPosition"]

    horizons = [
        (1, 90.0),
        (3, 75.0),
        (7, 60.0),
    ]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM forecast_records")
    today = datetime.date.today()
    results = []
    for horizon_days, confidence in horizons:
        expected_inflow = round(avg_daily_inflow * horizon_days, 2)
        expected_outflow = round(avg_daily_outflow * horizon_days, 2)
        projected_balance = round(current + expected_inflow - expected_outflow, 2)
        forecast_date = (today + datetime.timedelta(days=horizon_days)).isoformat()
        methodology = (f"Moving average: avg daily inflow (Rs.{avg_daily_inflow:,.2f}) and "
                       f"avg daily settlement outflow (Rs.{avg_daily_outflow:,.2f}) from actual "
                       f"transaction history, projected {horizon_days} day(s) forward.")
        cur.execute("""INSERT INTO forecast_records (forecast_date, horizon_days,
            expected_inflow, expected_outflow, projected_balance, confidence, methodology)
            VALUES (?,?,?,?,?,?,?)""",
            (forecast_date, horizon_days, expected_inflow, expected_outflow,
             projected_balance, confidence, methodology))
        results.append({
            "horizonDays": horizon_days,
            "forecastDate": forecast_date,
            "expectedInflow": expected_inflow,
            "expectedOutflow": expected_outflow,
            "projectedBalance": projected_balance,
            "confidence": confidence,
            "methodology": methodology,
        })
    conn.commit()
    conn.close()
    return results
