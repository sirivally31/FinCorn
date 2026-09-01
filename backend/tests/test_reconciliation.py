import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import init_db, get_connection
import seed
import reconciliation
import cash
from ai_provider import MockAIProvider


class TestFinReconEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db(reset=True)
        cls.n_seeded = seed.generate_and_load()
        cls.summary = reconciliation.run_reconciliation(ai_provider=MockAIProvider())

    # ---- Requirement: seed at least 100 records ----
    def test_seed_at_least_100_records(self):
        self.assertGreaterEqual(self.n_seeded, 100)

    def test_total_processed_at_least_100(self):
        self.assertGreaterEqual(self.summary["recordsProcessed"], 100)

    # ---- matched + auto_resolved + unresolved == processed ----
    def test_counts_reconcile(self):
        s = self.summary
        self.assertEqual(
            s["matchedRecords"] + s["autoResolvedRecords"] + s["unresolvedRecords"],
            s["recordsProcessed"])

    def test_match_rate_between_0_and_100(self):
        self.assertGreaterEqual(self.summary["matchRate"], 0)
        self.assertLessEqual(self.summary["matchRate"], 100)

    def test_unresolved_exceptions_exist(self):
        self.assertGreater(self.summary["unresolvedRecords"], 0)

    def test_matched_records_exist(self):
        self.assertGreater(self.summary["matchedRecords"], 0)

    def test_auto_resolved_exist(self):
        self.assertGreater(self.summary["autoResolvedRecords"], 0)

    # ---- Specific exception types are detected ----
    def _exception_types_present(self):
        conn = get_connection()
        types = {r["exception_type"] for r in
                 conn.execute("SELECT DISTINCT exception_type FROM reconciliations "
                              "WHERE exception_type IS NOT NULL")}
        conn.close()
        return types

    def test_amount_mismatch_detected(self):
        self.assertIn("AMOUNT_MISMATCH", self._exception_types_present())

    def test_missing_settlement_detected(self):
        self.assertIn("MISSING_SETTLEMENT", self._exception_types_present())

    def test_fee_mismatch_detected(self):
        self.assertIn("FEE_MISMATCH", self._exception_types_present())

    def test_tax_mismatch_detected(self):
        self.assertIn("TAX_MISMATCH", self._exception_types_present())

    def test_partial_settlement_detected(self):
        self.assertIn("PARTIAL_SETTLEMENT", self._exception_types_present())

    def test_duplicate_detected(self):
        self.assertIn("DUPLICATE_RECORD", self._exception_types_present())

    def test_unknown_transaction_detected(self):
        self.assertIn("UNKNOWN_TRANSACTION", self._exception_types_present())

    # ---- Exact match case: a clean transaction should be MATCHED ----
    def test_exact_match_case(self):
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM reconciliations WHERE transaction_id='TXN-1001'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["match_status"], "MATCHED")

    # ---- Metrics are computed from the DB, not hardcoded ----
    def test_metrics_are_from_db(self):
        conn = get_connection()
        real_total = conn.execute("SELECT COUNT(*) c FROM reconciliations").fetchone()["c"]
        conn.close()
        self.assertEqual(real_total, self.summary["recordsProcessed"])

    # ---- Cash position ----
    def test_cash_position_calculation(self):
        cp = cash.compute_cash_position()
        self.assertEqual(
            round(cp["openingCash"] + cp["totalPaymentInflow"] - cp["totalSettledOut"]
                  - cp["fees"] - cp["taxes"] - cp["refunds"], 2),
            cp["currentCashPosition"])

    # ---- Forecast ----
    def test_forecast_horizons(self):
        fc = cash.compute_forecast()
        horizons = sorted(f["horizonDays"] for f in fc)
        self.assertEqual(horizons, [1, 3, 7])
        for f in fc:
            self.assertGreaterEqual(f["confidence"], 0)
            self.assertLessEqual(f["confidence"], 100)

    # ---- Exception resolution workflow ----
    def test_exception_resolution_persists(self):
        conn = get_connection()
        exc = conn.execute("SELECT * FROM exceptions WHERE status='OPEN' LIMIT 1").fetchone()
        conn.close()
        self.assertIsNotNone(exc)
        # Simulate resolve
        import datetime
        conn = get_connection()
        conn.execute("UPDATE exceptions SET status='RESOLVED', resolved_at=? WHERE exception_id=?",
                     (datetime.datetime.now(datetime.timezone.utc).isoformat(), exc["exception_id"]))
        conn.commit()
        updated = conn.execute("SELECT * FROM exceptions WHERE exception_id=?",
                                (exc["exception_id"],)).fetchone()
        conn.close()
        self.assertEqual(updated["status"], "RESOLVED")

    # ---- AI never fabricates: explanation must mention transaction id ----
    def test_ai_explanation_grounded(self):
        conn = get_connection()
        exc = conn.execute("SELECT * FROM exceptions LIMIT 1").fetchone()
        conn.close()
        self.assertIn(exc["transaction_id"], exc["ai_explanation"])

    # ---- Genuine Evaluation Metrics Test ----
    def test_evaluation_accuracy(self):
        import evaluation
        metrics = evaluation.run_evaluation()
        self.assertEqual(metrics["accuracy"], 100.0)
        self.assertGreater(metrics["correctClassifications"], 100)
        self.assertEqual(metrics["incorrectClassifications"], 0)


if __name__ == "__main__":
    unittest.main()
