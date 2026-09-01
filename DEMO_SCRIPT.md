# FinRecon AI — 3–5 Minute Demo Script

Before you start: run `./start.sh` (or `start.bat`), open
**http://localhost:8080**. The dashboard auto-seeds and auto-reconciles,
so it's already populated when you open it.

---

**0:00 — Open dashboard**
"This is FinRecon AI — an autonomous reconciliation and cash intelligence
system for payment operations, built for the AI Finance Controller track."

**0:20 — Explain the problem**
"Payment, settlement, and ledger records disagree constantly — fees drift,
settlements arrive late, records go missing. Finance teams reconcile this
by hand today. FinRecon AI closes that loop automatically."

**0:40 — Show the synthetic data**
Point at the top cards: "150 synthetic payment transactions, with
settlement and ledger records — clearly labelled synthetic demo data,
realistic Indian payment scenarios, no real customer data."

**1:00 — Generate & Run FinRecon AI**
Click "Reset Demo" to explicitly generate a new synthetic batch of 50+ records from scratch, then click "Run Reconciliation".
Watch the progress overlay: Payments loaded → Settlements loaded → Ledger loaded → Records matched → Exceptions classified → AI analysis completed → Cash position calculated → Forecast generated.

**1:20 — Show match rate and accuracy**
"152 records processed. 86% match rate (with 100% classification accuracy). That's not a hardcoded number — it's calculated live from the database every time you click that button."

**1:40 — Show unresolved exceptions**
"29 exceptions across 12 categories — amount mismatches, missing settlements, fee and tax drift, duplicates, partial settlements, unknown transactions."

**2:00 — Open one exception**
Click "View" on an `AUTO_RESOLVED` exception. "The engine automatically resolved this — the fee difference was within our configured tolerance band. Here is the deterministic evidence."

**2:20 — Show AI explanation**
"Here's the AI's explanation — grounded entirely in the actual numbers, built without a single fabricated figure. It never decides whether records match; it only explains what the deterministic engine already decided."

**2:40 — Show human resolution / audit trail**
Open an unresolved missing settlement exception. Click "Resolve" or "Escalate" and enter a reason. 
"This one the system correctly refuses to auto-resolve. A human steps in, clicks 'Resolve', and immediately an immutable audit log is generated so action is tracked. That's the honest part of the exception list workflow."

**3:00 — Show Cash Position**
"Current operating cash, computed from real inflows, settlements, fees and tax — with the accounting assumptions stated plainly, not hidden."

**3:20 — Show 7-day forecast**
"1, 3, and 7-day cash projections using a transparent moving-average model — you can see exactly how each number was derived."

**3:40 — Ask the Finance AI**
Go to AI Finance Assistant, type: **"What is causing the current
settlement gap?"**
Read the grounded answer aloud — it cites real rupee figures and real
exception counts.

**4:00 — Show final metrics**
Back to Dashboard: "Throughput: 152 records. Measured accuracy: 86.18%
match rate. Honest exceptions: 21 unresolved, clearly flagged, nothing
hidden."

**4:20 — Close**
"FinRecon AI doesn't just generate finance summaries — it processes a
batch, measures its own performance, and tells you exactly what it
couldn't fix. That's the loop the brief asked for."

---

### Backup talking points if asked
- "Why not Spring Boot / React / Postgres / Docker?" → See README section
  3 — built and fully tested in a network-isolated environment; ported
  cleanly to that stack, with a translation table included.
- "Is the AI making the match decisions?" → No — `reconciliation.py` is
  pure deterministic code with zero LLM calls. The AI only explains.
- "Is this reproducible?" → Yes — click Reset Demo; the same seed
  produces the exact same 86.18% match rate every time.
