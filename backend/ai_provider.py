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
        q = question.lower()
        s = context["summary"]

        def fmt(v):
            return f"Rs.{v:,.2f}"

        if "fail" in q or "unresolved" in q and "how many" in q:
            return (f"{s['unresolvedRecords']} of {s['recordsProcessed']} transactions "
                    f"({s['exceptionRate']}%) are currently unresolved and need manual review.")
        if "unresolved amount" in q or ("total" in q and "unresolved" in q):
            return (f"The total unresolved exception value is {fmt(s['unresolvedExceptionValue'])} "
                    f"across {s['unresolvedRecords']} unresolved transactions.")
        if "settlement" in q and ("lower" in q or "gap" in q or "why" in q):
            gap = s['settlementDifference']
            direction = "below" if gap > 0 else "above"
            return (f"Total settlement value is {fmt(s['totalSettlementValue'])} against "
                    f"{fmt(s['totalPaymentValue'])} in payments - a gap of {fmt(abs(gap))} "
                    f"{direction} expected. This is driven by {s['unresolvedRecords']} unresolved "
                    f"exceptions (missing settlements, amount mismatches and partial settlements) "
                    f"worth {fmt(s['unresolvedExceptionValue'])}, plus {s['autoResolvedRecords']} "
                    f"auto-resolved fee/tax/timing differences.")
        if "top exception" in q or "exception types" in q or "which exception" in q:
            top = context.get("top_exceptions", [])
            if not top:
                return "There are no open exceptions in the current dataset."
            lines = [f"{t['exception_type']}: {t['count']} case(s), {fmt(t['value'])}" for t in top[:5]]
            return "Top exception types by frequency: " + "; ".join(lines) + "."
        if "merchant" in q and ("highest" in q or "top" in q or "most" in q):
            merch = context.get("top_merchants", [])
            if not merch:
                return "No merchant exception data is available yet - run reconciliation first."
            lines = [f"{m['name']} ({m['count']} exceptions, {fmt(m['value'])})" for m in merch[:5]]
            return "Merchants with the most reconciliation exceptions: " + "; ".join(lines) + "."
        if "settlement delay" in q or "delayed" in q:
            n = context.get("delay_count", 0)
            return (f"{n} transaction(s) show a settlement delay beyond the "
                    f"{context.get('date_tolerance_hours', 48)}-hour SLA.")
        if "cash position" in q and "tomorrow" not in q and "expected" not in q:
            cp = context["cash_position"]
            return (f"Current cash position is {fmt(cp['currentCashPosition'])}. "
                    f"Pending settlements of {fmt(cp['pendingSettlementAmount'])} are expected "
                    f"to be received, against {fmt(cp['expectedSettlementInflow'])} in scheduled inflows.")
        if "tomorrow" in q or "next day" in q or "expected cash" in q:
            fc = context.get("forecast_1d")
            if not fc:
                return "Forecast data is not available - run reconciliation first."
            return (f"Projected cash position for tomorrow is {fmt(fc['projectedBalance'])} "
                    f"(expected inflow {fmt(fc['expectedInflow'])}, expected outflow "
                    f"{fmt(fc['expectedOutflow'])}, confidence {fc['confidence']}%).")
        if "tax mismatch" in q:
            n = context.get("tax_mismatch_count", 0)
            return f"{n} transaction(s) currently show a tax mismatch between settlement and payment records."
        if "match rate" in q or "accuracy" in q:
            return (f"Current reconciliation match rate is {s['matchRate']}% "
                    f"({s['matchedRecords'] + s['autoResolvedRecords']} of {s['recordsProcessed']} "
                    f"records matched or safely auto-resolved).")

        # Generic grounded summary fallback
        return (f"Based on the current dataset: {s['recordsProcessed']} records processed, "
                f"{s['matchRate']}% match rate, {s['unresolvedRecords']} unresolved exceptions "
                f"worth {fmt(s['unresolvedExceptionValue'])}. Ask about match rate, cash position, "
                f"settlement gap, top exception types, or specific merchants for more detail.")


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
