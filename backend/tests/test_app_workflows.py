import base64
import io
import os
import tempfile
import unittest
from unittest.mock import patch

import database
from app import app


PAYMENTS_CSV = (
    "transaction_id,payment_id,merchant_id,amount,fee,tax,status,"
    "transaction_timestamp,bank_reference\n"
    "TX-REAL-1,PAY-1,M-1,100,2,0.36,SUCCESS,2026-01-01T12:00:00,REF-1\n"
)
SETTLEMENTS_CSV = (
    "settlement_id,transaction_id,merchant_id,gross_amount,fee,tax,net_amount,"
    "settlement_date,settlement_status,bank_reference\n"
    "SET-1,TX-REAL-1,M-1,100,2,0.36,97.64,2026-01-01T13:00:00,SETTLED,REF-1\n"
)
LEDGER_CSV = (
    "ledger_id,transaction_id,ledger_amount\n"
    "LED-1,TX-REAL-1,97.64\n"
)


class TestAppDataWorkflow(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
        self.temp_dir = tempfile.TemporaryDirectory(dir=data_dir)
        self.db_path = os.path.join(self.temp_dir.name, "workflow.db")
        self.database_path = patch.object(database, "DB_PATH", self.db_path)
        self.database_path.start()
        database.init_db(reset=False)
        self.environment = patch.dict(os.environ, {
            "APP_USERNAME": "operator",
            "APP_PASSWORD": "test-password",
            "FINRECON_ALLOW_IMPORT": "true",
            "FINRECON_DB_PATH": self.db_path,
        })
        self.environment.start()
        self.client = app.test_client()
        token = base64.b64encode(b"operator:test-password").decode("ascii")
        self.auth = {"Authorization": f"Basic {token}"}

    def tearDown(self):
        self.environment.stop()
        self.database_path.stop()
        self.temp_dir.cleanup()

    def _files(self, payments=PAYMENTS_CSV):
        return {
            "payments": (io.BytesIO(payments.encode("utf-8")), "payments.csv"),
            "settlements": (io.BytesIO(SETTLEMENTS_CSV.encode("utf-8")), "settlements.csv"),
            "ledger": (io.BytesIO(LEDGER_CSV.encode("utf-8")), "ledger.csv"),
        }

    def _import(self, payments=PAYMENTS_CSV):
        return self.client.post(
            "/api/import",
            data=self._files(payments),
            headers=self.auth,
            content_type="multipart/form-data",
        )

    def test_imported_source_records_survive_reconciliation(self):
        response = self._import()
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(response.json["summary"]["recordsProcessed"], 1)

        rerun = self.client.post("/api/reconciliation/run", headers=self.auth)
        self.assertEqual(rerun.status_code, 200)
        self.assertEqual(rerun.json["summary"]["recordsProcessed"], 1)
        records = self.client.get("/api/reconciliations", headers=self.auth).json
        self.assertEqual(records["results"][0]["transaction_id"], "TX-REAL-1")

    def test_invalid_import_preserves_active_dataset(self):
        self.assertEqual(self._import().status_code, 201)
        invalid = self._import("transaction_id,amount\nTX-OTHER,1\n")
        self.assertEqual(invalid.status_code, 400)
        records = self.client.get("/api/reconciliations", headers=self.auth).json
        self.assertEqual(records["count"], 1)
        self.assertEqual(records["results"][0]["transaction_id"], "TX-REAL-1")

    def test_financial_routes_require_auth_when_configured(self):
        self.assertEqual(self.client.get("/api/dashboard/summary").status_code, 401)
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_import_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {"FINRECON_ALLOW_IMPORT": "false"}):
            response = self.client.post("/api/import", headers=self.auth)
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
