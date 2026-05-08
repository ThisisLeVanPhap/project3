# P1 Demo Capability Report

Ngày rà soát: 2026-05-07  
Mục tiêu demo: chatbot tư vấn/gợi ý sản phẩm nội thất dùng RAG/gọi model, quản trị tenant, quản trị KB và quy trình chuyển nhu cầu mua hàng thành purchase request. Không trình bày theo hướng train/fine-tune model.

## 1. Tổng quan hệ thống có thể demo

Hệ thống hiện tại có 2 phần chính:

- Backend Spring Boot multi-tenant: đăng nhập platform/tenant, quản trị tenant/member, chatbot config, hội thoại, purchase request, KB source/rebuild, ops/benchmark, webhook Messenger/Telegram.
- Python chatbot service: FastAPI `/chat`, `/state`, `/feedback`, `/healthz`; mỗi tenant có thể được Spring Boot spawn một runtime Python riêng với `KB_DIR` tương ứng. Runtime hiện dùng `SimpleKb/BaselineRetriever` để truy xuất KB theo keyword/heuristic, sau đó gọi local model hoặc provider API tùy cấu hình chatbot.

Các điểm đã đối chiếu trực tiếp:

- README/docs: `README.md`, `docs/*.md`, `chatbot/README.md`, `chatbot/docs/*.md`, `multitenant/docs/*.md`.
- Docker/env: `docker-compose.yml`, `multitenant/Dockerfile`, `chatbot/Dockerfile`, `multitenant/src/main/resources/application.yml`.
- Backend route/controller/API/UI: các controller trong `multitenant/src/main/java/com/app/**`, static UI trong `multitenant/src/main/resources/static/**`.
- Python service: `chatbot/app/server.py`, `guardrails.py`, `sales_flow.py`, `retrieval_service.py`, `retrievers/baseline.py`, `tools/build_kb.py`, `tools/scrape_site.py`.
- Dữ liệu mẫu/migration: `multitenant/src/main/resources/db/migration/V*.sql`, `multitenant/docs/sql/demo_multi_tenant_setup.sql`, `chatbot/kb/**`, `chatbot/eval/results.json`.
- Test hiện có: Maven compile OK; Maven full test hiện lỗi ở test cũ liên quan `ChatResponse`; Python unittest hiện lỗi do thiếu dependency trong runtime kiểm tra và một số kỳ vọng guardrail/sales flow đã lệch.

Kết luận ngắn:

- Có thể demo được trọng tâm: web chat tổng quát, web chat theo tenant + RAG, quản trị KB source, benchmark retrieval từ artifact, purchase request sau hội thoại, và màn hình vận hành tenant.
- Cần chuẩn bị trước model/runtime, tenant account, chatbot instance, `kb_dir`, dữ liệu KB và ít nhất một kịch bản hội thoại đã thử trước.
- Không nên demo các claim kiểu API-key-only cho `/api/chat`, price reference, fine-tune/LoRA như tính năng sản phẩm, admin UI chatbot/binding dưới platform session, hoặc “toàn bộ test pass”.

## 2. Demo chắc chắn được

Các chức năng dưới đây không phụ thuộc nhiều vào chất lượng model hoặc network ngoài, miễn là database/backend đã chạy và migration thành công.

### 2.1 Đăng nhập và phân quyền platform/tenant

- Tên chức năng: Đăng nhập platform admin và tenant member.
- Actor sử dụng: Platform admin, tenant admin, tenant member.
- URL/API liên quan:
  - UI: `/login`, `/admin`, `/tenant`, `/tenant/purchase-requests`
  - API: `POST /api/login/admin`, `POST /api/login/tenant`, `POST /api/login/logout`, `GET /api/me`
- Dữ liệu cần chuẩn bị:
  - Platform admin hardcoded: `admin` / `admin123`.
  - Tenant mẫu từ migration V15: `admin@demo.local` / `admin123`, `member@demo.local` / `member123` cho tenant `demo_tenant`.
  - Nếu dùng tenant `demo_caco` hoặc `demo_article` từ `multitenant/docs/sql/demo_multi_tenant_setup.sql`, cần tạo thêm tenant member vì file SQL này chỉ tạo tenant/chatbot, chưa tạo account đăng nhập.
- Các bước demo:
  1. Mở `/login`.
  2. Đăng nhập platform admin, kiểm tra được điều hướng tới `/admin`.
  3. Logout, đăng nhập tenant admin hoặc tenant member, kiểm tra được điều hướng tới `/tenant`.
  4. Gọi hoặc quan sát `GET /api/me` trả về đúng role.
- Kết quả mong đợi:
  - Platform admin thấy dashboard `/admin`.
  - Tenant admin/member thấy dashboard `/tenant`.
  - Session cookie `SESSION` được dùng cho các API `/api/**` có bảo vệ.
- File/log/screenshot nên lưu làm bằng chứng:
  - Screenshot `/login`, `/admin`, `/tenant`.
  - Response `GET /api/me`.
  - Log backend nếu có lỗi đăng nhập.

### 2.2 Quản trị tenant và tenant member

- Tên chức năng: Platform admin tạo/xem tenant và tạo account tenant.
- Actor sử dụng: Platform admin.
- URL/API liên quan:
  - UI: `/admin`, tab Tenants/Members.
  - API: `GET /api/admin/tenants`, `POST /api/admin/tenants`, `GET /api/admin/tenant-members`, `POST /api/admin/tenant-members`.
- Dữ liệu cần chuẩn bị:
  - Đăng nhập platform admin.
  - Với demo RAG theo tenant, nên có tenant có `kb_dir` trỏ đúng thư mục KB:
    - Local Windows: `F:/20251/prj3/chatbot/kb/noithatcaco`
    - Docker app container: `/opt/app/chatbot/kb/noithatcaco`
- Các bước demo:
  1. Đăng nhập platform admin.
  2. Mở `/admin`, tải danh sách tenant.
  3. Tạo tenant hoặc kiểm tra tenant mẫu đã có.
  4. Tạo tenant admin/member cho tenant demo.
- Kết quả mong đợi:
  - Tenant được lưu trong bảng `tenants`.
  - Tenant member đăng nhập được qua `/api/login/tenant`.
- File/log/screenshot nên lưu làm bằng chứng:
  - Screenshot danh sách tenant/member.
  - Response `GET /api/admin/tenants`.
  - DB rows `tenants`, `tenant_members`.

### 2.3 Quản lý nguồn KB của tenant

- Tên chức năng: Xem/thêm/xóa URL nguồn KB.
- Actor sử dụng: Tenant admin.
- URL/API liên quan:
  - UI: `/tenant`, khu vực KB Source URLs.
  - API: `GET /api/kb/source-urls`, `POST /api/kb/source-urls`, `DELETE /api/kb/source-urls`.
- Dữ liệu cần chuẩn bị:
  - Tenant admin đã đăng nhập.
  - Tenant có `kb_dir` hợp lệ và writable.
  - File `raw_urls.txt` trong thư mục KB, ví dụ `chatbot/kb/noithatcaco/raw_urls.txt`.
- Các bước demo:
  1. Đăng nhập tenant admin.
  2. Mở `/tenant`.
  3. Tải danh sách URL nguồn.
  4. Thêm một URL hợp lệ dạng `https://...`.
  5. Xóa URL vừa thêm nếu chỉ dùng để demo.
- Kết quả mong đợi:
  - API đọc/ghi được `raw_urls.txt`.
  - URL không hợp lệ bị từ chối.
- File/log/screenshot nên lưu làm bằng chứng:
  - Screenshot khu vực KB Source URLs.
  - File `chatbot/kb/<tenant>/raw_urls.txt` trước/sau demo.
  - Log backend nếu ghi file thất bại.

### 2.4 Xem benchmark retrieval đã chạy sẵn

- Tên chức năng: Báo cáo benchmark retrieval từ artifact.
- Actor sử dụng: Platform admin.
- URL/API liên quan:
  - API: `GET /api/ops/benchmark-summary`
  - UI: `/admin`, khu vực ops/benchmark nếu dùng màn hình hiện có.
- Dữ liệu cần chuẩn bị:
  - File `chatbot/eval/results.json` hiện có.
  - Đăng nhập platform admin.
- Các bước demo:
  1. Đăng nhập platform admin.
  2. Gọi `GET /api/ops/benchmark-summary` hoặc mở khu vực benchmark trong `/admin`.
  3. Trình bày kết quả so sánh các mode retrieval từ artifact.
- Kết quả mong đợi:
  - Dataset hiện ghi 48 câu hỏi trên KB `noithatcaco`.
  - Kết quả artifact hiện tại:
    - `keyword`: Recall@5 `0.7917`, MRR `0.7333`.
    - `vector`: Recall@5 `0.6667`, MRR `0.4639`.
    - `hybrid`: Recall@5 `0.7917`, MRR `0.6708`.
    - `hybrid_rerank`: Recall@5 `0.7708`, MRR `0.6285`.
  - Nên nói đúng: runtime `/chat` hiện đang dùng baseline keyword/heuristic; vector/hybrid là phần eval/benchmark, không phải mode runtime mặc định trong `server.py`.
- File/log/screenshot nên lưu làm bằng chứng:
  - `chatbot/eval/results.json`.
  - Response `GET /api/ops/benchmark-summary`.
  - Screenshot bảng benchmark.

### 2.5 Quản lý purchase request đã có dữ liệu

- Tên chức năng: Xem, claim, assign, đổi trạng thái purchase request.
- Actor sử dụng: Tenant admin, tenant member.
- URL/API liên quan:
  - UI: `/tenant/purchase-requests`.
  - API: `GET /api/purchase-requests`, `POST /api/purchase-requests/{id}/claim`, `POST /api/purchase-requests/{id}/assign`, `POST /api/purchase-requests/{id}/status`.
- Dữ liệu cần chuẩn bị:
  - Tenant admin/member đã đăng nhập.
  - Có ít nhất một row `purchase_requests` thuộc tenant hiện tại. Row này có thể được tạo từ hội thoại chatbot hoặc chuẩn bị trước trong DB cho phần demo quản trị.
  - Nếu demo assign, cần có ít nhất hai tenant member trong cùng tenant.
- Các bước demo:
  1. Đăng nhập tenant admin/member.
  2. Mở `/tenant/purchase-requests`.
  3. Lọc trạng thái nếu cần.
  4. Claim request chưa có người phụ trách.
  5. Tenant admin assign request cho member khác.
  6. Đổi trạng thái `NEW -> CONTACTED -> COMPLETED`.
- Kết quả mong đợi:
  - Danh sách chỉ hiển thị request của tenant hiện tại.
  - `claim` chỉ thành công khi request chưa có assignee.
  - `assign` yêu cầu tenant admin.
  - Trạng thái được cập nhật đúng.
- File/log/screenshot nên lưu làm bằng chứng:
  - Screenshot `/tenant/purchase-requests`.
  - DB rows `purchase_requests`.
  - Log backend khi đổi trạng thái.

## 3. Demo được nhưng cần chuẩn bị dữ liệu/tài khoản/env

Các chức năng dưới đây là trọng tâm demo nhưng cần chuẩn bị kỹ để tránh cold start model, thiếu tenant account, sai `kb_dir`, hoặc thiếu dữ liệu.

### 3.1 Web chat tư vấn nội thất tổng quát

- Tên chức năng: Public general consumer chat.
- Actor sử dụng: Người mua/khách truy cập web.
- URL/API liên quan:
  - UI: `/chat/general/`
  - API: `POST /api/general/chat/start`, `POST /api/general/chat/send`, `GET /api/general/chat/conversations`, `GET /api/general/chat/{conversationId}/messages`, rename/delete conversation.
  - Python runtime: `/healthz`, `/chat`, `/state`.
- Dữ liệu cần chuẩn bị:
  - Migration V21 tạo system tenant và chatbot `general_consumer`.
  - Backend, Postgres và Python runtime chạy được.
  - Local model đã download/cache hoặc cấu hình provider API hợp lệ.
  - Nếu chạy Docker, chờ runtime warm up xong trước khi vào demo.
- Các bước demo:
  1. Mở `/chat/general/`.
  2. Bắt đầu hội thoại mới.
  3. Hỏi nhu cầu nội thất tự nhiên, ví dụ: “Tôi cần sofa cho phòng khách nhỏ, nhà có trẻ con, ngân sách khoảng 10 triệu.”
  4. Hỏi tiếp câu so sánh hoặc gợi ý theo phong cách.
  5. Đổi tên/xóa hội thoại nếu muốn demo quản lý lịch sử.
- Kết quả mong đợi:
  - UI tạo conversation mới.
  - Assistant trả lời theo hướng tư vấn nhu cầu, không cần login.
  - Tin nhắn được lưu trong DB.
- File/log/screenshot nên lưu làm bằng chứng:
  - Screenshot `/chat/general/`.
  - Log app lúc spawn runtime tenant system.
  - `chatbot/logs/chat.jsonl`.
  - DB rows `conversations`, `messages`.

### 3.2 Web chat theo tenant dùng RAG trên KB nội thất

- Tên chức năng: Tenant-specific RAG chat.
- Actor sử dụng: Người mua hoặc nhân sự demo dưới session tenant.
- URL/API liên quan:
  - UI: `/chat?tenantId=<tenantId>&chatbotId=<chatbotId>`
  - API: `POST /api/chat/start`, `POST /api/chat/send`, `GET /api/chat/conversations`, `GET /api/chat/{conversationId}/messages`.
  - Python runtime: `/chat`, `/state`.
- Dữ liệu cần chuẩn bị:
  - Tenant có chatbot instance `tenant_sales`.
  - Tenant có `kb_dir` trỏ tới KB đã build, ví dụ `chatbot/kb/noithatcaco`.
  - Tenant member đã đăng nhập trong cùng browser/session. Lưu ý: code hiện bảo vệ `/api/chat/**`; chỉ gửi `X-Tenant-Id` hoặc `X-API-Key` từ browser/curl không đủ nếu chưa có session đăng nhập.
  - Nếu dùng SQL mẫu `demo_multi_tenant_setup.sql`, cần:
    - Tạo tenant member cho `demo_caco`/`demo_article`.
    - Sửa `kb_dir` khi chạy Docker từ path Windows sang `/opt/app/chatbot/kb/...`.
- Các bước demo:
  1. Đăng nhập tenant admin/member của tenant cần demo.
  2. Mở `/chat?tenantId=<tenantId>&chatbotId=<chatbotId>`.
  3. Hỏi câu có đủ ngữ cảnh để kích hoạt retrieval, ví dụ: “Tôi cần sofa cho phòng khách nhỏ, dễ vệ sinh, ngân sách khoảng 10 triệu, có sản phẩm nào phù hợp không?”
  4. Hỏi thêm câu theo chính sách/sản phẩm có trong KB, ví dụ: “Có hỗ trợ giao hàng hoặc bảo hành như thế nào?”
  5. Mở log/DB để chứng minh tin nhắn và runtime theo tenant.
- Kết quả mong đợi:
  - Spring tạo hoặc tái dùng runtime Python theo tenant.
  - Runtime nhận `KB_DIR` của tenant.
  - Câu trả lời có nội dung bám KB/sản phẩm hơn câu chat chung.
  - Conversation/message được lưu theo tenant.
- File/log/screenshot nên lưu làm bằng chứng:
  - Screenshot web chat tenant.
  - `docker compose logs --no-color --tail=200 app` hoặc log backend có dòng spawn runtime/`KB_DIR`.
  - `chatbot/logs/chat.jsonl`.
  - DB rows `conversations`, `messages`.
  - File KB: `chatbot/kb/noithatcaco/chunks.jsonl`, `chatbot/kb/noithatcaco/index.json`.

### 3.3 Demo tách biệt KB theo tenant

- Tên chức năng: Multi-tenant RAG isolation.
- Actor sử dụng: Người demo với hai tenant khác nhau.
- URL/API liên quan:
  - UI: `/chat?tenantId=<tenantA>&chatbotId=<botA>`, `/chat?tenantId=<tenantB>&chatbotId=<botB>`
  - API: `/api/chat/start`, `/api/chat/send`, `GET /api/ops/platform`, `GET /api/runtime/llm`.
- Dữ liệu cần chuẩn bị:
  - Hai tenant có chatbot và member đăng nhập:
    - `demo_caco` với KB `noithatcaco`.
    - `demo_article` với KB `article`.
  - `kb_dir` đúng môi trường chạy.
  - Model/runtime đã warm up.
- Các bước demo:
  1. Đăng nhập tenant A, hỏi câu về sản phẩm/chính sách thuộc KB A.
  2. Đăng nhập tenant B hoặc dùng session tenant B, hỏi cùng kiểu câu.
  3. Dùng platform admin xem runtime hoặc log để thấy mỗi tenant có runtime/KB riêng.
- Kết quả mong đợi:
  - Câu trả lời không trộn dữ liệu giữa hai tenant.
  - Ops/runtime thể hiện tenant/base URL/runtime khác nhau.
- File/log/screenshot nên lưu làm bằng chứng:
  - Hai screenshot chat cạnh nhau.
  - Response `GET /api/ops/platform` hoặc `GET /api/runtime/llm`.
  - Log spawn runtime với `KB_DIR` khác nhau.

### 3.4 Tạo purchase request từ hội thoại chatbot

- Tên chức năng: Chuyển nhu cầu mua hàng từ chat sang purchase request.
- Actor sử dụng: Người mua, tenant operator.
- URL/API liên quan:
  - UI chat tenant: `/chat?tenantId=<tenantId>&chatbotId=<chatbotId>`
  - API chat: `/api/chat/start`, `/api/chat/send`
  - API quản trị: `GET /api/purchase-requests`
  - Python state: `/state`
- Dữ liệu cần chuẩn bị:
  - Tenant chat hoạt động ổn định.
  - Hội thoại phải đi qua luồng `tenant_sales` tới stage `close`, sau đó user xác nhận mua. Code hiện đặt `trigger_purchase_request=true` khi `old_stage == "close"` và intent là `confirm`.
  - Cần thu đủ thông tin cơ bản: tên, số điện thoại hợp lệ, địa chỉ/giao hàng và sản phẩm mong muốn.
  - Nên có kịch bản hội thoại đã chạy thử trước; không nên chỉ gửi `CONFIRM` ngay từ đầu.
- Các bước demo:
  1. Mở chat tenant đã đăng nhập.
  2. User nêu nhu cầu, ngân sách, không gian, phong cách.
  3. Assistant gợi ý sản phẩm.
  4. User cung cấp tên, số điện thoại, địa chỉ.
  5. Khi assistant đã chuyển sang chốt đơn/handoff, user xác nhận mua.
  6. Mở `/tenant/purchase-requests` để xem request mới.
- Kết quả mong đợi:
  - Backend tạo lead/purchase request idempotent theo conversation.
  - Chat trả về thông báo đã ghi nhận yêu cầu, kèm mã request nếu tạo được.
  - Purchase request xuất hiện ở trạng thái `NEW`.
- File/log/screenshot nên lưu làm bằng chứng:
  - Screenshot đoạn chat có xác nhận mua.
  - Screenshot `/tenant/purchase-requests` với request mới.
  - DB rows `leads`, `purchase_requests`, `conversations.lead_created`.
  - `chatbot/logs/chat.jsonl`, log backend quanh thời điểm tạo request.

### 3.5 Rebuild KB từ danh sách source URL

- Tên chức năng: Tenant admin rebuild KB.
- Actor sử dụng: Tenant admin.
- URL/API liên quan:
  - UI: `/tenant`
  - API: `POST /api/kb/rebuild`, `GET /api/ops/tenant`
- Dữ liệu cần chuẩn bị:
  - Tenant có `kb_dir` writable.
  - `raw_urls.txt` có URL hợp lệ.
  - `PYTHON_BIN` và `MODEL_SERVER_DIR` đúng.
  - Network tới website nguồn ổn định nếu scrape live.
  - Nên backup KB trước khi demo.
- Các bước demo:
  1. Đăng nhập tenant admin.
  2. Kiểm tra source URLs.
  3. Bấm rebuild hoặc gọi `POST /api/kb/rebuild`.
  4. Theo dõi trạng thái/histories trong tenant ops.
  5. Sau rebuild, hỏi chat về nội dung vừa cập nhật.
- Kết quả mong đợi:
  - Backend chạy script scrape/build KB.
  - Runtime tenant được evict để lần sau dùng KB mới.
  - File `chunks.jsonl`, `index.json` được tạo/cập nhật.
- File/log/screenshot nên lưu làm bằng chứng:
  - Screenshot trạng thái rebuild.
  - `chatbot/kb/<tenant>/chunks.jsonl`, `index.json`, `raw_urls.txt`.
  - Log backend của rebuild.

### 3.6 Feedback người dùng

- Tên chức năng: Ghi nhận feedback tốt/xấu cho câu trả lời.
- Actor sử dụng: Người dùng chat hoặc kênh webhook.
- URL/API liên quan:
  - Python: `POST /feedback`
  - Backend feedback repository/webhook flow khi user nhắn `RATE GOOD/BAD` trên Messenger.
- Dữ liệu cần chuẩn bị:
  - Runtime Python chạy được.
  - Nếu demo qua webhook thật, cần binding/token/channel.
- Các bước demo:
  1. Gửi một feedback mẫu tới runtime hoặc dùng kịch bản webhook.
  2. Kiểm tra log feedback.
- Kết quả mong đợi:
  - Feedback được append vào file log.
- File/log/screenshot nên lưu làm bằng chứng:
  - `chatbot/logs/feedback.jsonl`.
  - Log webhook nếu dùng kênh Messenger.

## 4. Có code nhưng rủi ro khi demo

### 4.1 API-key-only cho tenant chat

- Tài liệu/curl có chỗ gợi ý gọi `/api/chat/start` và `/api/chat/send` chỉ với `X-API-Key` hoặc `X-Tenant-Id`.
- Code hiện có `SecurityConfig` yêu cầu authenticated cho `/api/**`, trừ một số path public như `/api/login/**` và `/api/general/**`.
- `TenantResolver` có hỗ trợ header API key, nhưng security filter chặn trước khi vào controller nếu không có session.
- Khuyến nghị demo: dùng browser đã đăng nhập tenant, hoặc demo public `/api/general/**`. Không trình bày `/api/chat/**` như API public chỉ cần API key nếu chưa sửa security.

### 4.2 Admin UI chatbot/binding dưới platform session

- `/admin` chỉ dành platform admin, nhưng các endpoint chatbot/binding như `/api/chatbots`, `/api/messenger/bindings`, `/api/telegram/bindings` yêu cầu tenant admin/tenant context.
- Platform admin session không tự set `TenantContext` theo header.
- Khuyến nghị demo: dùng `/admin` cho tenant/member/ops; dùng tenant account hoặc API phù hợp cho phần chatbot/binding.

### 4.3 Gọi local model lúc cold start

- Docker app sẽ spawn Python runtime per tenant và chờ `/healthz ready=true`.
- Lần đầu có thể chậm do tải/warm model, thiếu RAM/CPU hoặc thiếu cache Hugging Face.
- Nếu model chưa ready, Spring có fallback message, nhưng đó không phải kết quả demo tốt cho RAG.
- Khuyến nghị demo: pre-warm từng tenant bằng một câu hỏi thử trước buổi demo.

### 4.4 Provider API bên ngoài

- Python có code gọi provider `claude`/API model, Spring truyền `apiKey`, `apiBaseUrl`, `apiModel`.
- Cần network và key hợp lệ; chất lượng/latency phụ thuộc dịch vụ ngoài.
- Khuyến nghị demo giữa kỳ: dùng local model đã cache hoặc một provider đã test trước, không đổi provider ngay trong buổi demo.

### 4.5 Purchase request tự tạo từ chat phụ thuộc stage

- `trigger_purchase_request` hiện phụ thuộc `old_stage == "close"` và intent `confirm`.
- Nếu user xác nhận quá sớm hoặc thiếu thông tin, request có thể không được tạo.
- Khuyến nghị demo: dùng script hội thoại đã chạy thử, và chuẩn bị sẵn một request mẫu để vẫn demo được màn hình vận hành nếu luồng live không đi tới close.

### 4.6 KB rebuild scrape live website

- Code rebuild có thật, nhưng phụ thuộc URL nguồn, network, SSL, HTML website và quyền ghi file.
- Website nguồn có thể đổi layout hoặc chặn request.
- Khuyến nghị demo: ưu tiên show source URLs/status và KB đã build sẵn; chỉ rebuild nếu đã chạy thử ngay trước demo.

### 4.7 Webhook Messenger/Telegram end-to-end

- Code có binding, webhook, conversation continuity, handoff và feedback.
- Demo thật cần token hợp lệ, public HTTPS/ngrok, cấu hình webhook ở platform ngoài và network outbound.
- Khuyến nghị demo giữa kỳ: nếu chưa chuẩn bị đầy đủ, chỉ trình bày code/API hoặc mô phỏng webhook nội bộ; không hứa demo live channel.

### 4.8 Price reference

- Có file `chatbot/kb/price_reference.json` và helper trong `guardrails.py`, nhưng `rule_reply` hiện không gọi luồng price reference.
- Không nên demo câu hỏi kiểu “giá khoảng X thì mua gì” như một tính năng price-reference chắc chắn.

### 4.9 Test suite hiện chưa xanh

- `mvn -q -DskipTests compile` trong `multitenant` chạy OK.
- `mvn -q test` hiện: 70 tests, 3 errors. Lỗi chính do test cũ gọi constructor `ChatResponse(String,Integer,String,String)` trong khi record hiện có nhiều field hơn.
- Python unittest bằng bundled Python hiện: 9 tests, 1 failure, 4 errors; lỗi gồm thiếu package `requests` trong runtime kiểm tra và kỳ vọng guardrail/sales flow tiếng Việt đã lệch code.
- Khuyến nghị demo: không nói “toàn bộ test pass”. Chỉ nói compile backend OK và có test hiện hữu nhưng cần cập nhật theo contract mới.

### 4.10 API contract cũ của Python

- `chatbot/docs/api-contract.md` còn mô tả contract kiểu `query/citations`.
- Code thật trong `chatbot/app/server.py` dùng `ChatReq` với `message`, `history`, `gen`, `conversation_id`, `channel`, `tenant_id`; response gồm `reply`, `latency_ms`, `model`, `adapter`, `trigger_purchase_request`, `captured_phone`, `captured_name`.
- Khuyến nghị demo: dùng contract trong code hoặc `multitenant/docs/api-contract.md` mới hơn.

## 5. Chưa nên demo

- Fine-tune/LoRA training như tính năng chính của hệ thống. Repo có dấu vết adapter/model config, nhưng mục tiêu hiện phù hợp hơn là RAG + gọi model + vận hành tenant.
- Public tenant chat API chỉ bằng `X-API-Key` cho `/api/chat/**`, vì hiện bị security session chặn.
- Admin UI tạo/sửa chatbot/binding dưới platform admin, vì role/context chưa khớp controller.
- Price reference theo file `price_reference.json`, vì helper chưa được nối vào luồng trả lời chính.
- `/actuator/health` từ nút Ping Health nếu chưa thêm actuator dependency/config; có khả năng 404.
- Claim runtime đang dùng vector/hybrid retrieval cho mọi câu chat. Runtime hiện dùng baseline retriever; vector/hybrid nằm ở phần eval/benchmark.
- Real Messenger/Telegram live nếu chưa có token, webhook public URL, verify secret và test gửi/nhận trước buổi demo.
- Cam kết “test suite pass 100%”. Hiện compile OK nhưng full test đang lỗi.
- Các nghiệp vụ checkout/thanh toán/tồn kho thật/vận chuyển thật. Code hiện thiên về tư vấn, lead/purchase request và handoff.

## 6. Điều kiện cần chuẩn bị trước demo

### 6.1 Hạ tầng chạy demo

- Chạy Postgres và Spring Boot app bằng Docker hoặc local.
- Nếu dùng Docker:
  - `docker compose up --build -d`
  - Chờ app và Postgres ready.
  - Chờ Python runtime warm khi gửi câu đầu tiên.
  - Đảm bảo volume `./chatbot:/opt/app/chatbot` có KB và log writable.
- Nếu chạy local:
  - Có Java/Maven.
  - Có Python và cài requirements cho `chatbot`.
  - Set `PYTHON_BIN`, `MODEL_SERVER_DIR`, `BASE_MODEL` phù hợp.

### 6.2 Dữ liệu tenant/chatbot

- Platform admin: `admin` / `admin123`.
- Tenant account có sẵn từ migration:
  - `admin@demo.local` / `admin123`
  - `member@demo.local` / `member123`
  - Thuộc tenant `demo_tenant`.
- Với demo CaCo/Article:
  - Chạy hoặc import `multitenant/docs/sql/demo_multi_tenant_setup.sql`.
  - Tạo tenant member cho `demo_caco` và `demo_article`.
  - Kiểm tra `kb_dir` đúng môi trường:
    - Local Windows: `F:/20251/prj3/chatbot/kb/noithatcaco`, `F:/20251/prj3/chatbot/kb/article`.
    - Docker: `/opt/app/chatbot/kb/noithatcaco`, `/opt/app/chatbot/kb/article`.

### 6.3 Model/runtime

- Pre-warm từng tenant demo bằng một câu chat thử trước khi bắt đầu.
- Ghi lại port/base URL runtime từ `GET /api/runtime/llm` hoặc log app.
- Nếu dùng provider ngoài, kiểm tra key/network/latency trước; không nhập key mới trong lúc demo.

### 6.4 KB và câu hỏi demo

- Kiểm tra các file tồn tại:
  - `chatbot/kb/noithatcaco/chunks.jsonl`
  - `chatbot/kb/noithatcaco/index.json`
  - `chatbot/kb/noithatcaco/raw_urls.txt`
  - `chatbot/eval/results.json`
- Chuẩn bị 3 nhóm câu hỏi:
  - Gợi ý sản phẩm: “Tôi cần sofa cho phòng khách nhỏ, dễ vệ sinh, ngân sách khoảng 10 triệu.”
  - Chính sách/dịch vụ: câu hỏi có nội dung trong KB.
  - Chốt mua: tên, số điện thoại hợp lệ, địa chỉ, xác nhận mua sau khi assistant đã tới close stage.

### 6.5 Bằng chứng nên chuẩn bị

- Screenshot:
  - `/login`
  - `/admin` tenant/member/benchmark
  - `/tenant` KB source/ops
  - `/chat/general/`
  - `/chat?tenantId=...&chatbotId=...`
  - `/tenant/purchase-requests`
- Log/file:
  - `docker compose logs --no-color --tail=200 app`
  - `chatbot/logs/chat.jsonl`
  - `chatbot/logs/feedback.jsonl`
  - `chatbot/eval/results.json`
  - DB rows `tenants`, `tenant_members`, `chatbot_instances`, `conversations`, `messages`, `purchase_requests`
- Verification:
  - Maven compile OK.
  - Full test hiện có lỗi, không dùng làm bằng chứng pass.

## 7. Kịch bản demo đề xuất cho giữa kỳ

### Pha 1: Mở hệ thống và phân quyền

1. Mở `/login`.
2. Đăng nhập platform admin `admin/admin123`.
3. Mở `/admin`, show danh sách tenant/member.
4. Tạo hoặc chỉ ra tenant demo và tenant member đã chuẩn bị.

Mục tiêu trình bày: hệ thống là multi-tenant, có phân quyền platform và tenant, không phải một chatbot đơn lẻ hardcode.

### Pha 2: Chứng minh dữ liệu RAG và benchmark

1. Trong `/admin`, mở benchmark summary hoặc gọi `GET /api/ops/benchmark-summary`.
2. Trình bày artifact `chatbot/eval/results.json` với 48 câu hỏi trên KB `noithatcaco`.
3. Nói rõ runtime demo đang dùng baseline keyword/heuristic retriever; benchmark có so sánh thêm vector/hybrid để đánh giá.

Mục tiêu trình bày: nhóm đã có KB, có cách đo retrieval, và không claim sai là mọi mode đều đang chạy trong runtime.

### Pha 3: Tenant admin quản trị KB

1. Logout platform, đăng nhập tenant admin.
2. Mở `/tenant`.
3. Show `raw_urls.txt` qua UI KB Source URLs.
4. Nếu đã test trước, chạy rebuild; nếu chưa, chỉ show nguồn và trạng thái để tránh rủi ro network.

Mục tiêu trình bày: tenant tự quản nguồn tri thức, hệ thống build KB theo tenant.

### Pha 4: Chat tư vấn tổng quát

1. Mở `/chat/general/`.
2. Hỏi một nhu cầu nội thất tự nhiên.
3. Show lịch sử hội thoại hoặc rename/delete conversation nếu cần.

Mục tiêu trình bày: khách public có thể chat tư vấn nội thất mà không cần login.

### Pha 5: Chat RAG theo tenant

1. Đăng nhập tenant đã chuẩn bị.
2. Mở `/chat?tenantId=<tenantId>&chatbotId=<chatbotId>`.
3. Hỏi câu gợi ý sản phẩm có nhiều tiêu chí: không gian, ngân sách, phong cách, trẻ em/thú cưng.
4. Hỏi tiếp câu về chính sách hoặc sản phẩm có trong KB.
5. Mở log hoặc ops runtime để chứng minh đang dùng KB tenant.

Mục tiêu trình bày: cùng một hệ thống có thể phục vụ tenant khác nhau, mỗi tenant có KB riêng, câu trả lời bám dữ liệu nội thất.

### Pha 6: Chuyển nhu cầu thành purchase request

1. Trong chat tenant, tiếp tục hội thoại tới bước chốt.
2. User cung cấp tên, số điện thoại hợp lệ, địa chỉ.
3. User xác nhận mua sau khi assistant đã hỏi xác nhận/chốt.
4. Mở `/tenant/purchase-requests` để show request mới.
5. Claim/assign/đổi trạng thái request.

Mục tiêu trình bày: chatbot không chỉ trả lời mà còn tạo đầu việc vận hành cho nhân sự bán hàng.

### Pha 7: Kết thúc bằng bằng chứng kỹ thuật

1. Show `chatbot/logs/chat.jsonl` hoặc log app ngắn.
2. Show DB/API conversations/messages/purchase_requests nếu cần.
3. Nêu rõ giới hạn hiện tại:
   - Full test chưa xanh.
   - API-key-only cho tenant chat chưa nên demo.
   - Price reference và live Messenger/Telegram chưa nên hứa nếu chưa cấu hình riêng.

Mục tiêu trình bày: demo trung thực, bám code hiện tại và có kế hoạch nâng cấp rõ ràng sau giữa kỳ.

