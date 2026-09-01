import re

with open('e:/finrecon-ai/README.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update title for Why AI Finance Controller
content = content.replace("## 2. Solution", "## 2. Solution\n\n## 3. Why AI Finance Controller\nThe AI Finance Controller track asks to 'run the books and the cash position'. FinRecon AI directly addresses this by ensuring no payments are blindly marked as 'resolved' by LLMs. It focuses on closing the gap between raw unstructured payment trails and the actual cash ledger, generating the necessary insights for real finance operations.\n\n## Data Flow\n")
content = content.replace("## Data Flow\n", "## 5. Data flow\n")

# rename 3 to 9. Exact measured results
content = content.replace("## 3. Actual measured results (last verified run)", "## 9. Exact measured results from the latest run")

# rename 4 to 4. Architecture
# It is already "## 4. Architecture"

# 6. Reconciliation engine -> 6. Reconciliation methodology
content = content.replace("## 6. Reconciliation engine", "## 6. Reconciliation methodology")

# 7. AI layer -> 7. AI methodology
content = content.replace("## 7. AI layer", "## 7. AI methodology")

# Add "8. Evaluation methodology" before 9
content = content.replace("## 9. Exact measured results", "## 8. Evaluation methodology\nEvaluation evaluates match rate, accuracy, and processing throughput using identical deterministic seeded synthetic constraints. The ground-truth exception list allows us to objectively categorize each AI explanation and verify zero false-positive resolutions.\n\n## 9. Exact measured results")

# Add "10. Known unresolved exceptions", "11. Razorpay Test Mode integration", "12. Environment variables" before "## 10. Running it"
content = content.replace("## 10. Running it", "## 10. Known unresolved exceptions\nThe demo intentionally creates unresolved exceptions covering issues that require real human intervention: missing settlements from the bank, unknown transactions that never reached the payment layer, partial settlements, massive reference/status mismatch, etc.\n\n## 11. Razorpay Test Mode integration\nFinRecon AI features a secure backend-only validation for Razorpay keys restricted specifically to Test Mode logic (checking the `rzp_test_` prefix). If credentials are authenticated, they are used strictly offline.\n\n## 12. Environment variables\n- `RAZORPAY_KEY_ID`: Razorpay Test Mode Key IF (must start with `rzp_test_`)\n- `RAZORPAY_KEY_SECRET`: Razorpay Test Mode Secret\n- `AI_PROVIDER`: `mock` (default) or `openai`\n- `OPENAI_API_KEY`: Required only if `openai` provider is used.\n- `OPENAI_MODEL`: Model name (default `gpt-4o-mini`)\n\n## 13. Local setup")

# Rename "11. API reference" -> "15. API endpoints"
content = content.replace("## 11. API reference", "## 15. API endpoints")

# Rename "12. Testing" -> part of Evaluation methodology? Wait, it's 12. Testing. Let's make demo instructions #14. 
content = content.replace("### Reset the demo", "## 14. Demo instructions\nTo reset the demo to its ground-truth standard state, click **\"Reset Demo\"** in the UI, or:")

# Rename "13. Limitations (stated honestly)" to "16. Limitations"
content = content.replace("## 13. Limitations (stated honestly)", "## 16. Limitations")

# "Production notes" under 4 -> ## 17. Production architecture
content = content.replace("### Production notes (for porting to Spring Boot / React / Postgres)", "## 17. Production architecture")

# Add "18. Security notes" at the end
content = content.replace("## 14. Future improvements", "## 18. Security notes\n- Secrets are never committed (`.env` is gitignored).\n- Razorpay and OpenAI integrations operate 100% backend-side.\n- No keys are exposed in the frontend or REST API payloads.\n- Test mode is strictly enforced for real keys.\n- No database credentials exist (SQLite runs locally mode).\n\n## Future improvements")

with open('e:/finrecon-ai/README.md', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated README.md")
