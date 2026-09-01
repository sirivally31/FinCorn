import sys
import json
sys.path.append('backend')
import seed
import reconciliation
import cash
from ai_provider import MockAIProvider
import database
database.init_db(reset=True)
seed.generate_and_load()
summary = reconciliation.run_reconciliation(ai_provider=MockAIProvider())
print(json.dumps(summary, indent=2))
