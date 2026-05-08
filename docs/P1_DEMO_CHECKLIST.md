# P1 Demo Checklist

Ngày cập nhật: 2026-05-08  
Mục tiêu: checklist trước demo giữa kỳ cho hệ thống chatbot tư vấn/gợi ý sản phẩm nội thất dùng RAG/gọi model.

## Phân loại nhanh trước khi kiểm tra

Demo chắc chắn được nếu môi trường chạy đúng:

- Login platform admin và tenant member.
- Quản trị tenant/member.
- Kiểm tra KB source URLs và trạng thái KB của tenant.
- General chat public `/chat/general/` sau khi runtime/model đã warm.
- Tenant chat RAG qua `/chat?tenantId=...&chatbotId=...` nếu đã login tenant, có chatbot và `kb_dir` đúng.
- Xem/claim/assign/update purchase request nếu đã có request.
- Xem ops/runtime/benchmark summary nếu đã login đúng role.

Không nên demo live nếu chưa chuẩn bị riêng:

- `/api/chat/**` chỉ bằng `X-API-Key` mà không login session.
- `/actuator/health`.
- Admin UI tạo chatbot/binding dưới platform session.
- Price reference.
- Full test suite pass 100%.
- Messenger/Telegram live nếu chưa có token, binding và public HTTPS/ngrok.
- KB rebuild live từ website nếu chưa chạy thử ngay trước demo.

## 1. Kiểm tra máy, port, env

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| Kiểm tra thư mục làm việc. | `cd F:\20251\prj3` | Đang ở root repo, có `docker-compose.yml`, `multitenant`, `chatbot`, `docs`. | Nếu sai thư mục, chuyển về `F:\20251\prj3`. |
| Kiểm tra port chính. | `Get-NetTCPConnection -LocalPort 8080,5432 -ErrorAction SilentlyContinue \| Select-Object LocalPort,State,OwningProcess` | Trước khi start: port rảnh hoặc do service demo đang dùng. Sau khi start: `5432` và `8080` đang listen. | Nếu bị app khác chiếm, stop process đó hoặc đổi `APP_PORT`/`POSTGRES_PORT` trước khi `docker compose up`. |
| Kiểm tra port runtime AI. | `Get-NetTCPConnection -LocalPort 8101,8102,8103 -ErrorAction SilentlyContinue` | Không có process lạ chiếm dải runtime trước demo. Runtime sẽ xuất hiện sau request chat đầu tiên. | Đổi `LLM_PORT_START`/`LLM_PORT_END` hoặc stop process cũ. |
| Kiểm tra biến env Docker quan trọng. | `Get-ChildItem Env:POSTGRES_DB,Env:POSTGRES_USER,Env:POSTGRES_PASSWORD,Env:APP_PORT,Env:BASE_MODEL,Env:LLM_STARTUP_TIMEOUT_MS -ErrorAction SilentlyContinue` | Có thể trống nếu dùng default Compose. Default hợp demo: DB `global_admin`, user `postgres`, password `admin`, app `8080`, model TinyLlama. | Set lại trước khi chạy: `BASE_MODEL=TinyLlama/TinyLlama-1.1B-Chat-v1.0`, `LLM_STARTUP_TIMEOUT_MS=600000`. |
| Kiểm tra Docker Desktop. | `docker version` và `docker compose version` | Docker trả version, không lỗi daemon. | Mở Docker Desktop hoặc chạy service Docker rồi thử lại. |

## 2. Kiểm tra Docker, PostgreSQL, backend, Python runtime

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| Start stack chính. | `docker compose up --build -d` | Container `postgres` và `app` được tạo. | Nếu build lỗi dependency/network, kiểm tra log build. Nếu Docker chưa chạy, mở Docker Desktop. |
| Xem trạng thái container. | `docker compose ps` | `postgres` healthy/running, `app` running, port `8080` publish. | Nếu `postgres` unhealthy, xem `docker compose logs postgres`. Nếu `app` exited, xem log app. |
| Kiểm tra backend/UI. | `curl.exe -i http://localhost:8080/login` | HTTP 200 hoặc HTML login. | Nếu connection refused, app chưa chạy hoặc port sai. Xem `docker compose logs --no-color --tail=200 app`. |
| Kiểm tra API public tối thiểu. | `curl.exe -s -X POST http://localhost:8080/api/general/chat/start` | Trả JSON có `conversationId`. | Nếu lỗi DB/migration, xem log app và Postgres. |
| Kiểm tra runtime Python qua backend. | Sau khi login admin: `curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/runtime/llm` | Trả danh sách runtime. Có thể rỗng trước khi chat; sau chat sẽ có tenant/runtime. | Nếu rỗng trước chat là bình thường. Nếu chat lỗi startup, xem log app có dòng `Spawning LLM instance`, `Waiting LLM healthy`, `LLM READY`. |
| Kiểm tra log runtime. | `docker compose logs --no-color --tail=300 app` | Có log Spring startup, Flyway migration, và sau chat có log `[llm:<tenant>]`, `kb loaded`, `LLM READY`. | Nếu `Timed out waiting for chatbot warmup`, pre-warm sớm hơn, tăng timeout, dùng TinyLlama, hoặc dùng backup video/screenshot. |

Không nên dùng `/actuator/health`: code hiện không có actuator dependency trong `pom.xml`.

## 3. Kiểm tra tài khoản demo

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| Login platform admin. | `curl.exe -i -c tmp\admin-cookie.txt -b tmp\admin-cookie.txt -X POST http://localhost:8080/api/login/admin -H "Content-Type: application/json" -d "{\"name\":\"admin\",\"code\":\"admin123\"}"` | Response success, cookie session được lưu. | Nếu fail, kiểm tra đúng body `name/code`; tài khoản này hardcoded trong `LoginController`. |
| Xem principal admin. | `curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/me` | Role `PLATFORM_ADMIN`. | Nếu 401/403, cookie không được lưu; tạo lại thư mục `tmp` và login lại. |
| Login tenant admin seed. | `curl.exe -i -c tmp\tenant-cookie.txt -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/login/tenant -H "Content-Type: application/json" -d "{\"name\":\"admin@demo.local\",\"code\":\"admin123\"}"` | Role `TENANT_ADMIN`, tenant `demo_tenant`. | Nếu fail, kiểm tra migration V15 đã chạy và tenant `demo_tenant` tồn tại. |
| Login tenant member seed. | `curl.exe -i -c tmp\member-cookie.txt -b tmp\member-cookie.txt -X POST http://localhost:8080/api/login/tenant -H "Content-Type: application/json" -d "{\"name\":\"member@demo.local\",\"code\":\"member123\"}"` | Role `TENANT_MEMBER`. | Nếu fail, kiểm tra DB `tenant_members`. |
| Kiểm tra tenant demo dùng cho RAG. | `curl.exe -s -b tmp\admin-cookie.txt http://localhost:8080/api/admin/tenants` | Có tenant muốn demo, có `id`, `code`, `kbDir`, `status=ACTIVE`. | Nếu dùng `demo_caco`/`demo_article`, cần import SQL demo và tạo tenant member vì SQL đó chưa tạo account. |
| Tạo tenant member nếu thiếu. | `curl.exe -s -b tmp\admin-cookie.txt -X POST "http://localhost:8080/api/admin/tenant-members?tenantId=TODO_TENANT_ID" -H "Content-Type: application/json" -d "{\"email\":\"TODO_EMAIL\",\"displayName\":\"TODO_NAME\",\"role\":\"TENANT_ADMIN\",\"status\":\"ACTIVE\",\"password\":\"admin123\"}"` | Trả member mới với role đúng. | Nếu email trùng, dùng account đã có hoặc đổi email. Nếu 403, đang không dùng cookie platform admin. |

TODO trước demo: xác định rõ tenant chính để quay: `demo_tenant` tự seed hay `demo_caco` từ SQL demo.

## 4. Kiểm tra dữ liệu KB

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| Kiểm tra KB file trên host. | `Test-Path F:\20251\prj3\chatbot\kb\noithatcaco\chunks.jsonl`; `Test-Path F:\20251\prj3\chatbot\kb\noithatcaco\index.json`; `Test-Path F:\20251\prj3\chatbot\kb\noithatcaco\raw_urls.txt` | Cả 3 trả `True`. | Nếu thiếu, dùng KB khác có đủ file hoặc chạy build KB trước demo. Không rebuild live nếu chưa test. |
| Kiểm tra source URLs. | `Get-Content F:\20251\prj3\chatbot\kb\noithatcaco\raw_urls.txt -TotalCount 5` | Có URL `http/https`. | Nếu rỗng, thêm URL qua tenant UI/API hoặc dùng KB đã có dữ liệu. |
| Kiểm tra `kb_dir` trong DB. | `docker compose exec postgres psql -U postgres -d global_admin -c "select code, kb_dir from tenants order by code;"` | Tenant demo trỏ đúng path môi trường. Docker nên là `/opt/app/chatbot/kb/noithatcaco`; local Windows nên là `F:/20251/prj3/chatbot/kb/noithatcaco`. | Nếu sai path, update DB. Docker: `UPDATE tenants SET kb_dir='/opt/app/chatbot/kb/noithatcaco' WHERE code='TODO_CODE';`. |
| Kiểm tra tenant ops KB. | `curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/ops/tenant` | `knowledgeBase.status` là `READY` hoặc có artifact count. | Nếu `NOT_CONFIGURED`, tenant thiếu `kb_dir`. Nếu `NO_ARTIFACTS`, path không có artifacts. |
| Kiểm tra KB source API. | `curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/kb/source-urls` | Trả JSON có `tenantId`, `urls`. | Nếu 403, account không phải tenant admin. Nếu lỗi path, kiểm tra `kb_dir`. |

Chức năng chắc demo: xem KB source/status.  
Chức năng cần chuẩn bị: rebuild KB. Chỉ bấm `POST /api/kb/rebuild` nếu đã chạy thử và network website nguồn ổn định.

## 5. Kiểm tra API chat

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| General chat start. | `curl.exe -s -X POST http://localhost:8080/api/general/chat/start` | Trả `conversationId`. | Nếu lỗi, kiểm tra migration V21 đã tạo system tenant/general chatbot. |
| General chat send. | `curl.exe -s -X POST http://localhost:8080/api/general/chat/send -H "Content-Type: application/json" -d "{\"conversationId\":\"TODO_GENERAL_CONVERSATION_ID\",\"message\":\"Tôi cần tư vấn chọn sofa cho căn hộ nhỏ.\"}"` | Trả `reply`, `latencyMs`, `model`, `llmBaseUrl`. | Nếu chậm, đợi warmup. Nếu fallback, xem log runtime/model. |
| Tenant chat start. | `curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chat/start -H "Content-Type: application/json" -H "X-Tenant-Id: TODO_TENANT_ID" -d "{\"chatbotId\":\"TODO_CHATBOT_ID\",\"userExternalId\":\"demo-user-01\"}"` | Trả `conversationId`. | Nếu 401/403, chưa login tenant. Nếu `Chatbot does not belong to this tenant`, sai `chatbotId` hoặc login nhầm tenant. |
| Tenant chat send. | `curl.exe -s -b tmp\tenant-cookie.txt -X POST http://localhost:8080/api/chat/send -H "Content-Type: application/json" -H "X-Tenant-Id: TODO_TENANT_ID" -d "{\"conversationId\":\"TODO_TENANT_CONVERSATION_ID\",\"message\":\"Tôi cần sofa phòng khách nhỏ, dễ vệ sinh, ngân sách 10 triệu.\"}"` | Trả `reply`, `latencyMs`, `model`, `llmBaseUrl`; assistant không báo lỗi. | Nếu `llmBaseUrl` rỗng hoặc reply fallback, runtime/model lỗi. Xem `docker compose logs app`. |
| Kiểm tra history. | `curl.exe -s -b tmp\tenant-cookie.txt "http://localhost:8080/api/chat/conversations?chatbotId=TODO_CHATBOT_ID&limit=10"` và `curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/chat/conversation/TODO_CONVERSATION_ID/messages` | Có conversation và messages vừa gửi. | Nếu trống, đang dùng sai tenant/chatbot/userExternalId hoặc conversation chưa lưu. |

Không nên demo: gọi `/api/chat/**` bằng API key thuần không cookie session. Code security hiện yêu cầu authenticated session cho `/api/**`, trừ `/api/general/**` và `/api/login/**`.

## 6. Kiểm tra UI

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| Login UI. | `http://localhost:8080/login` | Form login hiện, đăng nhập admin/tenant được. | Nếu redirect lạ, logout bằng `POST /api/login/logout` hoặc xóa cookie browser. |
| Admin UI. | `http://localhost:8080/admin` | Platform admin vào được, tenant/member/ops dùng được. | Nếu bị redirect, đang không phải platform admin. Login lại `admin/admin123`. |
| Tenant UI. | `http://localhost:8080/tenant` | Tenant admin/member vào được. Tenant admin thấy tools KB/member/ops. | Nếu platform admin bị redirect về `/admin` là đúng hành vi. Login tenant account. |
| General chat UI. | `http://localhost:8080/chat/general/` | Chat public mở được, tạo hội thoại và gửi tin. | Nếu gửi chậm, model đang warm. Pre-warm trước demo. |
| Tenant chat UI. | `http://localhost:8080/chat?tenantId=TODO_TENANT_ID&chatbotId=TODO_CHATBOT_ID` | Chat mở được sau khi đã login tenant cùng browser. | Nếu báo thiếu tenant/chatbot, kiểm tra URL. Nếu 401/403 khi gửi, chưa login tenant hoặc session sai tenant. |
| Purchase request UI. | `http://localhost:8080/tenant/purchase-requests` | Tenant operator xem được danh sách request. | Nếu empty, chưa có request cho tenant; dùng request đã chuẩn bị hoặc tạo từ chat. |

Không nên demo: phần admin UI chatbot/binding dưới platform session nếu chưa sửa role/context. Dùng tenant UI hoặc tenant admin API cho chatbot/KB.

## 7. Kiểm tra purchase request

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| Xem danh sách request. | `curl.exe -s -b tmp\tenant-cookie.txt http://localhost:8080/api/purchase-requests` | Trả array request của tenant hiện tại. | Nếu 403, account không phải tenant operator. Nếu empty, chưa có request. |
| Tạo request từ chat. | Trong tenant chat nhập đủ nhu cầu, tên, phone, địa chỉ, rồi xác nhận mua khi assistant đã tới bước chốt. | Chat trả lời đã ghi nhận yêu cầu; `/tenant/purchase-requests` có row mới `NEW`. | Nếu không tạo, có thể chưa tới stage `close`. Dùng script đã chạy thử hoặc request mẫu. |
| Claim request. | `curl.exe -s -b tmp\member-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/claim` | Request có `assigned_to_member_id`, `claimed_at`. | Nếu đã assigned, claim sẽ không hợp lệ; chọn request khác hoặc dùng admin reassign. |
| Assign request. | `curl.exe -s -b tmp\tenant-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/assign -H "Content-Type: application/json" -d "{\"member_id\":\"TODO_MEMBER_ID\"}"` | Assignee đổi sang member đã chọn. | Nếu lỗi body, nhớ field là `member_id`, không phải `memberId`. Nếu 403, account không phải tenant admin. |
| Đổi trạng thái. | `curl.exe -s -b tmp\tenant-cookie.txt -X PUT http://localhost:8080/api/purchase-requests/TODO_REQUEST_ID/status -H "Content-Type: application/json" -d "{\"status\":\"CONTACTED\"}"` | Status đổi sang `CONTACTED`; sau đó có thể đổi `COMPLETED`. | Nếu status không hợp lệ, dùng `NEW`, `CONTACTED`, `COMPLETED` theo service hiện tại. |

Chức năng chắc demo: xem/xử lý purchase request nếu có dữ liệu.  
Chức năng cần chuẩn bị: tạo request live từ chat, vì phụ thuộc sales-flow stage và câu xác nhận.

## 8. Kiểm tra ngrok/link public nếu dùng

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| Quyết định có dùng live channel không. | TODO: xác nhận với nhóm có demo Messenger/Telegram hay không. | Nếu không demo live channel, bỏ qua mục này và dùng web chat. | Không cố demo ngrok nếu chưa chuẩn bị token/binding. |
| Kiểm tra public URL. | TODO: `ngrok http 8080` hoặc công cụ public HTTPS tương đương. | Có HTTPS URL public trỏ về backend `localhost:8080`. | Nếu không truy cập được, kiểm tra firewall/ngrok session. |
| Kiểm tra endpoint webhook Messenger. | `GET https://TODO_PUBLIC_URL/webhook/messenger?...` theo verify token đã cấu hình. | Chỉ dùng nếu đã cấu hình app/page ngoài platform. | Nếu verify fail, kiểm tra `MESSENGER_VERIFY_TOKEN`. |
| Kiểm tra endpoint webhook Telegram. | `POST https://TODO_PUBLIC_URL/webhook/telegram/TODO_SECRET_PATH` | Chỉ dùng nếu đã có binding Telegram. | Nếu fail, kiểm tra secret path, token, binding. |

Phân loại: Messenger/Telegram là chức năng có code nhưng không nên demo live nếu chưa chuẩn bị public URL, token, binding và test trước. Web chat là kênh demo chính chắc hơn.

## 9. Backup plan nếu model local chạy chậm

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| Pre-warm trước giờ demo. | Gửi 1 câu general chat và 1 câu tenant chat trước khi quay. | Request sau đó trả nhanh hơn, runtime còn sống. | Không evict runtime trước demo. |
| Kiểm tra model demo nhẹ. | `BASE_MODEL=TinyLlama/TinyLlama-1.1B-Chat-v1.0` trong Compose/env. | TinyLlama được dùng cho demo CPU local. | Nếu đang dùng model lớn, set lại `BASE_MODEL` rồi restart. |
| Tăng timeout warmup. | `LLM_STARTUP_TIMEOUT_MS=600000` | Backend đủ thời gian đợi Python ready. | Nếu vẫn timeout, dùng backup video/screenshot và không demo câu chat live dài. |
| Theo dõi log warmup. | `docker compose logs --no-color --tail=300 app` | Có `LLM READY`. | Nếu `LLM process exited` hoặc thiếu dependency, dùng Docker image build lại hoặc chuyển sang phần UI/DB/KB/purchase request đã chuẩn bị. |
| Backup nội dung trình bày. | Chuẩn bị sẵn screenshot/video chat thành công, JSON response và DB rows. | Có thể tiếp tục demo bằng bằng chứng đã lưu. | Nếu live chat lỗi, nói rõ model local đang warm/chậm và chuyển sang backup bằng chứng. |

Không nên làm trong demo: đổi provider/model/API key ngay trên sân khấu nếu chưa test trước.

## 10. Backup screenshots/video nếu live demo lỗi

| Cách kiểm tra | Lệnh/URL | Kết quả đạt | Cách xử lý nếu lỗi |
|---|---|---|---|
| Screenshot login/admin. | Chụp `/login`, `/admin` sau login platform. | Thể hiện phân quyền và tenant/member. | Nếu UI lỗi, dùng response `GET /api/me`, `GET /api/admin/tenants`. |
| Screenshot tenant KB/ops. | Chụp `/tenant` với KB Source URLs/Tenant Ops. | Thể hiện KB và trạng thái tenant. | Nếu UI lỗi, dùng `GET /api/kb/source-urls`, `GET /api/ops/tenant`. |
| Screenshot chat. | Chụp `/chat/general/` và tenant chat có reply thành công. | Có câu hỏi sản phẩm và reply assistant. | Nếu live model chậm, dùng screenshot đã chụp trước. |
| Screenshot purchase request. | Chụp `/tenant/purchase-requests`. | Có request với tên, phone, địa chỉ, status. | Nếu live tạo request thất bại, dùng request tạo thử trước buổi demo. |
| Backup log/file. | `docker compose logs --no-color --tail=200 app`; `chatbot/logs/chat.jsonl`; `chatbot/eval/results.json`. | Có bằng chứng runtime, chat log, benchmark artifact. | Nếu log quá dài, lọc đoạn có `LLM READY`, `KB_DIR`, conversation hoặc purchase request. |
| Backup video ngắn. | Quay trước 1 clip 30-60 giây cho chat và purchase request. | Có clip thay thế nếu live lỗi. | Nếu live lỗi, chuyển sang clip backup và giải thích đang dùng bằng chứng từ lần chạy thử cùng code. |

## Checklist cuối cùng trong 10 phút trước demo

- [ ] `docker compose ps` OK.
- [ ] Mở được `http://localhost:8080/login`.
- [ ] Login platform admin `admin/admin123` OK.
- [ ] Login tenant admin đã chọn OK.
- [ ] Tenant demo có chatbot id đúng.
- [ ] Tenant demo có `kb_dir` đúng môi trường.
- [ ] `chunks.jsonl`, `index.json`, `raw_urls.txt` tồn tại.
- [ ] General chat đã pre-warm.
- [ ] Tenant chat đã pre-warm.
- [ ] Có sẵn `TODO_TENANT_ID`, `TODO_CHATBOT_ID`, `TODO_MEMBER_ID`.
- [ ] Có ít nhất một purchase request để demo xử lý.
- [ ] Có screenshots/video backup.
- [ ] Không mở hoặc nhắc các chức năng không nên demo live nếu chưa chuẩn bị.

