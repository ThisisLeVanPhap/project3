# Docker / VPS Smoke Checklist

## Local Docker Smoke

### 1. Services
```bash
docker compose ps
# Expected: 3 containers running (app, chatbot-api, postgres)
```

### 2. Health
```bash
# Backend
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/login
# Expected: 405 (method not allowed — but reachable)

# FastAPI
curl -s http://localhost:8000/healthz | python -c "import sys,json; d=json.load(sys.stdin); print('ready:', d.get('ready'))"
# Expected: ready: True

# Admin login
curl -s -c /tmp/cookies.txt -X POST http://localhost:8080/api/login \
  -H "Content-Type: application/json" \
  -d '{"name":"admin","code":"admin123"}'
# Expected: ok:true, role:PLATFORM_ADMIN
```

### 3. Data
```bash
# General data via quality summary
curl -s -b /tmp/cookies.txt http://localhost:8080/api/admin/general/quality-summary | \
  python -c "import sys,json; d=json.load(sys.stdin); print(d['totalProducts'], 'products,', d['sourceCount'], 'sources')"
# Expected: ~6070 products, 1+ sources
```

### 4. Quick Smoke Script
```bash
python scripts/eval/docker_smoke_check.py
# Expected: All checks PASS or SKIP (KB loaded may be false — expected)
```

### 5. Eval Scripts
```bash
python scripts/eval/run_all_eval_scenarios.py
# Expected: 29 pass, 0 fail, 0 skip
```

## VPS Smoke

### 1. Required Environment Variables
| Variable | Required | Default | Description |
|---|---|---|---|
| `POSTGRES_DB` | Yes | `global_admin` | Database name |
| `POSTGRES_USER` | Yes | `postgres` | Database user |
| `POSTGRES_PASSWORD` | Yes | — | Database password |
| `INTERNAL_API_SECRET` | **Yes (production)** | `` | Protects internal APIs |
| `CLAUDER_API_KEY` / `ANTHROPIC_API_KEY` | If using Claude | — | LLM API key |
| `INSTALL_LOCAL_AI` | No | `false` | Keep false for VPS 6GB |
| `BACKEND_BASE_URL` | No | `http://app:8080` | Used by chatbot-api internally |

### 2. Deployment
```bash
# Pull latest code
git pull

# Start all services
INSTALL_LOCAL_AI=false docker compose up -d --build

# Check services
docker compose ps
docker compose logs --tail=50 app
docker compose logs --tail=50 chatbot-api

# Wait for Flyway migrations (check logs for "Successfully applied" or "up to date")
```

### 3. Post-Deployment Checks
```bash
# Backend health
curl -s http://localhost:8080/api/login

# Admin login
curl -s -c /tmp/vps-cookies.txt -X POST http://localhost:8080/api/login \
  -H "Content-Type: application/json" \
  -d '{"name":"admin","code":"admin123"}'

# Internal APIs (if INTERNAL_API_SECRET set)
curl -s -H "X-Internal-Api-Key: YOUR_SECRET" \
  "http://localhost:8080/api/internal/general-products/search?q=sofa&limit=3"

# General data
curl -s -b /tmp/vps-cookies.txt http://localhost:8080/api/admin/general/quality-summary
```

### 4. Run Eval (from host machine)
```bash
BACKEND_BASE_URL=http://VPS_IP:8080 \
CHATBOT_BASE_URL=http://VPS_IP:8000 \
ADMIN_USERNAME=admin \
ADMIN_PASSWORD=admin123 \
INTERNAL_API_SECRET=YOUR_SECRET \
  python scripts/eval/run_all_eval_scenarios.py
```

### 5. Memory Check
```bash
docker stats --no-stream
# Expected (with INSTALL_LOCAL_AI=false):
#   app: ~400-500MB
#   chatbot-api: ~50-100MB
#   postgres: ~50-100MB
#   Total: ~600-700MB (well within 6GB VPS)
```

## Troubleshooting

### INTERNAL_API_SECRET not set
- Backend logs warning: "INTERNAL_API_SECRET is not configured; /api/internal/ endpoints are OPEN"
- Set env for both `app` and `chatbot-api` services in docker-compose.yml

### torch missing (expected)
```bash
python -c "import torch"
# ModuleNotFoundError — this is correct for lightweight deploy
```

### tenant.kbDir is legacy
- Source-of-truth: `activeKbVersionId` → `TenantKbVersion.kbDir`
- `tenant.kbDir` is fallback only
- Rebuild/bind will create `TenantKbVersion` and set `activeKbVersionId`

### FastAPI KB loaded = false
- KB_DIR points to `/app/kb/article` by default
- This is expected when no tenant RAG data is mounted
- Does not affect general_compare or market_price

### Eval scripts time out
- Increase `EVAL_TIMEOUT_SECONDS` env var (default 30)
- Check if backend/FastAPI are actually reachable
- Check if INTERNAL_API_SECRET matches

### UI static inaccessible
- Check if Spring Boot is serving static content
- Verify `/admin/` returns 200 (not 401)

## Architecture Reminders

```
data_pipeline (Python)
  → crawl, enrich, dedupe, rag_export, materialize, quality_audit, taxonomy

Spring Boot (Java)
  → ProductDataset Registry, Artifact, Binding, General Data Layer, Scope Resolver

FastAPI (Python)
  → tenant_sales (uses active KB), general_compare (uses general_products via backend),
    market_price (uses general_products aggregate via backend)
```
