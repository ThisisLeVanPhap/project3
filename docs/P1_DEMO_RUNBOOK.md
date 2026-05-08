# P1 Demo Runbook

Ngày cập nhật: 2026-05-08  
Phạm vi: hướng dẫn chạy demo giữa kỳ dựa trên code hiện tại của repo. Các bước có `TODO` là dữ liệu phải điền hoặc chuẩn bị thủ công trước demo.

## 1. Cách khởi động hệ thống

### 1.1 Phương án khuyến nghị: Docker Compose

Từ thư mục root repo:

```powershell
cd F:\20251\prj3
docker compose up --build -d
```

Các service theo `docker-compose.yml`:

- `postgres`: PostgreSQL 16, mặc định DB `global_admin`, user `postgres`, password `admin`, port host `5432`.
- `app`: Spring Boot backend + UI, port host `8080`. Khi có request chat, Spring tự spawn Python runtime theo tenant trong cùng container app.
- `chatbot-api`: optional profile, chỉ dùng smoke test FastAPI trực tiếp trên port `8000`; backend mặc định không gọi service này.

Theo dõi trạng thái:

```powershell
docker compose ps
docker compose logs --no-color --tail=200 app
docker compose logs --no-color --tail=100 postgres
```

Dừng hệ thống:

```powershell
docker compose down
```

Chỉ khi muốn xóa cả database volume:

```powershell
docker compose down -v
```

Biến môi trường Docker Compose có căn cứ từ `docker-compose.yml`:

```powershell
$env:POSTGRES_DB="global_admin"
$env:POSTGRES_USER="postgres"
$env:POSTGRES_PASSWORD="admin"
$env:POSTGRES_PORT="5432"
$env:APP_PORT="8080"
$env:BASE_MODEL="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
$env:LLM_PORT_START="8101"
$env:LLM_PORT_END="8199"
$env:LLM_STARTUP_TIMEOUT_MS="600000"
$env:MESSENGER_VERIFY_TOKEN="woodchat_secret"
```

Lưu ý quan trọng cho Docker:

- Python runtime tenant chạy bên trong container `app`; `llmBaseUrl` kiểu `http://127.0.0.1:8101` là địa chỉ nhìn từ container app, không nhất thiết truy cập được trực tiếp từ host Windows.
- Tenant `kb_dir` trong DB phải là path container nhìn thấy, ví dụ `/opt/app/chatbot/kb/noithatcaco` hoặc `/opt/app/chatbot/kb/article`.
- `demo_multi_tenant_setup.sql` hiện ghi path Windows `F:/20251/...`; nếu import file đó để chạy Docker, cần update lại `kb_dir`.

Optional FastAPI smoke test trực tiếp:

```powershell
docker compose --profile chatbot-api up --build -d chatbot-api
curl.exe http://localhost:8000/healthz
```

`chatbot-api` dùng các biến:

```powershell
$env:CHATBOT_KB_DIR="/app/kb/noithatcaco"
$env:CHATBOT_BASE_MODEL="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
$env:CHATBOT_PORT="8000"
```

Messenger/Telegram không nằm trong kịch bản chính. Nếu muốn demo live channel, cần chuẩn bị thủ công:

- TODO: public HTTPS/ngrok URL.
- TODO: Messenger page access token hoặc Telegram bot token.
- TODO: binding page/bot với đúng tenant/chatbot.
- TODO: cấu hình webhook ngoài platform trỏ về `/webhook/messenger` hoặc `/webhook/telegram/{secretPath}`.

### 1.2 Phương án local: PostgreSQL + Spring Boot tự spawn Python runtime

Phương án này dùng PostgreSQL local hoặc container PostgreSQL, còn Spring Boot chạy bằng Maven trên host Windows.

Start PostgreSQL bằng Docker nếu chưa có PostgreSQL local:

```powershell
cd F:\20251\prj3
docker compose up -d postgres
```

Nếu dùng PostgreSQL local thật và database chưa tồn tại:

```powershell
psql -U postgres -c "CREATE DATABASE global_admin;"
```

Chuẩn bị Python cho chatbot:

```powershell
cd F:\20251\prj3\chatbot
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Chạy backend local:

```powershell
cd F:\20251\prj3\multitenant
$env:SPRING_DATASOURCE_URL="jdbc:postgresql://localhost:5432/global_admin"
$env:SPRING_DATASOURCE_USERNAME="postgres"
$env:SPRING_DATASOURCE_PASSWORD="admin"
$env:SERVER_PORT="8080"
$env:PYTHON_BIN="F:\20251\prj3\chatbot\.venv\Scripts\python.exe"
$env:MODEL_SERVER_DIR="F:\20251\prj3\chatbot"
$env:BASE_MODEL="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
$env:LLM_HOST="127.0.0.1"
$env:LLM_PORT_START="8101"
$env:LLM_PORT_END="8199"
$env:LLM_STARTUP_TIMEOUT_MS="600000"
mvn spring-boot:run
```

Lưu ý local:

- Spring sẽ tự chạy `python -m uvicorn app.server:app --host 127.0.0.1 --port <8101-8199>` khi có request chat.
- Nếu dùng tenant có `kb_dir` `/opt/app/...` từ Docker, local Windows sẽ không đọc được. Cần tạo tenant mới với `kbDir` Windows hoặc update DB path. TODO: chọn một cách trước demo.

Ví dụ update `kb_dir` cho local:

```powershell
psql -U postgres -d global_admin -c "UPDATE tenants SET kb_dir = 'F:/20251/prj3/chatbot/kb/noithatcaco' WHERE code = 'TODO_TENANT_CODE';"
```

### 1.3 Chạy Python service độc lập để smoke test

Backend mặc định không dùng service độc lập này, nhưng có thể chạy để kiểm tra `chatbot/app/server.py` và KB.

```powershell
cd F:\20251\prj3\chatbot
.\.venv\Scripts\Activate.ps1
$env:KB_DIR="F:\20251\prj3\chatbot\kb\noithatcaco"
$env:BASE_MODEL="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

Kiểm tra:

```powershell
curl.exe http://localhost:8000/healthz
```

## 2. Cách kiểm tra hệ thống đã sẵn sàng

### 2.1 URL UI cần mở

Backend/UI:

- Trang chủ static: `http://localhost:8080/`
- Login: `http://localhost:8080/login`
- Platform admin UI: `http://localhost:8080/admin`
- Tenant UI: `http://localhost:8080/tenant`
- Tenant purchase requests: `http://localhost:8080/tenant/purchase-requests`
- General chat public: `http://localhost:8080/chat/general/`
- Tenant chat: `http://localhost:8080/chat?tenantId=TODO_TENANT_ID&chatbotId=TODO_CHATBOT_ID`

Lưu ý:

- `/actuator/health` không nên dùng làm health check vì `pom.xml` hiện không có actuator dependency.
- Tenant chat UI gửi header `X-Tenant-Id`, nhưng API `/api/chat/**` vẫn cần session đăng nhập theo `SecurityConfig`. Vì vậy hãy login tenant trong cùng browser trước khi mở URL tenant chat.

### 2.2 API health check

Spring Boot không có endpoint health riêng. Dùng các check sau:

```powershell
curl.exe -i http://localhost:8080/login
curl.exe -i http://localhost:8080/chat/general/
```

Kiểm tra general chat API public đã tạo được conversation:

```powershell
curl.exe -s -X POST http://localhost:8080/api/general/chat/start
```

Kết quả mong đợi:

```json
{"conversationId":"..."}
```

Kiểm tra runtime LLM qua backend sau khi đã login platform admin:

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
curl.exe -i -c tmp\admin-cookie.txt -b tmp\admin-cookie.txt -X POST http://localhost:8080/api/login/admin `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"admin\",\"code\":\"admin123\"}"

curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/runtime/llm
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/ops/platform
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/ops/benchmark-summary
```

FastAPI health nếu chạy service độc lập hoặc nếu truy cập được spawned runtime local:

```powershell
curl.exe http://localhost:8000/healthz
curl.exe http://127.0.0.1:TODO_LLM_PORT/healthz
```

Kết quả Python `/healthz` mong đợi:

```json
{
  "status": "ready",
  "ready": true,
  "error": null,
  "cached_pipelines": 1,
  "kb_dir": "...",
  "kb_loaded": true
}
```

TODO: với Docker default, lấy health Python qua `GET /api/runtime/llm` hoặc log app; không giả định host Windows gọi được `127.0.0.1:8101`.

### 2.3 API login

Platform admin:

```powershell
curl.exe -i -c tmp\admin-cookie.txt -b tmp\admin-cookie.txt -X POST http://localhost:8080/api/login/admin `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"admin\",\"code\":\"admin123\"}"

curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/me
```

Tenant admin:

```powershell
curl.exe -i -c tmp\tenant-cookie.txt -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/login/tenant `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"admin@demo.local\",\"code\":\"admin123\"}"

curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/me
```

Tenant member:

```powershell
curl.exe -i -c tmp\member-cookie.txt -b tmp\member-cookie.txt -X POST http://localhost:8080/api/login/tenant `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"member@demo.local\",\"code\":\"member123\"}"

curl.exe -s -b tmp\member-cookie.txt http://localhost:8080/api/me
```

### 2.4 API chat

General chat public, không cần login:

```powershell
curl.exe -s -X POST http://localhost:8080/api/general/chat/start
```

Điền `conversationId` trả về vào lệnh sau:

```powershell
curl.exe -s -X POST http://localhost:8080/api/general/chat/send `
  -H "Content-Type: application/json" `
  -d "{\"conversationId\":\"TODO_GENERAL_CONVERSATION_ID\",\"message\":\"Tôi cần sofa cho phòng khách nhỏ, dễ vệ sinh, ngân sách khoảng 10 triệu.\"}"
```

Tenant chat, cần cookie tenant:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chat/start `
  -H "Content-Type: application/json" `
  -H "X-Tenant-Id: TODO_TENANT_ID" `
  -d "{\"chatbotId\":\"TODO_CHATBOT_ID\",\"userExternalId\":\"demo-user-01\"}"
```

Điền `conversationId` trả về:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chat/send `
  -H "Content-Type: application/json" `
  -H "X-Tenant-Id: TODO_TENANT_ID" `
  -d "{\"conversationId\":\"TODO_TENANT_CONVERSATION_ID\",\"message\":\"Tôi cần sofa cho phòng khách nhỏ, nhà có trẻ con, ngân sách khoảng 10 triệu. Có mẫu nào phù hợp không?\"}"
```

Kết quả mong đợi:

- Response có `reply`, `latencyMs`, `model`, `adapter`, `llmBaseUrl`.
- Lần đầu có thể chậm vì runtime/model warmup.
- Nếu Python lỗi, backend có fallback message; đây là dấu hiệu cần xem log chứ không phải kết quả demo mong muốn.

### 2.5 Kiểm tra database

Docker:

```powershell
docker compose exec postgres psql -U postgres -d global_admin -c "select code, name, status, kb_dir from tenants order by code;"
docker compose exec postgres psql -U postgres -d global_admin -c "select tenant_id, email, role, status from tenant_members order by email;"
docker compose exec postgres psql -U postgres -d global_admin -c "select id, tenant_id, name, channel, status, mode, provider from chatbot_instances order by name;"
docker compose exec postgres psql -U postgres -d global_admin -c "select id, tenant_id, chatbot_id, title, lead_created, created_at from conversations order by created_at desc limit 10;"
docker compose exec postgres psql -U postgres -d global_admin -c "select id, tenant_id, customer_name, phone, status, assigned_to_member_id, created_at from purchase_requests order by created_at desc limit 10;"
```

Local PostgreSQL:

```powershell
psql -U postgres -d global_admin -c "select code, name, status, kb_dir from tenants order by code;"
```

### 2.6 Kiểm tra knowledge base

Trên host:

```powershell
Test-Path F:\20251\prj3\chatbot\kb\noithatcaco\chunks.jsonl
Test-Path F:\20251\prj3\chatbot\kb\noithatcaco\index.json
Test-Path F:\20251\prj3\chatbot\kb\noithatcaco\raw_urls.txt
Get-Content F:\20251\prj3\chatbot\kb\noithatcaco\raw_urls.txt -TotalCount 5
```

Trong Docker DB, kiểm tra tenant `kb_dir` là path container:

```powershell
docker compose exec postgres psql -U postgres -d global_admin -c "select code, kb_dir from tenants order by code;"
```

Nếu dùng demo SQL và Docker, cập nhật path:

```powershell
@"
UPDATE tenants SET kb_dir = '/opt/app/chatbot/kb/noithatcaco' WHERE code = 'demo_caco';
UPDATE tenants SET kb_dir = '/opt/app/chatbot/kb/article' WHERE code = 'demo_article';
"@ | docker compose exec -T postgres psql -U postgres -d global_admin
```

## 3. Tài khoản demo cần dùng

### 3.1 Platform admin

Có trong code `LoginController`, không cần seed DB:

- Username: `admin`
- Password: `admin123`
- Role: `PLATFORM_ADMIN`
- Dùng cho: `/admin`, `/api/admin/tenants`, `/api/admin/tenant-members`, `/api/runtime/llm`, `/api/ops/platform`, `/api/ops/benchmark-summary`.

### 3.2 Tenant admin

Có trong migration `V15__add_tenant_member_auth_fields.sql` nếu tenant `demo_tenant` tồn tại:

- Email: `admin@demo.local`
- Password: `admin123`
- Role: `TENANT_ADMIN`
- Tenant: `demo_tenant`
- Dùng cho: `/tenant`, `/api/chatbots`, `/api/kb/source-urls`, `/api/kb/rebuild`, `/api/ops/tenant`, `/tenant/purchase-requests`.

Lưu ý:

- `demo_tenant` có account nhưng migration không seed sẵn tenant chatbot bán hàng cho tenant này. Cần tạo chatbot bằng API tenant admin hoặc dùng SQL demo có chatbot.
- Với local Windows, `demo_tenant.kb_dir` có thể đang là `/opt/app/chatbot/kb/article` từ migration V14, path này hợp Docker hơn local. TODO: nếu chạy local, update `kb_dir` hoặc tạo tenant mới.

### 3.3 Tenant member

Có trong migration `V15__add_tenant_member_auth_fields.sql`:

- Email: `member@demo.local`
- Password: `member123`
- Role: `TENANT_MEMBER`
- Tenant: `demo_tenant`
- Dùng cho: xem/claim purchase request trong `/tenant/purchase-requests`.

### 3.4 User/guest

- General chat `/chat/general/`: không cần account.
- Tenant chat `/chat?tenantId=...&chatbotId=...`: UI có ý tưởng guest token, nhưng API `/api/chat/**` hiện cần session login. TODO: nếu muốn demo guest public theo tenant, cần sửa security hoặc demo bằng browser đã login tenant.

### 3.5 Demo CaCo/Article tenant

File `multitenant/docs/sql/demo_multi_tenant_setup.sql` có tenant và chatbot:

- `demo_caco`
  - Tenant id: `daf0378f-53e1-4705-8234-41c74287e489`
  - API key trong SQL: `029269d7f5f445f7ac36c196dffa134e`
  - Chatbot id: `e08a7b4f-ebfb-4874-a119-b90e95e85fc7`
  - KB: `chatbot/kb/noithatcaco`
- `demo_article`
  - Tenant id: `58ca3bdb-50b4-4e36-bcf6-fc88dbd2e457`
  - API key trong SQL: `a4b9d130f0d34f74ac6b54cf8d6d2e11`
  - Chatbot id: `5fd0f6f4-c0b8-4e4e-9d7b-4b65f4c3998b`
  - KB: `chatbot/kb/article`

TODO bắt buộc nếu dùng hai tenant này:

- Import SQL demo vào DB.
- Tạo tenant admin/member cho từng tenant, vì SQL demo chưa tạo account đăng nhập.
- Khi chạy Docker, update `kb_dir` từ path Windows sang `/opt/app/chatbot/kb/...`.

Import SQL demo bằng Docker:

```powershell
Get-Content F:\20251\prj3\multitenant\docs\sql\demo_multi_tenant_setup.sql | docker compose exec -T postgres psql -U postgres -d global_admin
```

Tạo member cho tenant demo bằng platform admin API:

```powershell
curl.exe -s -b tmp\admin-cookie.txt -X POST "http://localhost:8080/api/admin/tenant-members?tenantId=TODO_TENANT_ID" `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"TODO_EMAIL\",\"displayName\":\"TODO_DISPLAY_NAME\",\"role\":\"TENANT_ADMIN\",\"status\":\"ACTIVE\",\"password\":\"admin123\"}"
```

## 4. Kịch bản demo chính

### 4.1 Login admin

UI:

1. Mở `http://localhost:8080/login`.
2. Đăng nhập `admin` / `admin123`.
3. Kiểm tra được vào `/admin`.

API:

```powershell
curl.exe -i -c tmp\admin-cookie.txt -b tmp\admin-cookie.txt -X POST http://localhost:8080/api/login/admin `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"admin\",\"code\":\"admin123\"}"
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/me
```

### 4.2 Kiểm tra tenant/chatbot

Xem tenant:

```powershell
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/admin/tenants
```

Nếu chưa có tenant phù hợp cho demo RAG, tạo tenant mới:

```powershell
curl.exe -s -b tmp\admin-cookie.txt -X POST http://localhost:8080/api/admin/tenants `
  -H "Content-Type: application/json" `
  -d "{\"code\":\"midterm_caco\",\"name\":\"Midterm CaCo\",\"kbDir\":\"/opt/app/chatbot/kb/noithatcaco\",\"status\":\"ACTIVE\"}"
```

TODO:

- Nếu chạy local Windows, đổi `kbDir` thành `F:/20251/prj3/chatbot/kb/noithatcaco`.
- Lưu `id` tenant trả về vào `TODO_TENANT_ID`.

Tạo tenant admin cho tenant mới:

```powershell
curl.exe -s -b tmp\admin-cookie.txt -X POST "http://localhost:8080/api/admin/tenant-members?tenantId=TODO_TENANT_ID" `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"midterm.admin@demo.local\",\"displayName\":\"Midterm Admin\",\"role\":\"TENANT_ADMIN\",\"status\":\"ACTIVE\",\"password\":\"admin123\"}"
```

Đăng nhập tenant admin:

```powershell
curl.exe -i -c tmp\tenant-cookie.txt -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/login/tenant `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"midterm.admin@demo.local\",\"code\":\"admin123\"}"
```

Xem chatbot của tenant:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/chatbots
```

Nếu danh sách trống, tạo chatbot:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chatbots `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"Midterm Web Sales Bot\",\"channel\":\"web\",\"personaJson\":\"{\\\"tone\\\":\\\"friendly\\\",\\\"purpose\\\":\\\"interior sales advisor\\\"}\",\"responseStyle\":\"natural\",\"mode\":\"tenant_sales\",\"provider\":\"local\"}"
```

TODO: lưu `id` chatbot trả về vào `TODO_CHATBOT_ID`.

### 4.3 Kiểm tra nguồn dữ liệu/knowledge base

UI:

1. Đăng nhập tenant admin.
2. Mở `http://localhost:8080/tenant`.
3. Bấm load KB Source URLs.
4. Bấm load Tenant Ops.

API:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/kb/source-urls
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/ops/tenant
```

Thêm URL nguồn nếu cần:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/kb/source-urls `
  -H "Content-Type: application/json" `
  -d "{\"url\":\"TODO_SOURCE_URL\"}"
```

Rebuild KB chỉ nên chạy nếu đã thử trước:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/kb/rebuild
```

TODO: `TODO_SOURCE_URL` phải là URL `http` hoặc `https` thật và website phải truy cập được từ môi trường chạy demo.

### 4.4 Chat hỏi đáp sản phẩm

UI:

1. Đăng nhập tenant admin/member trong browser.
2. Mở `http://localhost:8080/chat?tenantId=TODO_TENANT_ID&chatbotId=TODO_CHATBOT_ID`.
3. Hỏi câu có liên quan KB, ví dụ:
   - “Tôi muốn tìm sofa cho phòng khách nhỏ, dễ vệ sinh, ngân sách khoảng 10 triệu.”
   - “Có mẫu nào phù hợp cho nhà có trẻ nhỏ không?”
   - “Chính sách giao hàng hoặc bảo hành thế nào?”

API:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chat/start `
  -H "Content-Type: application/json" `
  -H "X-Tenant-Id: TODO_TENANT_ID" `
  -d "{\"chatbotId\":\"TODO_CHATBOT_ID\",\"userExternalId\":\"demo-user-01\"}"

curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chat/send `
  -H "Content-Type: application/json" `
  -H "X-Tenant-Id: TODO_TENANT_ID" `
  -d "{\"conversationId\":\"TODO_TENANT_CONVERSATION_ID\",\"message\":\"Tôi muốn tìm sofa cho phòng khách nhỏ, dễ vệ sinh, ngân sách khoảng 10 triệu.\"}"
```

### 4.5 Chat gợi ý sản phẩm theo nhu cầu

Gợi ý script:

```text
Tôi cần sofa cho phòng khách khoảng 18m2, nhà có trẻ nhỏ, muốn dễ lau chùi, phong cách hiện đại, ngân sách khoảng 10 triệu.
Tôi thích màu trung tính, ưu tiên sofa gọn và bền.
Bạn so sánh giúp tôi 2 lựa chọn phù hợp nhất.
```

Kỳ vọng:

- Assistant hỏi thêm hoặc gợi ý theo nhu cầu.
- Với KB tenant đã load, câu trả lời nên nhắc sản phẩm/chính sách có trong KB.
- Response API có `llmBaseUrl` khác rỗng nếu runtime đã gọi được.

### 4.6 Tạo purchase request từ hội thoại

Luồng tạo purchase request trong code phụ thuộc Python trả `trigger_purchase_request=true`; với `tenant_sales`, điều này xảy ra khi hội thoại đã tới stage `close` rồi user xác nhận. Không nên chỉ gửi `CONFIRM` ngay từ đầu.

Script đề xuất, cần chạy thử trước:

```text
Tôi cần sofa cho phòng khách nhỏ, ngân sách khoảng 10 triệu, nhà có trẻ nhỏ.
Tôi thích màu trung tính, dễ vệ sinh, giao về quận 1.
Tôi chọn phương án bạn gợi ý. Tên tôi là Nguyễn Văn A, số điện thoại 0912345678, địa chỉ 123 Nguyễn Trãi, Quận 1, TP.HCM.
Tôi xác nhận mua, bạn tạo yêu cầu giúp tôi.
```

Sau đó mở:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/purchase-requests
```

Hoặc UI:

```text
http://localhost:8080/tenant/purchase-requests
```

TODO: chuẩn bị sẵn một purchase request mẫu trong DB nếu luồng live không đi tới `close` trong thời gian demo.

### 4.7 Tenant admin/member xem và xử lý purchase request

Tenant member claim request:

```powershell
curl.exe -s -b tmp\member-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/claim
```

Tenant admin assign request:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/assign `
  -H "Content-Type: application/json" `
  -d "{\"member_id\":\"TODO_MEMBER_ID\"}"
```

Đổi trạng thái:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/status `
  -H "Content-Type: application/json" `
  -d "{\"status\":\"CONTACTED\"}"

curl.exe -s -b tmp\tenant-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/status `
  -H "Content-Type: application/json" `
  -d "{\"status\":\"COMPLETED\"}"
```

Lấy `TODO_MEMBER_ID`:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/tenant-members
```

### 4.8 Xem thống kê/runtime nếu ổn định

Platform admin:

```powershell
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/runtime/llm
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/ops/platform
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/ops/benchmark-summary
```

Tenant admin:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/ops/tenant
curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/ops/runtime/evict
```

Chỉ evict runtime khi muốn chứng minh lần chat sau khởi động lại runtime; không nên evict ngay trước phần chat chính vì sẽ gây cold start.

## 5. Lệnh curl/Postman theo từng bước quan trọng

### 5.1 Biến Postman nên tạo

- `base_url`: `http://localhost:8080`
- `tenant_id`: `TODO_TENANT_ID`
- `chatbot_id`: `TODO_CHATBOT_ID`
- `conversation_id`: `TODO_CONVERSATION_ID`
- `request_id`: `TODO_PURCHASE_REQUEST_ID`
- `member_id`: `TODO_MEMBER_ID`

Postman lưu cookie session tự động theo domain `localhost`. Với curl, dùng `-c tmp\*.txt -b tmp\*.txt`.

### 5.2 Admin login và tenant setup

```powershell
curl.exe -i -c tmp\admin-cookie.txt -b tmp\admin-cookie.txt -X POST http://localhost:8080/api/login/admin `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"admin\",\"code\":\"admin123\"}"

curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/admin/tenants

curl.exe -s -b tmp\admin-cookie.txt -X POST http://localhost:8080/api/admin/tenants `
  -H "Content-Type: application/json" `
  -d "{\"code\":\"TODO_CODE\",\"name\":\"TODO_NAME\",\"kbDir\":\"TODO_KB_DIR\",\"status\":\"ACTIVE\"}"

curl.exe -s -b tmp\admin-cookie.txt -X POST "http://localhost:8080/api/admin/tenant-members?tenantId=TODO_TENANT_ID" `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"TODO_EMAIL\",\"displayName\":\"TODO_NAME\",\"role\":\"TENANT_ADMIN\",\"status\":\"ACTIVE\",\"password\":\"admin123\"}"
```

### 5.3 Tenant login, chatbot, KB

```powershell
curl.exe -i -c tmp\tenant-cookie.txt -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/login/tenant `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"TODO_TENANT_ADMIN_EMAIL\",\"code\":\"admin123\"}"

curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/chatbots

curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chatbots `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"TODO_BOT_NAME\",\"channel\":\"web\",\"personaJson\":\"{}\",\"responseStyle\":\"natural\",\"mode\":\"tenant_sales\",\"provider\":\"local\"}"

curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/kb/source-urls
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/ops/tenant
```

### 5.4 General chat

```powershell
curl.exe -s -X POST http://localhost:8080/api/general/chat/start

curl.exe -s -X POST http://localhost:8080/api/general/chat/send `
  -H "Content-Type: application/json" `
  -d "{\"conversationId\":\"TODO_GENERAL_CONVERSATION_ID\",\"message\":\"Tôi cần tư vấn chọn sofa cho căn hộ nhỏ.\"}"
```

### 5.5 Tenant chat

```powershell
curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chat/start `
  -H "Content-Type: application/json" `
  -H "X-Tenant-Id: TODO_TENANT_ID" `
  -d "{\"chatbotId\":\"TODO_CHATBOT_ID\",\"userExternalId\":\"demo-user-01\"}"

curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chat/send `
  -H "Content-Type: application/json" `
  -H "X-Tenant-Id: TODO_TENANT_ID" `
  -d "{\"conversationId\":\"TODO_TENANT_CONVERSATION_ID\",\"message\":\"Tôi cần sofa phòng khách nhỏ, dễ vệ sinh, ngân sách 10 triệu.\"}"

curl.exe -s -b tmp\tenant-cookie.txt "http://localhost:8080/api/chat/conversations?chatbotId=TODO_CHATBOT_ID&limit=10"
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/chat/conversation/TODO_TENANT_CONVERSATION_ID/messages
```

### 5.6 Purchase request

```powershell
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/purchase-requests

curl.exe -s -b tmp\member-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/claim

curl.exe -s -b tmp\tenant-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/assign `
  -H "Content-Type: application/json" `
  -d "{\"member_id\":\"TODO_MEMBER_ID\"}"

curl.exe -s -b tmp\tenant-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/status `
  -H "Content-Type: application/json" `
  -d "{\"status\":\"CONTACTED\"}"
```

### 5.7 Runtime/ops

```powershell
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/runtime/llm
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/ops/platform
curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/ops/benchmark-summary
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/ops/tenant
```

## 6. Các lỗi thường gặp khi demo và cách xử lý

### 6.1 `/actuator/health` trả 404

Nguyên nhân: repo hiện không có Spring Boot actuator dependency.  
Cách xử lý: dùng `/login`, `/chat/general/`, `/api/general/chat/start`, `/api/me` sau login, hoặc `docker compose ps`.

### 6.2 Tenant chat trả 401/403 khi gọi curl chỉ có `X-API-Key`

Nguyên nhân: `SecurityConfig` yêu cầu authenticated cho `/api/**`, trừ `/api/login/**` và `/api/general/**`. Header API key trong `TenantResolver` không đủ để vượt qua security hiện tại.  
Cách xử lý: login tenant trước, dùng cookie session với `-b tmp\tenant-cookie.txt`. TODO nếu muốn public API-key-only: cần sửa security trước demo.

### 6.3 Mở `/chat?tenantId=...&chatbotId=...` nhưng không gửi được

Nguyên nhân thường gặp:

- Chưa login tenant trong cùng browser.
- `chatbotId` không thuộc tenant session hiện tại.
- Tenant không có `kb_dir` đúng.

Cách xử lý:

```powershell
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/me
curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/chatbots
docker compose exec postgres psql -U postgres -d global_admin -c "select id, code, kb_dir from tenants;"
```

### 6.4 Runtime/model warmup quá lâu

Nguyên nhân: lần đầu tải hoặc warm model local. Docker đã set `BASE_MODEL` mặc định TinyLlama và timeout 600000 ms nhưng vẫn có thể mất vài phút.  
Cách xử lý:

- Pre-warm trước demo bằng một câu general chat và một câu tenant chat.
- Xem log:

```powershell
docker compose logs --no-color --tail=300 app
```

- Không evict runtime ngay trước phần chat chính.

### 6.5 `kb_loaded=false` hoặc câu trả lời không bám KB

Nguyên nhân:

- `kb_dir` sai môi trường.
- Thiếu `chunks.jsonl` hoặc `index.json`.
- Tenant mới chưa cấu hình KB.

Cách xử lý:

```powershell
Test-Path F:\20251\prj3\chatbot\kb\noithatcaco\chunks.jsonl
Test-Path F:\20251\prj3\chatbot\kb\noithatcaco\index.json
docker compose exec postgres psql -U postgres -d global_admin -c "select code, kb_dir from tenants;"
```

Docker path đúng nên là `/opt/app/chatbot/kb/...`.

### 6.6 Import `demo_multi_tenant_setup.sql` xong nhưng không login được demo_caco/demo_article

Nguyên nhân: SQL này tạo tenant và chatbot, chưa tạo tenant member.  
Cách xử lý: tạo member bằng `/api/admin/tenant-members` với platform admin. TODO điền email/password demo trước buổi demo.

### 6.7 `POST /api/chatbots` không thấy bot ở admin UI

Nguyên nhân: endpoint chatbot yêu cầu tenant admin và tenant context. `/admin` là platform UI, không phải nơi ổn định để demo tạo chatbot tenant.  
Cách xử lý: login tenant admin và dùng `/api/chatbots` hoặc phần tenant tools. Dùng `/admin` chủ yếu cho tenant/member/ops.

### 6.8 Purchase request không được tạo sau câu “CONFIRM”

Nguyên nhân: code Python chỉ bật `trigger_purchase_request` khi hội thoại đã ở stage `close` rồi user confirm; xác nhận quá sớm không tạo request.  
Cách xử lý:

- Dùng script hội thoại đủ nhu cầu, thông tin liên hệ và xác nhận sau khi assistant đã chốt.
- Chuẩn bị sẵn một purchase request mẫu trong DB để demo màn hình xử lý nếu luồng live không tới close. TODO chuẩn bị trước.

### 6.9 Assign purchase request không nhận `memberId`

Nguyên nhân: request DTO dùng JSON field `member_id`, không phải `memberId`.  
Cách xử lý:

```json
{"member_id":"TODO_MEMBER_ID"}
```

### 6.10 Method purchase request sai

Code hiện dùng `PUT`:

- `PUT /api/purchase-requests/{id}/status`
- `PUT /api/purchase-requests/{id}/claim`
- `PUT /api/purchase-requests/{id}/assign`

Không dùng `POST` cho các endpoint này.

### 6.11 KB rebuild thất bại

Nguyên nhân:

- Website nguồn không truy cập được.
- `raw_urls.txt` rỗng hoặc URL invalid.
- `PYTHON_BIN`/`MODEL_SERVER_DIR` sai.
- Thiếu quyền ghi `kb_dir`.

Cách xử lý:

- Không rebuild live nếu chưa thử trước.
- Demo KB source + artifact đã build sẵn.
- Xem response `GET /api/ops/tenant` và log app.

### 6.12 PowerShell `curl` không chạy đúng

Nguyên nhân: `curl` trong PowerShell có thể là alias.  
Cách xử lý: dùng `curl.exe` như runbook.

### 6.13 Python dependency thiếu khi chạy local

Nguyên nhân: chưa cài `chatbot/requirements.txt` vào venv hoặc dùng nhầm Python.  
Cách xử lý:

```powershell
cd F:\20251\prj3\chatbot
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

### 6.14 Full test suite không xanh

Hiện `mvn -q -DskipTests compile` OK, nhưng full test đang có test cũ lệch contract `ChatResponse`; Python unittest cũng có lỗi trong môi trường kiểm tra hiện tại.  
Cách xử lý: không dùng “test pass toàn bộ” làm claim trong demo. Chỉ dùng compile, UI/API smoke test và log/DB làm bằng chứng.

## 7. Checklist nhanh trước khi vào phòng demo

- `docker compose ps` cho thấy `postgres` healthy và `app` running.
- Mở được `http://localhost:8080/login`.
- Login được platform admin `admin/admin123`.
- Login được tenant admin đã chọn.
- `GET /api/admin/tenants` có tenant demo.
- `GET /api/chatbots` dưới tenant admin có ít nhất một chatbot id.
- Tenant `kb_dir` đúng môi trường.
- `chunks.jsonl` và `index.json` tồn tại.
- General chat đã được pre-warm.
- Tenant chat đã được pre-warm.
- Có sẵn script hội thoại chốt mua.
- Có sẵn ít nhất một purchase request mẫu hoặc đã tạo thử thành công.
- Không evict runtime trước phần chat chính.
- Có sẵn log command và screenshot cần lưu.
