import sys; sys.path.append('e:/finrecon-ai/backend')
import database, seed, reconciliation, evaluation
database.init_db(True)
seed.generate_and_load()
reconciliation.run_reconciliation()
gt = evaluation.get_ground_truth()
cur = database.get_connection().cursor()
recons = cur.execute('SELECT * FROM reconciliations').fetchall()
with open("e:/finrecon-ai/backend/debug_out.txt", "w") as f:
    for r in recons:
        tid = r['transaction_id']
        g = gt.get(tid, {})
        has_err = False
        if r['match_status'] != g.get('match_status'):
            has_err = True
        elif g.get('match_status') != 'MATCHED' and r['exception_type'] != g.get('exception_type'):
            has_err = True
        
        if has_err:
            f.write(f"{tid} Expected: {g.get('match_status')} / {g.get('exception_type')}  Actual: {r['match_status']} / {r['exception_type']}\n")
