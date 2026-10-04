"""
FinRecon AI - Database layer
SQLite is used for a zero-install, single-command demo. The schema, field
names and relationships mirror what a PostgreSQL production schema would
look like (see README for the Postgres DDL translation notes).
"""
import sqlite3
import os

DB_PATH = os.environ.get(
    "FINRECON_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "finrecon.db"),
)
DB_PATH = os.path.abspath(DB_PATH)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS merchants (
    merchant_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    transaction_id TEXT PRIMARY KEY,
    payment_id TEXT,
    merchant_id TEXT,
    customer_id TEXT,
    upi_id TEXT,
    amount REAL,
    currency TEXT,
    payment_method TEXT,
    status TEXT,
    transaction_timestamp TEXT,
    settlement_date TEXT,
    gateway_reference TEXT,
    bank_reference TEXT,
    fee REAL,
    tax REAL,
    net_amount REAL
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id TEXT PRIMARY KEY,
    transaction_id TEXT,
    merchant_id TEXT,
    settlement_reference TEXT,
    gross_amount REAL,
    fee REAL,
    tax REAL,
    net_amount REAL,
    settlement_date TEXT,
    settlement_status TEXT,
    bank_reference TEXT
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    ledger_id TEXT PRIMARY KEY,
    transaction_id TEXT,
    merchant_id TEXT,
    debit REAL,
    credit REAL,
    ledger_amount REAL,
    tax_amount REAL,
    fee_amount REAL,
    entry_date TEXT,
    ledger_status TEXT,
    reference TEXT
);

CREATE TABLE IF NOT EXISTS reconciliations (
    reconciliation_id TEXT PRIMARY KEY,
    transaction_id TEXT,
    payment_id TEXT,
    settlement_id TEXT,
    ledger_id TEXT,
    match_status TEXT,
    exception_type TEXT,
    confidence REAL,
    payment_amount REAL,
    settlement_amount REAL,
    ledger_amount REAL,
    difference_amount REAL,
    difference_percentage REAL,
    reason TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS exceptions (
    exception_id TEXT PRIMARY KEY,
    transaction_id TEXT,
    exception_type TEXT,
    severity TEXT,
    amount REAL,
    root_cause TEXT,
    ai_explanation TEXT,
    recommended_action TEXT,
    status TEXT,
    created_at TEXT,
    resolved_at TEXT,
    resolution_reason TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT,
    actor TEXT,
    transaction_id TEXT,
    old_status TEXT,
    new_status TEXT,
    reason TEXT,
    timestamp TEXT
);

CREATE TABLE IF NOT EXISTS cash_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT,
    opening_cash REAL,
    inflows REAL,
    outflows REAL,
    fees REAL,
    taxes REAL,
    refunds REAL,
    closing_cash REAL
);

CREATE TABLE IF NOT EXISTS forecast_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_date TEXT,
    horizon_days INTEGER,
    expected_inflow REAL,
    expected_outflow REAL,
    projected_balance REAL,
    confidence REAL,
    methodology TEXT
);

CREATE INDEX IF NOT EXISTS idx_payments_merchant ON payments(merchant_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_settlements_txn ON settlements(transaction_id);
CREATE INDEX IF NOT EXISTS idx_ledger_txn ON ledger_entries(transaction_id);
CREATE INDEX IF NOT EXISTS idx_recon_txn ON reconciliations(transaction_id);
CREATE INDEX IF NOT EXISTS idx_recon_status ON reconciliations(match_status);
CREATE INDEX IF NOT EXISTS idx_exceptions_status ON exceptions(status);
CREATE INDEX IF NOT EXISTS idx_exceptions_created ON exceptions(created_at);
"""


def init_db(reset=False):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def wipe_data():
    """Delete rows but keep schema - used by Reset Demo."""
    conn = get_connection()
    for t in ["merchants", "payments", "settlements", "ledger_entries",
              "reconciliations", "exceptions", "audit_logs",
              "cash_snapshots", "forecast_records"]:
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()
