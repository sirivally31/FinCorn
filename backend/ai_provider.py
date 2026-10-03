"""
FinRecon AI - AI provider abstraction.

AIProvider is the interface. MockAIProvider is rule-based / template-driven
and needs no network or API key - it is the default and guarantees the demo
never breaks. OpenAIProvider is used only when AI_PROVIDER=openai and
OPENAI_API_KEY is set.

SAFETY: every explanation is built ONLY from numbers actually passed in
(payment/settlement/ledger rows already computed by the deterministic
reconciliation engine). Nothing is invented.
"""
import os
import json
import re
import urllib.request


class AIProvider:
    def explain_exception(self, txn_id, exc_type, payment, settlement, ledger, diff, reason):
        raise NotImplementedError

    def answer_query(self, question, context: dict):
        raise NotImplementedError


class MockAIProvider(AIProvider):
    """Deterministic, template-based 'AI'. No network, no API key required."""

    LABELS = {
        "AMOUNT_MISMATCH": "an amount mismatch",
        "MISSING_SETTLEMENT": "a missing settlement",
        "FEE_MISMATCH": "a fee mismatch",
        "TAX_MISMATCH": "a tax mismatch",
        "SETTLEMENT_DELAY": "a settlement delay",
        "PARTIAL_SETTLEMENT": "a partial settlement",
        "REFERENCE_MISMATCH": "a bank reference mismatch",
        "LEDGER_MISMATCH": "a ledger mismatch",
        "DUPLICATE_RECORD": "a duplicate record",
        "UNKNOWN_TRANSACTION": "an unknown/orphan transaction",
        "STATUS_MISMATCH": "a status mismatch",
    }

    ACTIONS = {
        "AMOUNT_MISMATCH": "Escalate to finance ops for manual bank statement cross-check; "
                            "do not auto-correct amount discrepancies above tolerance.",
        "MISSING_SETTLEMENT": "Hold in exception queue and re-check next settlement cycle; "
                               "escalate if still missing after 3 business days.",
        "FEE_MISMATCH": "Mark as expected fee deduction if within policy band; otherwise "
                         "confirm current fee schedule with payment gateway.",
        "TAX_MISMATCH": "Verify GST computation against the fee actually charged; auto-"
                         "resolve if the drift is a rounding difference.",
        "SETTLEMENT_DELAY": "Monitor; auto-resolve if within the acceptable settlement "
                             "window, otherwise escalate to the banking partner.",
        "PARTIAL_SETTLEMENT": "Confirm with payment gateway whether a partial or split "
                               "settlement was intentional before releasing funds.",
        "REFERENCE_MISMATCH": "Manually verify bank reference against the bank statement; "
                               "do not assume the transaction is fraudulent without review.",
        "LEDGER_MISMATCH": "Reconcile with the accounting/ERP system; check for a posting "
                            "error or missed adjustment entry.",
        "DUPLICATE_RECORD": "Confirm with the gateway whether this is a duplicate submission "
                             "or a genuine repeat transaction before merging or voiding.",
        "UNKNOWN_TRANSACTION": "Escalate immediately - a settlement with no matching payment "
                                "record needs finance and engineering investigation.",
        "STATUS_MISMATCH": "Escalate - conflicting status between payment and settlement "
                            "systems can indicate a failed/reversed payment.",
    }

    def explain_exception(self, txn_id, exc_type, payment, settlement, ledger, diff, reason):
        label = self.LABELS.get(exc_type, exc_type)
        p_amt = payment["amount"] if payment else None
        s_amt = settlement["gross_amount"] if settlement else None

        parts = [f"Transaction {txn_id} was flagged with {label}."]
        if p_amt is not None:
            parts.append(f"Payment amount on record: Rs.{p_amt:,.2f}.")
        if s_amt is not None:
            parts.append(f"Settlement amount on record: Rs.{s_amt:,.2f}.")
        if diff is not None:
            parts.append(f"Difference: Rs.{abs(diff):,.2f} "
                         f"({'payment higher' if diff > 0 else 'settlement higher'}).")
        parts.append(reason)

        explanation = " ".join(parts)
        action = self.ACTIONS.get(exc_type, "Route to finance operations for manual review.")
        return explanation, action

    def answer_query(self, question, context: dict):
        q = (question or "").strip().lower()
        s = context.get("summary", {}) or {}

        def fmt(v):
            return f"Rs.{float(v):,.2f}"

        if not q:
            return "Please enter a finance question to get a grounded answer."

        if re.search(r"\b(mark|reconciled|resolve|resolved)\b", q) and "transaction" in q:
            return ("I cannot mark transactions as reconciled or change the financial truth. "
                    "The deterministic engine owns reconciliation; use the human-review workflow in the Exceptions queue for any required action.")

        if "how much money is currently unsettled" in q or "currently unsettled" in q or ("unsettled" in q and ("money" in q or "amount" in q)):
            unsettled = context.get("cash_position", {}).get("pendingSettlementAmount", s.get("unresolvedExceptionValue", 0))
            return f"The currently unsettled amount is {fmt(unsettled)}."

        if "largest financial discrepancy" in q or "largest discrepancy" in q or "largest settlement discrepancy" in q:
            top = context.get("top_exceptions", [])
            if top:
                entry = top[0]
                return f"The largest identified discrepancy today is {entry.get('exception_type', 'an unresolved exception')} at {fmt(entry.get('value', 0))}."
            return "I do not have enough exception data to identify the largest discrepancy."

        if "what is causing the current settlement gap" in q or "settlement gap" in q and "why" in q:
            gap = s.get("settlementDifference", 0)
            return (f"The settlement gap is {fmt(abs(gap))} {('below' if gap > 0 else 'above')} the expected payment total. "
                    f"It is driven by {s.get('unresolvedRecords', 0)} unresolved exceptions worth {fmt(s.get('unresolvedExceptionValue', 0))}, "
                    f"including missing settlements and amount mismatches.")

        if "cash position" in q and "tomorrow" not in q and "expected" not in q and "current" in q:
            cp = context.get("cash_position", {})
            return (f"Current cash position is {fmt(cp.get('currentCashPosition', s.get('currentCash', 0)))}. "
                    f"Pending settlement exposure is {fmt(cp.get('pendingSettlementAmount', 0))}.")

        if "next 7 days" in q or "7 day" in q or "7-day" in q or "expected cash position over the next 7 days" in q or ("expected cash" in q and "7" in q):
            fc = context.get("forecast_7d") or next((f for f in context.get("forecast_horizons", []) if f.get("horizonDays") == 7), None) or context.get("forecast_1d")
            if not fc:
                return "Forecast data is not available for the next 7 days in the current dataset."
            return (f"Expected cash position in 7 days is {fmt(fc.get('projectedBalance', 0))} with expected inflow {fmt(fc.get('expectedInflow', 0))} "
                    f"and expected outflow {fmt(fc.get('expectedOutflow', 0))}; confidence is {fc.get('confidence', 0)}%.")

        if "what is our current cash position" in q or "current cash position" in q:
            cp = context.get("cash_position", {})
            return f"Current cash position is {fmt(cp.get('currentCashPosition', s.get('currentCash', 0)))}."

        if "what percentage of transactions matched" in q or "percentage of transactions matched" in q or "match rate" in q and "percentage" in q:
            return f"{s.get('matchRate', 0)}% of transactions matched or were safely auto-resolved."

        if "match rate is not 100" in q or "reconciliation match rate is not 100" in q or "why" in q and "match rate" in q:
            return (f"The match rate is {s.get('matchRate', 0)}% because {s.get('unresolvedRecords', 0)} transactions remain unresolved, "
                    f"worth {fmt(s.get('unresolvedExceptionValue', 0))}, while {s.get('autoResolvedRecords', 0)} were safely auto-resolved.")

        if "issue should a finance controller investigate first" in q or "investigate first" in q:
            top = context.get("top_exceptions", [])
            if top:
                first = top[0]
                return f"The highest-priority issue is {first.get('exception_type', 'an unresolved exception')}, appearing {first.get('count', 0)} time(s)."
            return "There is no unresolved exception data to rank right now."

        if "main reasons transactions remain unresolved" in q or "reasons transactions remain unresolved" in q:
            top = context.get("top_exceptions", [])
            if not top:
                return "No unresolved exception reasons are present in the current data."
            fragments = [f"{t.get('exception_type', 'Unknown')} ({t.get('count', 0)} case(s))" for t in top[:3]]
            return "The main unresolved reasons are: " + "; ".join(fragments) + "."

        if "merchant" in q and ("most unresolved" in q or "highest" in q or "top" in q or "most" in q):
            merch = context.get("top_merchants", [])
            if not merch:
                return "No merchant exception data is available yet."
            lines = [f"{m['name']} ({m['count']} unresolved cases, {fmt(m['value'])})" for m in merch[:5]]
            return "Merchants with the most unresolved exceptions: " + "; ".join(lines) + "."

        if "top exception" in q or "exception types" in q or "which exception" in q or "exception type" in q:
            top = context.get("top_exceptions", [])
            if not top:
                return "There are no open exceptions in the current dataset."
            lines = [f"{t['exception_type']}: {t['count']} case(s), {fmt(t['value'])}" for t in top[:5]]
            return "Top exception types: " + "; ".join(lines) + "."

        if "settlement delay" in q or "delayed" in q:
            n = context.get("delay_count", 0)
            return f"{n} transaction(s) show a settlement delay beyond the allowed {context.get('date_tolerance_hours', 48)}-hour SLA."

        if "tax mismatch" in q:
            n = context.get("tax_mismatch_count", 0)
            return f"{n} transaction(s) currently show a tax mismatch between settlement and payment records."

        if "unresolved" in q and ("how many" in q or "count" in q or "failed" in q):
            return (f"{s.get('unresolvedRecords', 0)} of {s.get('recordsProcessed', 0)} transactions "
                    f"({s.get('exceptionRate', 0)}%) are unresolved and require manual review.")

        if "unresolved amount" in q or "total unresolved" in q or ("unresolved" in q and "amount" in q):
            return (f"The total unresolved exception value is {fmt(s.get('unresolvedExceptionValue', 0))} "
                    f"across {s.get('unresolvedRecords', 0)} unresolved transactions.")

        if "settlement" in q and ("lower" in q or "gap" in q or "why" in q or "shortfall" in q):
            gap = s.get("settlementDifference", 0)
            direction = "below" if gap > 0 else "above"
            return (f"Total settlement value is {fmt(s.get('totalSettlementValue', 0))} compared with {fmt(s.get('totalPaymentValue', 0))} in payments. "
                    f"The current gap is {fmt(abs(gap))} {direction} expected, driven by unresolved exceptions worth {fmt(s.get('unresolvedExceptionValue', 0))}.")

        if "match rate" in q or "accuracy" in q or "matched" in q and "transactions" in q:
            return (f"Current reconciliation match rate is {s.get('matchRate', 0)}% and classification accuracy is {s.get('accuracy', 0)}%. "
                    f"{s.get('matchedRecords', 0) + s.get('autoResolvedRecords', 0)} of {s.get('recordsProcessed', 0)} records matched or were auto-resolved.")

        return (f"Based on the current dataset: {s.get('recordsProcessed', 0)} records processed, "
                f"{s.get('matchRate', 0)}% match rate, {s.get('unresolvedRecords', 0)} unresolved exceptions, "
                f"and {fmt(s.get('unresolvedExceptionValue', 0))} in unresolved value. Ask about cash position, settlement gap, exception types, or merchant risk for more detail.")


class OpenAIProvider(AIProvider):
    """Used only when AI_PROVIDER=openai and OPENAI_API_KEY is configured."""

    def __init__(self, api_key, model="gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def _chat(self, system, user):
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps({
                "model": self.model,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                "temperature": 0.2,
            }).encode(),
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]

    def explain_exception(self, txn_id, exc_type, payment, settlement, ledger, diff, reason):
        system = ("You are a finance operations analyst. Use ONLY the facts given. "
                  "Never invent numbers. Be concise (2-3 sentences) and end with a "
                  "one-line recommended action prefixed 'ACTION:'.")
        user = (f"Transaction: {txn_id}\nException type: {exc_type}\n"
                f"Payment: {dict(payment) if payment else None}\n"
                f"Settlement: {dict(settlement) if settlement else None}\n"
                f"Ledger: {dict(ledger) if ledger else None}\nDifference: {diff}\n"
                f"Deterministic engine reason: {reason}")
        text = self._chat(system, user)
        if "ACTION:" in text:
            explanation, action = text.split("ACTION:", 1)
        else:
            explanation, action = text, "Route to finance operations for manual review."
        return explanation.strip(), action.strip()

    def answer_query(self, question, context: dict):
        system = ("You are FinRecon AI's finance assistant. Answer ONLY using the JSON "
                  "context provided. Never invent figures. If the answer isn't in the "
                  "context, say you don't have enough evidence.")
        user = f"Context: {json.dumps(context, default=str)}\n\nQuestion: {question}"
        return self._chat(system, user).strip()


def get_provider():
    provider = os.environ.get("AI_PROVIDER", "mock").lower()
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        if key:
            model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            return OpenAIProvider(key, model)
    return MockAIProvider()
