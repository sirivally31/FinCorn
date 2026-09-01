import seed
from database import get_connection

def get_ground_truth():
    gt = {}
    for i in range(1, seed.TOTAL_TRANSACTIONS + 1):
        txn_id = f"TXN-{1000 + i}"
        exc = seed.EXCEPTION_RECIPE.get(i)
        
        if exc is None:
            gt[txn_id] = {"match_status": "MATCHED", "exception_type": None}
        elif exc in ("FEE_MISMATCH", "TAX_MISMATCH", "SETTLEMENT_DELAY"):
            gt[txn_id] = {"match_status": "AUTO_RESOLVED", "exception_type": exc}
        elif exc == "DUPLICATE_TRANSACTION":
            gt[txn_id] = {"match_status": "MATCHED", "exception_type": None}
            gt[f"{txn_id}-DUP"] = {"match_status": "UNRESOLVED", "exception_type": "DUPLICATE_RECORD"}
        elif exc == "DUPLICATE_SETTLEMENT":
            gt[txn_id] = {"match_status": "UNRESOLVED", "exception_type": "DUPLICATE_RECORD"}
        elif exc == "UNKNOWN_TRANSACTION":
            gt[txn_id] = {"match_status": "MATCHED", "exception_type": None}
        else:
            gt[txn_id] = {"match_status": "UNRESOLVED", "exception_type": exc}
            
    if 130 in seed.EXCEPTION_RECIPE.values() or True:
        gt["TXN-UNKNOWN-9999"] = {"match_status": "UNRESOLVED", "exception_type": "UNKNOWN_TRANSACTION"}
        
    return gt

def run_evaluation():
    conn = get_connection()
    cur = conn.cursor()
    recons = [dict(r) for r in cur.execute("SELECT * FROM reconciliations").fetchall()]
    conn.close()
    
    gt = get_ground_truth()
    
    total = len(recons)
    correct = 0
    incorrect = 0
    false_matches = 0
    missed_exceptions = 0
    unresolved_exceptions = 0
    matched = 0
    auto_resolved = 0
    
    for r in recons:
        txn_id = r["transaction_id"]
        actual_status = r["match_status"]
        actual_type = r["exception_type"]
        
        if actual_status == "MATCHED":
            matched += 1
        elif actual_status == "AUTO_RESOLVED":
            auto_resolved += 1
        elif actual_status == "UNRESOLVED":
            unresolved_exceptions += 1

        expected = gt.get(txn_id)
        if expected is None:
            incorrect += 1
            if actual_status in ("UNRESOLVED", "AUTO_RESOLVED"):
                false_matches += 1
            continue
            
        expected_status = expected["match_status"]
        expected_type = expected["exception_type"]
        
        is_correct = True
        
        if actual_status != expected_status:
            is_correct = False
            
        if expected_status != "MATCHED":
            if actual_type != expected_type:
                is_correct = False
                
        if is_correct:
            correct += 1
        else:
            incorrect += 1
            expected_is_exception = expected_status in ("UNRESOLVED", "AUTO_RESOLVED")
            actual_is_exception = actual_status in ("UNRESOLVED", "AUTO_RESOLVED")
            
            if expected_is_exception and not actual_is_exception:
                missed_exceptions += 1
            elif not expected_is_exception and actual_is_exception:
                false_matches += 1
                
    accuracy = round((correct / total) * 100, 2) if total > 0 else 0.0
    match_rate = round(((matched + auto_resolved) / total) * 100, 2) if total > 0 else 0.0
    
    return {
        "totalRecords": total,
        "correctClassifications": correct,
        "incorrectClassifications": incorrect,
        "accuracy": accuracy,
        "matchRate": match_rate,
        "falseMatches": false_matches,
        "missedExceptions": missed_exceptions,
        "unresolvedExceptions": unresolved_exceptions,
        "matchedRecords": matched,
        "autoResolvedRecords": auto_resolved
    }
