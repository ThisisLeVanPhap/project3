# Tài liệu cài đặt, sử dụng và API - Hệ thống chatbot tư vấn nội thất

## 1. Mục đích tài liệu

Tài liệu này hướng dẫn cài đặt, chạy, sử dụng giao diện và gọi API của hệ thống chatbot tư vấn/gợi ý sản phẩm nội thất. Nội dung áp dụng cho môi trường demo và môi trường phát triển cục bộ.

## 2. Thành phần triển khai

Repository gồm các thành phần:

- `multitenant/`: backend Spring Boot, API nghiệp vụ, giao diện static, migration database và test backend.
- `chatbot/`: Python FastAPI chatbot service, RAG/retrieval, prompt, state hội thoại, công cụ xử lý dữ liệu sản phẩm và test Python.
- `docker-compose.yml`: cấu hình chạy PostgreSQL và backend tích hợp Python runtime.
- `chatbot/kb/`: dữ liệu sản phẩm và knowledge base theo tenant.
- `docs/`: tài liệu kỹ thuật.

## 3. Yêu cầu môi trường

- Java 21.
- Maven.
- Python 3.11.
- PostgreSQL 16.
- Docker Desktop cho phương án Docker Compose.

## 4. Chạy hệ thống bằng Docker Compose

Từ root repository:

```powershell
cd F:\20251\prj3
docker compose up --build
```

Chạy nền:

```powershell
docker compose up --build -d
```

Port dịch vụ:

- Backend/API/UI: `http://localhost:8080`
- PostgreSQL: `localhost:5432`
- Python runtime theo tenant: dải `8101-8199`

Dừng hệ thống:

```powershell
docker compose down
```

## 5. Chạy hệ thống cục bộ

Cài Python dependencies:

```powershell
cd F:\20251\prj3\chatbot
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Tạo database:

```sql
CREATE DATABASE global_admin;
```

Chạy backend:

```powershell
$env:PYTHON_BIN="F:\20251\prj3\chatbot\.venv\Scripts\python.exe"
$env:MODEL_SERVER_DIR="F:\20251\prj3\chatbot"
$env:SPRING_DATASOURCE_URL="jdbc:postgresql://localhost:5432/global_admin"
$env:SPRING_DATASOURCE_USERNAME="postgres"
$env:SPRING_DATASOURCE_PASSWORD="admin"
cd F:\20251\prj3\multitenant
mvn spring-boot:run
```

Nạp dữ liệu demo:

```powershell
psql -U postgres -d global_admin -f F:\20251\prj3\multitenant\docs\sql\demo_multi_tenant_setup.sql
```

Chạy Python chatbot service độc lập:

```powershell
cd F:\20251\prj3\chatbot
.\.venv\Scripts\Activate.ps1
$env:KB_DIR="F:\20251\prj3\chatbot\kb\noithatcaco"
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

Swagger UI của Python service:

```text
http://localhost:8000/docs
```

## 6. Cấu hình môi trường

Backend:

- `SPRING_DATASOURCE_URL`: JDBC URL PostgreSQL.
- `SPRING_DATASOURCE_USERNAME`: tài khoản database.
- `SPRING_DATASOURCE_PASSWORD`: mật khẩu database.
- `SERVER_PORT`: port backend.
- `PYTHON_BIN`: đường dẫn Python runtime.
- `MODEL_SERVER_DIR`: thư mục `chatbot`.
- `LLM_HOST`: host Python runtime.
- `LLM_PORT_START`: port bắt đầu.
- `LLM_PORT_END`: port kết thúc.
- `LLM_HEALTH_PATH`: health endpoint của Python service.
- `LLM_UVICORN_MODULE`: module Uvicorn.
- `MESSENGER_VERIFY_TOKEN`: token verify webhook Messenger.

Python chatbot service:

- `KB_DIR`: thư mục knowledge base.
- `BASE_MODEL`: tên model local.
- `LORA_ADAPTER`: đường dẫn adapter khi sử dụng local runtime có adapter.
- `TOKENIZER_PATH`: tokenizer path.
- `MAX_NEW_TOKENS`: số token sinh tối đa.
- `TEMPERATURE`: sampling temperature.
- `TOP_P`: nucleus sampling.
- `TOP_K`: top-k sampling.

## 7. Giao diện sử dụng

Các URL giao diện:

- Login: `http://localhost:8080/login`
- Admin UI: `http://localhost:8080/admin`
- Tenant UI: `http://localhost:8080/tenant`
- Tenant purchase requests: `http://localhost:8080/tenant/purchase-requests`
- Web chat: `http://localhost:8080/chat`
- General chat: `http://localhost:8080/chat/general`

Các vai trò sử dụng:

- Platform admin quản lý tenant, chatbot, thống kê và vận hành nền tảng.
- Tenant admin quản lý dữ liệu cửa hàng, hội thoại và yêu cầu mua hàng.
- Người dùng cuối chat để hỏi đáp, nhận tư vấn và gửi nhu cầu mua hàng.

## 8. Quy trình sử dụng chính

Quy trình chat theo tenant:

1. Người dùng mở web chat hoặc gửi tin nhắn qua kênh tích hợp.
2. Client tạo conversation qua `/api/chat/start`.
3. Client gửi câu hỏi qua `/api/chat/send`.
4. Backend xác định tenant, chatbot và lịch sử hội thoại.
5. Python chatbot service truy xuất tri thức từ KB của tenant.
6. Mô hình ngôn ngữ lớn sinh câu trả lời từ prompt chứa context truy xuất.
7. Backend lưu hội thoại và trả reply cho client.
8. Khi hội thoại có nhu cầu mua hàng, hệ thống tạo purchase request để nhân viên xử lý.

Quy trình quản lý KB:

1. Tenant/admin cấu hình nguồn dữ liệu sản phẩm.
2. Công cụ xử lý dữ liệu tạo `docs.jsonl`, `chunks.jsonl`, `index.json`.
3. Tenant trỏ `kb_dir` đến thư mục knowledge base.
4. Runtime chatbot nạp KB theo `KB_DIR`.

## 9. API chat theo tenant

Tạo conversation:

```powershell
curl -X POST http://localhost:8080/api/chat/start `
  -H "Content-Type: application/json" `
  -H "X-API-Key: tenant-api-key-demo" `
  -d "{\"chatbotId\":\"e08a7b4f-ebfb-4874-a119-b90e95e85fc7\"}"
```

Gửi tin nhắn:

```powershell
curl -X POST http://localhost:8080/api/chat/send `
  -H "Content-Type: application/json" `
  -H "X-API-Key: tenant-api-key-demo" `
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"Tôi muốn mua sofa cho phòng khách nhỏ\"}"
```

Response:

```json
{
  "reply": "Nội dung tư vấn",
  "latencyMs": 1000,
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "adapter": "",
  "llmBaseUrl": "http://127.0.0.1:8101"
}
```

Quản lý hội thoại:

- `GET /api/chat/conversations?chatbotId=<uuid>&limit=50`
- `GET /api/chat/conversation/{conversationId}/messages`
- `PUT /api/chat/conversation/{conversationId}/rename`
- `DELETE /api/chat/conversation/{conversationId}`

## 10. API chat tư vấn chung

Tạo conversation:

```powershell
curl -X POST http://localhost:8080/api/general/chat/start
```

Gửi tin nhắn:

```powershell
curl -X POST http://localhost:8080/api/general/chat/send `
  -H "Content-Type: application/json" `
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"Tôi nên chọn sofa kích thước nào cho căn hộ nhỏ?\"}"
```

Quản lý hội thoại:

- `GET /api/general/chat/conversations?limit=50`
- `GET /api/general/chat/conversation/{conversationId}/messages`
- `PUT /api/general/chat/conversation/{conversationId}/rename`
- `DELETE /api/general/chat/conversation/{conversationId}`

## 11. API Python chatbot service

Health:

```powershell
curl http://localhost:8000/healthz
```

Chat trực tiếp:

```powershell
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"Tôi muốn tìm bàn ăn gỗ\", \"history\":[], \"conversation_id\":\"demo\", \"channel\":\"web\", \"tenant_id\":\"demo\"}"
```

Đọc state:

```powershell
curl "http://localhost:8000/state?conversation_id=demo"
```

Gửi feedback:

```powershell
curl -X POST http://localhost:8000/feedback `
  -H "Content-Type: application/json" `
  -d "{\"conversation_id\":\"demo\",\"tenant_id\":\"demo\",\"channel\":\"web\",\"question\":\"...\",\"answer\":\"...\",\"is_correct\":true,\"note\":\"\"}"
```

## 12. API quản trị

Đăng nhập và session:

- `POST /api/login/admin`
- `POST /api/login/tenant`
- `POST /api/login/logout`
- `GET /api/me`

Tenant và member:

- `GET /api/admin/tenants`
- `POST /api/admin/tenants`
- `GET /api/admin/tenants/{tenantId}`
- `GET /api/admin/tenant-members`
- `POST /api/admin/tenant-members`
- `GET /api/tenant-members`
- `POST /api/tenant-members`

Chatbot:

- `GET /api/chatbots`
- `POST /api/chatbots`
- `PUT /api/chatbots/{id}`

Knowledge base:

- `GET /api/kb/source-urls`
- `POST /api/kb/source-urls`
- `DELETE /api/kb/source-urls`
- `POST /api/kb/rebuild`

## 13. API purchase request

- `GET /api/purchase-requests`
- `PUT /api/purchase-requests/{id}/status`
- `PUT /api/purchase-requests/{id}/claim`
- `PUT /api/purchase-requests/{id}/assign`

Purchase request lưu các thông tin:

- Tenant.
- Kênh hội thoại.
- Conversation id.
- Lead id.
- Tên khách hàng.
- Số điện thoại.
- Địa chỉ nhận hàng.
- Ghi chú.
- Trạng thái xử lý.
- Tham chiếu sản phẩm.

## 14. API kênh ngoài và vận hành

Messenger:

- `GET /api/messenger/bindings`
- `POST /api/messenger/bindings`
- `DELETE /api/messenger/bindings/{id}`
- `GET /webhook/messenger`
- `POST /webhook/messenger`

Telegram:

- `GET /api/telegram/bindings`
- `POST /api/telegram/bindings`
- `POST /webhook/telegram/{secretPath}`

Runtime và thống kê:

- `GET /api/runtime/llm`
- `GET /api/ops/platform`
- `GET /api/ops/tenant`
- `GET /api/ops/benchmark-summary`
- `POST /api/ops/runtime/evict`
- `GET /admin/api/stats/overview`
- `GET /admin/api/stats/by-tenant`
- `GET /admin/api/stats/timeseries`

## 15. Xử lý dữ liệu sản phẩm

Build KB từ URL nguồn:

```powershell
cd F:\20251\prj3\chatbot
python tools\scrape_site.py article kb\article\raw_urls.txt kb\article\docs.jsonl
python tools\build_kb.py kb\article\docs.jsonl kb\article\chunks.jsonl kb\article\index.json
```

Cấu trúc đầu ra:

- `docs.jsonl`: dữ liệu sản phẩm/chính sách sau khi thu thập.
- `chunks.jsonl`: các đoạn tri thức cho retrieval.
- `index.json`: chỉ mục tìm kiếm.

## 16. Test cases và kết quả thử nghiệm

Chạy test backend:

```powershell
cd F:\20251\prj3\multitenant
mvn test
```

Chạy test Python:

```powershell
cd F:\20251\prj3\chatbot
python -m unittest discover -s tests
```

Chạy thử nghiệm retrieval:

```powershell
cd F:\20251\prj3
python chatbot\eval\runner.py --dataset chatbot\eval\dataset.jsonl --kb-dir chatbot\kb\noithatcaco --top-k 5 --compare
```

Kết quả thử nghiệm retrieval được ghi trong `chatbot/eval/results-summary.md`, gồm Recall@k và MRR cho các mode retrieval.

## 17. Dữ liệu mẫu demo

Tenant CaCo:

- API key: `tenant-api-key-demo-caco`
- Chatbot id: `e08a7b4f-ebfb-4874-a119-b90e95e85fc7`
- KB: `chatbot/kb/noithatcaco`

Tenant Article:

- API key: `tenant-api-key-demo-article`
- Chatbot id: `5fd0f6f4-c0b8-4e4e-9d7b-4b65f4c3998b`
- KB: `chatbot/kb/article`

Kịch bản demo chat:

```text
Tôi muốn mua sofa cho phòng khách nhỏ.
Tên tôi là Nguyễn Văn A, số điện thoại là 0912345678.
Địa chỉ nhận hàng là 123 Nguyễn Trãi, Hà Nội.
CONFIRM
```
