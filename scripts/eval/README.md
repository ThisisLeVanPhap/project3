# Eval Scenarios

Eval scripts for 3 capabilities: general_compare, market_price, tenant_sales.

## Prerequisites

- Backend (Spring Boot) running at `BACKEND_BASE_URL` (default `http://localhost:8080`)
- FastAPI chatbot running at `CHATBOT_BASE_URL` (default `http://localhost:8000`)
- General Data Layer must have imported data (gotrangtri 6070 products)
- Admin account `admin` / `admin123`
- If `INTERNAL_API_SECRET` is set on backend, set same value in env

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BACKEND_BASE_URL` | `http://localhost:8080` | Spring Boot backend |
| `CHATBOT_BASE_URL` | `http://localhost:8000` | FastAPI chatbot |
| `ADMIN_USERNAME` | `admin` | Admin login |
| `ADMIN_PASSWORD` | `admin123` | Admin password |
| `INTERNAL_API_SECRET` | `` | Internal API secret if configured |
| `EVAL_TIMEOUT_SECONDS` | `30` | Request timeout |

## Commands

```bash
# All scenarios
python scripts/eval/run_all_eval_scenarios.py

# Individual mode
python scripts/eval/test_general_compare_scenarios.py
python scripts/eval/test_market_price_scenarios.py
python scripts/eval/test_tenant_sales_scenarios.py
```

## Expected Output

- Terminal: PASS/FAIL/SKIP per scenario with summary
- Evidence files in `tmp/eval/`:
  - `general_compare_results.json`
  - `market_price_results.json`
  - `tenant_sales_results.json`
  - `eval_summary.json`

## Notes

- Tenant sales scenarios require at least one tenant with `activeKbVersionId` set.
- If no tenant has active KB, tenant sales scenarios are skipped with clear message.
- Backend unavailable → all scenarios skipped (no silent failures).
