"""
FinRecon AI - Deterministic synthetic dataset generator.

Generates 150 payment transactions plus corresponding settlement and
ledger records. A fixed RNG seed + a fixed exception recipe (mapping
specific transaction indices to specific injected discrepancies) makes
every fresh seed run byte-for-byte reproducible.

ALL DATA GENERATED HERE IS SYNTHETIC DEMO DATA. No real customers,
accounts, or bank details are used.
"""
import random
import datetime
from database import get_connection

random.seed(42)

TOTAL_TRANSACTIONS = 150

MERCHANTS = [
    ("MER001", "Sharma Electronics", "Electronics"),
    ("MER002", "Fresh Basket Grocers", "Grocery"),
    ("MER003", "Reddy Travels", "Travel"),
    ("MER004", "Kapoor Apparel Co", "Fashion"),
    ("MER005", "Bengaluru Bites", "Food & Beverage"),
    ("MER006", "Chennai Books & Stationery", "Retail"),
    ("MER007", "Pune Fitness Studio", "Fitness"),
    ("MER008", "Delhi Home Decor", "Home"),
    ("MER009", "Mumbai Cab Services", "Transport"),
    ("MER010", "Hyderabad Pharmacy Plus", "Healthcare"),
]

PAYMENT_METHODS = ["UPI", "CARD", "NETBANKING", "WALLET"]
UPI_HANDLES = ["okhdfcbank", "okicici", "oksbi", "okaxis", "ybl", "paytm"]
FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Reyansh", "Ananya",
               "Diya", "Saanvi", "Myra", "Kavya", "Rohan", "Priya", "Neha",
               "Karan", "Sanjay", "Meera", "Arjun", "Pooja", "Vikram", "Anjali"]

BASE_DATE = datetime.date(2026, 8, 1)

# ---------------------------------------------------------------------
# Deterministic exception recipe: txn index -> exception type.
# 27 of 150 transactions (18%) carry a controlled, reproducible defect.
# ---------------------------------------------------------------------
EXCEPTION_RECIPE = {}
def _assign(indices, label):
    for i in indices:
        EXCEPTION_RECIPE[i] = label

_assign([5, 25, 45, 65, 85], "AMOUNT_MISMATCH")
_assign([10, 30, 50, 70], "MISSING_SETTLEMENT")
_assign([15, 35, 55], "FEE_MISMATCH")
_assign([20, 40, 60], "TAX_MISMATCH")
_assign([75, 95], "LEDGER_MISMATCH")
_assign([80, 100], "SETTLEMENT_DELAY")
_assign([105, 120], "PARTIAL_SETTLEMENT")
_assign([110], "REFERENCE_MISMATCH")
_assign([115], "DUPLICATE_TRANSACTION")
_assign([125], "DUPLICATE_SETTLEMENT")
_assign([130], "UNKNOWN_TRANSACTION")
_assign([135], "STATUS_MISMATCH")
_assign([140, 145], "MISSING_SETTLEMENT")
_assign([150], "AMOUNT_MISMATCH")
# = 27 injected exceptions across 12 categories, rest (123) are clean matches.


def _amount_for(i):
    # Deterministic realistic amount curve, INR 150 - 45000
    base = 150 + (i * 173) % 44850
    return round(base + (i % 7) * 12.5, 2)


def _ts(i, offset_hours=0):
    dt = datetime.datetime.combine(BASE_DATE, datetime.time(9, 0)) + \
        datetime.timedelta(hours=(i * 3) % 240, minutes=(i * 11) % 60) + \
        datetime.timedelta(hours=offset_hours)
    return dt.isoformat()


def generate_and_load():
    conn = get_connection()
    cur = conn.cursor()

    for mid, name, cat in MERCHANTS:
        cur.execute("INSERT INTO merchants (merchant_id, name, category) VALUES (?,?,?)",
                    (mid, name, cat))

    for i in range(1, TOTAL_TRANSACTIONS + 1):
        txn_id = f"TXN-{1000 + i}"
        payment_id = f"PAY-{2000 + i}"
        merchant_id = MERCHANTS[i % len(MERCHANTS)][0]
        customer_id = f"CUST-{3000 + i}"
        name = FIRST_NAMES[i % len(FIRST_NAMES)].lower()
        upi_id = f"{name}{i}@{UPI_HANDLES[i % len(UPI_HANDLES)]}"
        method = PAYMENT_METHODS[i % len(PAYMENT_METHODS)]
        amount = _amount_for(i)
        fee = round(amount * 0.02, 2)          # 2% processing fee
        tax = round(fee * 0.18, 2)             # 18% GST on fee
        net_amount = round(amount - fee - tax, 2)
        gateway_ref = f"GW{700000 + i}"
        bank_ref = f"BNK{800000 + i}"
        txn_time = _ts(i)
        settlement_date = _ts(i, offset_hours=24)
        status = "SUCCESS"

        exc = EXCEPTION_RECIPE.get(i)

        if exc == "STATUS_MISMATCH":
            status = "SUCCESS"  # payment says success

        cur.execute("""INSERT INTO payments (transaction_id, payment_id, merchant_id,
            customer_id, upi_id, amount, currency, payment_method, status,
            transaction_timestamp, settlement_date, gateway_reference, bank_reference,
            fee, tax, net_amount) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (txn_id, payment_id, merchant_id, customer_id, upi_id, amount, "INR",
             method, status, txn_time, settlement_date, gateway_ref, bank_ref,
             fee, tax, net_amount))

        if exc == "DUPLICATE_TRANSACTION":
            dup_txn_id = f"TXN-{1000 + i}-DUP"
            cur.execute("""INSERT INTO payments (transaction_id, payment_id, merchant_id,
                customer_id, upi_id, amount, currency, payment_method, status,
                transaction_timestamp, settlement_date, gateway_reference, bank_reference,
                fee, tax, net_amount) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (dup_txn_id, payment_id, merchant_id, customer_id, upi_id, amount, "INR",
                 method, status, txn_time, settlement_date, gateway_ref, bank_ref,
                 fee, tax, net_amount))

        # ---- Settlement record ----
        settlement_id = f"STL-{4000 + i}"
        s_gross, s_fee, s_tax, s_net = amount, fee, tax, net_amount
        s_date = settlement_date
        s_status = "SETTLED"
        s_bank_ref = bank_ref

        if exc == "AMOUNT_MISMATCH":
            s_gross = round(amount - (50 + (i % 5) * 17.5), 2)
            s_net = round(s_gross - s_fee - s_tax, 2)
        elif exc == "FEE_MISMATCH":
            s_fee = round(fee + 35.0, 2)
            s_net = round(s_gross - s_fee - s_tax, 2)
        elif exc == "TAX_MISMATCH":
            s_tax = round(tax + 12.0, 2)
            s_net = round(s_gross - s_fee - s_tax, 2)
        elif exc == "SETTLEMENT_DELAY":
            s_date = _ts(i, offset_hours=24 + 96)  # 4 extra days
        elif exc == "PARTIAL_SETTLEMENT":
            s_gross = round(amount * 0.6, 2)
            s_fee = round(s_gross * 0.02, 2)
            s_tax = round(s_fee * 0.18, 2)
            s_net = round(s_gross - s_fee - s_tax, 2)
            s_status = "PARTIALLY_SETTLED"
        elif exc == "REFERENCE_MISMATCH":
            s_bank_ref = f"BNK{999000 + i}"  # does not match payment's bank_ref
        elif exc == "STATUS_MISMATCH":
            s_status = "FAILED"

        if exc != "MISSING_SETTLEMENT":
            cur.execute("""INSERT INTO settlements (settlement_id, transaction_id, merchant_id,
                settlement_reference, gross_amount, fee, tax, net_amount, settlement_date,
                settlement_status, bank_reference) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (settlement_id, txn_id, merchant_id, f"SREF{i}", s_gross, s_fee, s_tax,
                 s_net, s_date, s_status, s_bank_ref))

            if exc == "DUPLICATE_SETTLEMENT":
                dup_settlement_id = f"STL-{4000 + i}-DUP"
                cur.execute("""INSERT INTO settlements (settlement_id, transaction_id, merchant_id,
                    settlement_reference, gross_amount, fee, tax, net_amount, settlement_date,
                    settlement_status, bank_reference) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (dup_settlement_id, txn_id, merchant_id, f"SREF{i}-DUP", s_gross, s_fee, s_tax,
                     s_net, s_date, s_status, s_bank_ref))

        # ---- Ledger record ----
        ledger_id = f"LED-{5000 + i}"
        l_amount, l_tax, l_fee = net_amount, tax, fee
        l_status = "POSTED"

        if exc == "LEDGER_MISMATCH":
            l_amount = round(net_amount - 40.0, 2)

        cur.execute("""INSERT INTO ledger_entries (ledger_id, transaction_id, merchant_id,
            debit, credit, ledger_amount, tax_amount, fee_amount, entry_date,
            ledger_status, reference) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (ledger_id, txn_id, merchant_id, 0.0, l_amount, l_amount, l_tax, l_fee,
             txn_time, l_status, gateway_ref))

    # ---- One genuinely orphan settlement (UNKNOWN_TRANSACTION) ----
    if 130 in EXCEPTION_RECIPE.values() or True:
        cur.execute("""INSERT INTO settlements (settlement_id, transaction_id, merchant_id,
            settlement_reference, gross_amount, fee, tax, net_amount, settlement_date,
            settlement_status, bank_reference) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("STL-9999", "TXN-UNKNOWN-9999", "MER003", "SREF-ORPHAN", 3200.0, 64.0,
             11.52, 3124.48, _ts(130, 24), "SETTLED", "BNK-ORPHAN-9999"))

    conn.commit()
    conn.close()
    return TOTAL_TRANSACTIONS


if __name__ == "__main__":
    from database import init_db
    init_db(reset=True)
    n = generate_and_load()
    print(f"Seeded {n} transactions with {len(EXCEPTION_RECIPE)} injected exceptions.")
