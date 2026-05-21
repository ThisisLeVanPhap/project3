# Runtime And Local Runbook

This project now treats the Python chatbot as a separate runtime service.
Spring Boot should call it through `PYTHON_LLM_BASE_URL` in Docker and in
normal local development. The old spawned Python process mode is kept only as
a fallback for local debugging.

## Verified Runtime Status

Last verified: 2026-05-19.

- Docker Compose runs three main services: `postgres`, `chatbot-api`, and `app`.
- Spring calls Python through `PYTHON_LLM_BASE_URL`.
- Spawned Python is only a local development fallback when `PYTHON_LLM_BASE_URL`
  is not set.
- Docker and IntelliJ-with-`chatbot-api` do not need `PYTHON_BIN`,
  `MODEL_SERVER_DIR`, or a local HuggingFace snapshot path.
- Default `BASE_MODEL` is `Qwen/Qwen2.5-1.5B-Instruct`.
- Database schema is managed by Flyway; verified through migration `V25`.
- `/price-check` sends `mode=market_price` and does not create leads or purchase
  requests.

## Docker Compose

1. Create a local env file from the template:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Fill local-only secrets in `.env` as needed.

   For Claude demo mode, set:

   ```text
   ANTHROPIC_API_KEY=your-local-key
   # or
   CLAUDE_API_KEY=your-local-key
   ```

   Do not commit `.env`. If a key is exposed, rotate it in Anthropic and update
   your local `.env`.

3. Start the full stack:

   ```powershell
   docker compose up --build
   ```

4. Open:

   - Spring app: `http://localhost:8080`
   - Python health: `http://localhost:8000/healthz`

In Docker, Spring uses:

```text
SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/global_admin
PYTHON_LLM_BASE_URL=http://chatbot-api:8000
```

That means the app container uses the Compose `postgres` and `chatbot-api`
services, not local Windows paths or a local Windows database.

## Claude System-Level Provider

Claude is now a system-level provider. API key/model/base URL are resolved from
system environment only, not from per-chatbot configuration.

1. Put a local-only key in `.env`:

   ```text
   ANTHROPIC_API_KEY=your-local-key
   # or
   CLAUDE_API_KEY=your-local-key
   ```

   `CLAUDE_MODEL` defaults to `claude-sonnet-4-6`.
   `CLAUDE_API_BASE_URL` defaults to `https://api.anthropic.com`.

2. Create a chatbot with `provider=claude`. Do not enter per-chatbot API fields
   in the admin UI — they no longer exist.

3. Keep `PYTHON_LLM_BASE_URL` pointing at the Python service as usual.

Notes:
- Per-chatbot `apiKey`, `apiModel`, and `apiBaseUrl` fields have been removed from
  the admin UI and are no longer persisted or used at runtime.
- Legacy DB columns remain temporarily but are nulled and scheduled for removal.
- Stub/mock mode is for fast verification, not real Claude generation.

## Real Qwen Mode

Use this for normal local Docker runs when you want the actual model path:

```text
CHATBOT_TEST_MODE=0
MARKET_PRICE_PROVIDER=
CHATBOT_BASE_MODEL=Qwen/Qwen2.5-1.5B-Instruct
```

With these defaults, `market_price` only uses the mock provider if you opt in
explicitly through environment variables.

## Mock Verification Mode

Use this only for fast verification of the Docker/Spring/Python market-price
provider path:

```text
CHATBOT_TEST_MODE=1
MARKET_PRICE_PROVIDER=mock
```

Or keep `CHATBOT_TEST_MODE=0` and enable only the mock provider:

```text
USE_MOCK_MARKET_PRICE=1
```

Mock/test mode is not appropriate for a production-like demo when you want real
Claude or Qwen generation.

## IntelliJ Local Spring

Recommended setup:

1. Start dependencies only:

   ```powershell
   docker compose up -d postgres chatbot-api
   ```

2. Run Spring Boot from IntelliJ with these environment variables:

   ```text
   SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/global_admin
   SPRING_DATASOURCE_USERNAME=postgres
   SPRING_DATASOURCE_PASSWORD=admin
   PYTHON_LLM_BASE_URL=http://localhost:8000
   ANTHROPIC_API_KEY=your-local-key
   ```

Do not set `PYTHON_BIN`, `MODEL_SERVER_DIR`, or a HuggingFace snapshot path for
this mode.

## Local Spawn Fallback

Use this only when you intentionally want Spring to start Python itself:

```text
PYTHON_LLM_BASE_URL=
PYTHON_BIN=python
MODEL_SERVER_DIR=../chatbot
```

If `PYTHON_LLM_BASE_URL` is set, Spring will use external HTTP mode and will not
spawn Python.

## Model Configuration

Default local model:

```text
CHATBOT_BASE_MODEL=Qwen/Qwen2.5-1.5B-Instruct
```

Claude system-level env:

```text
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_API_BASE_URL=https://api.anthropic.com
```

Do not commit machine-specific HuggingFace snapshot paths.

## Reset Dev Database

This deletes the Compose database volume:

```powershell
docker compose down -v
docker compose up --build
```

Flyway will recreate the schema on app startup.

## Verify Runtime

Check containers:

```powershell
docker compose ps
docker compose logs chatbot-api --tail=100
docker compose logs app --tail=100
docker compose logs postgres --tail=100
```

Expected Spring log when using Docker:

```text
LLM runtime selected mode=external_http ... baseUrl=http://chatbot-api:8000
```

There should be no lookup for `python.exe` and no `TinyLlama` model selection.

## Verify Price Check

Open:

```text
http://localhost:8080/price-check/
http://localhost:8080/chat/price-check/
```

API smoke test:

```powershell
$body = @{ userExternalId = "dev-price-check"; mode = "market_price" } | ConvertTo-Json
$start = Invoke-RestMethod -Method Post -Uri "http://localhost:8080/api/general/chat/start" -ContentType "application/json" -Body $body

$sendBody = @{
  userExternalId = "dev-price-check"
  conversationId = $start.conversationId
  message = "Gia sofa SFG041 khoang bao nhieu la hop ly?"
  mode = "market_price"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8080/api/general/chat/send" -ContentType "application/json" -Body $sendBody
```

Expected app log:

```text
requestedMode=market_price finalMode=market_price ... pythonRuntimeMode=external_http
```

Check Flyway and chatbot records:

```powershell
docker compose exec postgres psql -U postgres -d global_admin -c "select version, description, success from flyway_schema_history order by installed_rank desc limit 5;"
docker compose exec postgres psql -U postgres -d global_admin -c "select id, mode, provider, base_model from chatbot_instances where mode in ('general_compare', 'market_price', 'general_consumer') order by mode;"
```

## VPS CPU-Only Deployment

For VPS deployment using Claude API as primary provider (no local model):

```text
ANTHROPIC_API_KEY=your-claude-api-key
FALLBACK_TO_LOCAL_ENABLED=false
CLAUDE_MAX_NEW_TOKENS=768
LOCAL_FALLBACK_MAX_TOKENS=128
LOCAL_FALLBACK_TIMEOUT_SECONDS=45
LOCAL_PIPELINE_MAX_CACHE=2
LOCAL_PIPELINE_IDLE_TTL_SECONDS=180
LOCAL_PIPELINE_CLEANUP_INTERVAL_SECONDS=30
```

With `FALLBACK_TO_LOCAL_ENABLED=false` and Claude API key set:
- chatbot-api skips Qwen model warmup at startup
- No model download occurs
- Server starts quickly (under 30s)
- Local model only loads if `provider=local` is explicitly requested
- If Qwen/local is loaded, the in-process pipeline cache keeps at most 2 entries
- Idle local pipelines are unloaded after 180 seconds by a 30-second cleanup loop

Expected startup log when Claude is available:

```text
[warmup] Claude API available, skipping local model warmup (lazy load on provider=local)
```

To enable local fallback on VPS (requires GPU or slow CPU inference):

```text
FALLBACK_TO_LOCAL_ENABLED=true
LOCAL_FALLBACK_TIMEOUT_SECONDS=120
LOCAL_PIPELINE_MAX_CACHE=2
LOCAL_PIPELINE_IDLE_TTL_SECONDS=180
LOCAL_PIPELINE_CLEANUP_INTERVAL_SECONDS=30
```

With fallback enabled, server will warmup Qwen model at startup (may take 2-5 minutes on CPU).
After unload, Python/PyTorch memory may not return fully to the OS because of allocator behavior.
TODO Round 2: use a subprocess-based local worker when exact memory return is required.
