# Project Status

## 1. Current Runtime Architecture
- Docker services hiện tại: `postgres`, `chatbot-api`, `app`
- Spring gọi Python qua `PYTHON_LLM_BASE_URL` (external HTTP mode)
- Postgres dùng Flyway migration để quản lý schema
- Qwen local là fallback/local mode (có thể timeout 120s trên CPU-only)
- Claude provider đã có sẵn trong code nhưng cần API key Anthropic hợp lệ
- Stub/mock mode dùng cho fast verification (không phải real generation)

## 2. Completed Work
- RAG `/chat` nối retrieval context vào prompt
- Stub test mode với debug trace đầy đủ
- 3 modes: `tenant_sales`, `general_compare`, `market_price`
- Java/Spring mode contract qua `GenerationConfig`
- `/price-check` UI và backend flow
- Runtime hygiene Docker (env vars, health checks, volumes)
- Provider layer 4A: `InternalCatalogProvider`, `MockMarketPriceProvider`, `ExternalPriceProvider`
- Response formatting cho `general_compare` và `market_price` với cấu trúc ổn định
- API key handling docs/config (.env, .gitignore, RUN_LOCAL.md)
- Claude error instrumentation để debug upstream failures

## 3. Verified Tests / Evidence
- Python targeted tests: `tests/test_server_rag_stub.py` + `tests/test_market_data_providers.py` = **11 passed**
- Docker stack từng verify pass: `postgres`, `chatbot-api`, `app`
- `/price-check` sends `mode=market_price`
- `general_compare`/`market_price` không tạo purchase request/lead
- Claude container nhận được `ANTHROPIC_API_KEY` (boolean true, len=40)
- Claude upstream trả `401 authentication_error` với key hiện tại: `invalid x-api-key`

## 4. Current Blockers
- **Qwen local Docker timeout 120s** trên máy không có GPU, không phù hợp làm demo chính
- ~~**Claude provider key hiện tại không hợp lệ** cho endpoint `https://api.anthropic.com/v1/messages`~~
  - ~~Error đã xác nhận: `401 authentication_error`~~
- ~~**general_compare Claude chưa pass** vì upstream reject key~~
- ~~**market_price Claude từng pass** trong một lần trước khi có instrumentation, nhưng cần re-test sau khi thay key hợp lệ~~

## 5. Phase 1 Complete - Claude Direct API Verified (2026-05-19)
- Claude provider gọi được Anthropic chính chủ với key chính chủ.
- Model thực tế: `claude-sonnet-4-6`.
- Direct Python `/chat` with `provider=claude`:
  - `market_price`: **PASS**
  - `general_compare`: **PASS**
- Lỗi `401 invalid x-api-key` đã hết sau khi dùng key chính chủ.
- Đã sửa `server.py` (line 102-111) để Claude request chỉ gửi `temperature` HOẶC `top_p`, không gửi cả hai.
- Targeted tests: **11 passed**.

## 6. Recommended Next Steps - Phase 2
- Cleanup per-chatbot `apiKey`/`apiBaseUrl`/`apiModel` khỏi UI/API/DB.
- Claude provider dùng env hệ thống (`CLAUDE_API_KEY`, `CLAUDE_MODEL`, `CLAUDE_API_BASE_URL`).

## 5. Important Implementation Notes
- Code ưu tiên provider key theo thứ tự:
  1. `cfg.api_key` (from chatbot_instance DB)
  2. `CLAUDE_API_KEY` (env)
  3. `ANTHROPIC_API_KEY` (env)
- DB hiện không có `api_key` override cho các bot đã kiểm tra (`general_compare`, `tenant_sales`, `market_price`)
- Khuyến nghị: DB chỉ lưu `provider=claude` và `apiModel`, **không lưu API key thật**
- `.env` và `.claude/` phải nằm trong `.gitignore`
- **Không được commit .env**
- Claude instrumentation hiện tại (`_call_claude_api` trả tuple + `debug.claude_error`) có thể giữ để debug hoặc revert sau khi key ổn định

## 6. Phase 2 Round 1 Complete - Claude System-Level Provider (2026-05-20)
- UI: đã xóa/hide input `botApiModel`, `botApiKey`, `botApiBaseUrl` ở admin chatbot form.
- Java CRUD: giữ DTO fields để backward compatibility nhưng không persist `apiModel/apiKey/apiBaseUrl` nữa.
- Java runtime: không forward per-chatbot Claude config xuống Python; các field này luôn được set `null`.
- Python: Claude provider chỉ lấy config từ env: `ANTHROPIC_API_KEY`/`CLAUDE_API_KEY`, `CLAUDE_MODEL`, `CLAUDE_API_BASE_URL`. Không dùng `cfg.api_key`/`cfg.api_model`/`cfg.api_base_url`.
- Migration numbering:
  - `V22__add_lead_created_to_conversations.sql` là migration gốc hợp lệ, giữ nguyên.
  - Migration Phase 2 đúng là `V26__null_chatbot_api_fields_for_system_claude.sql`.
  - `V26` dùng để null legacy `api_key`/`api_model`/`api_base_url`, chưa drop columns.
- Docker: `chatbot-api` đã thêm `init: true` để tránh zombie process.
- ✅ Flyway V26 verified: version=26, description="null chatbot api fields for system claude", success=true.
- ✅ Legacy fields verified: `api_key`/`api_model`/`api_base_url` đều NULL (false) trong `chatbot_instances`.
- ✅ App boot verified: Started successfully.
- ✅ Direct Python /chat provider=claude: PASS (market_price + general_compare).
- ✅ Spring route general_compare: PASS.
- ✅ Spring route market_price: PASS.
- ✅ No purchase request side effect: PASS.
- Runtime verified:
  - provider=claude
  - model=claude-sonnet-4-6
  - pythonRuntimeMode=external_http
- DB demo update:
  - `general_compare` bot: provider=claude
  - `market_price` bot: created with provider=claude
- Docs: cập nhật PROJECT_STATUS.md, RUN_LOCAL.md, .env.example cho system-level Claude.
- TODO Round 2 (optional): Drop columns `api_key`, `api_model`, `api_base_url` khỏi `chatbot_instances` sau khi compatibility window closes.

## 7. Implementation Notes
- Claude uses system-level env only:
  - `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY`
  - `CLAUDE_MODEL` (default: claude-sonnet-4-6)
  - `CLAUDE_API_BASE_URL` (default: https://api.anthropic.com)
- DB columns `api_key`, `api_model`, `api_base_url` tạm thời còn tồn tại nhưng đã được null và sẽ drop ở Phase 2 Round 2 (optional).
- `.env` và `.claude/` phải nằm trong `.gitignore`
- **Không được commit .env**
- **Claude API requirement**: chỉ gửi `temperature` HOẶC `top_p`, không gửi cả hai (fixed in server.py)

## 8. How To Resume In A New Claude/Codex Thread
"Continue from docs/PROJECT_STATUS.md. Phase 2 Round 1 complete and fully verified end-to-end: Claude is now system-level provider with env-only config. UI and Java no longer accept/persist per-chatbot API fields. Python resolves from ANTHROPIC_API_KEY/CLAUDE_API_KEY, CLAUDE_MODEL, CLAUDE_API_BASE_URL. All verifications PASS: Direct Python /chat, Flyway V26, legacy fields NULL, app boot, Spring routes (general_compare + market_price), no purchase side effects. Runtime: provider=claude, model=claude-sonnet-4-6, pythonRuntimeMode=external_http. `V22__add_lead_created_to_conversations.sql` remains valid; Phase 2 uses `V26__null_chatbot_api_fields_for_system_claude.sql`. DB demo bots updated to provider=claude. Next: Phase 2 Round 2 (optional) can drop DB columns if stable. Keep scope tight."

## 9. Files Touched Recently
- `chatbot/app/server.py` — Claude env-only resolution, temperature/top_p fix, VPS CPU-only lazy load
- `chatbot/app/modes.py` — Mode system instructions, formatting requirements
- `chatbot/app/market_data.py` — Provider layer, mock price provider
- `chatbot/app/data/mock_market_prices.demo.json` — Mock price references
- `chatbot/tests/test_server_rag_stub.py` — Stub-mode tests
- `chatbot/tests/test_market_data_providers.py` — Provider tests
- `docker-compose.yml` — Env propagation, CLAUDE_MAX_NEW_TOKENS, LOCAL_FALLBACK_MAX_TOKENS, FALLBACK_TO_LOCAL_ENABLED
- `.env.example` — Documented Claude key handling, VPS CPU-only settings
- `.gitignore` — Added `.env` and `.claude/`
- `docs/RUN_LOCAL.md` — Claude demo mode documentation, VPS deployment notes
- `docs/PROJECT_STATUS.md` — Phase 1 complete, Phase 2 Round 1 complete status, VPS CPU-only deployment
- `multitenant/src/main/java/com/app/bots/ChatbotController.java` — Ignore per-chatbot Claude config
- `multitenant/src/main/java/com/app/modelserver/PythonChatClient.java` — Stop forwarding DB Claude config
- `multitenant/src/main/resources/static/admin/index.html` — Removed Claude per-chatbot fields
- `multitenant/src/main/resources/static/admin/app.js` — Removed Claude per-chatbot payload handling
- `multitenant/src/main/resources/db/migration/V26__null_chatbot_api_fields_for_system_claude.sql` — Null legacy `api_key`/`api_model`/`api_base_url` only; columns remain for now

## 10. VPS CPU-Only Deployment Notes
- **Eager load behavior**: chatbot-api now skips Qwen/local model warmup when Claude API key is present and `FALLBACK_TO_LOCAL_ENABLED=false`
- **Lazy load**: Local model only loads on-demand when `provider=local` is explicitly requested
- **Env vars for VPS**:
  - `FALLBACK_TO_LOCAL_ENABLED=false` — Disable local fallback on CPU-only VPS
  - `CLAUDE_MAX_NEW_TOKENS=768` — Higher token limit for Claude
  - `LOCAL_FALLBACK_MAX_TOKENS=128` — Lower token limit for Qwen fallback (if enabled)
  - `LOCAL_FALLBACK_TIMEOUT_SECONDS=45` — Timeout for local fallback requests
- **Startup logs**: When Claude is available, `[warmup] Claude API available, skipping local model warmup`
- **No Qwen download**: On VPS CPU-only with Claude, no model download occurs at startup