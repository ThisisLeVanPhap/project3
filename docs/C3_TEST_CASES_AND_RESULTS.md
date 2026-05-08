# C.3 Dữ liệu, test cases và kết quả thử nghiệm

## 1. Mục đích

Tài liệu này mô tả dữ liệu đầu vào, dữ liệu đầu ra, test cases và kết quả thử nghiệm của hệ thống chatbot tư vấn/gợi ý sản phẩm nội thất sử dụng RAG và tích hợp mô hình ngôn ngữ lớn qua API.

Mục đích của bộ kiểm thử:

- Kiểm tra khả năng quản lý dữ liệu sản phẩm nội thất theo tenant.
- Kiểm tra quy trình xử lý dữ liệu sản phẩm thành knowledge base phục vụ truy xuất tri thức.
- Đánh giá khả năng retrieval trả về đúng thông tin sản phẩm/chính sách liên quan.
- Kiểm tra chatbot hỏi đáp, gợi ý/tư vấn sản phẩm và duy trì ngữ cảnh hội thoại.
- Kiểm tra API backend, Python AI/RAG service và luồng tích hợp frontend - backend - AI/RAG service.
- Ghi nhận kết quả thử nghiệm theo nhóm chức năng để phục vụ nghiệm thu sản phẩm.

## 2. Dữ liệu đầu vào

### 2.1. Dữ liệu sản phẩm nội thất

Dữ liệu sản phẩm và tri thức được tổ chức theo từng tenant trong thư mục `chatbot/kb/`. Các nguồn dữ liệu tiêu biểu:

- `chatbot/kb/noithatcaco`: dữ liệu sản phẩm, chính sách và nội dung tư vấn của tenant demo CaCo.
- `chatbot/kb/article`: dữ liệu nội thất theo phong cách Article.
- `chatbot/kb/castlery`: dữ liệu nội thất theo phong cách Castlery.
- `chatbot/kb/price_reference.json`: dữ liệu tham chiếu giá theo nhóm sản phẩm.

Cấu trúc dữ liệu đầu vào của mỗi knowledge base:

- `raw_urls.txt`: danh sách URL nguồn sản phẩm/chính sách.
- `docs.jsonl`: dữ liệu sản phẩm/chính sách sau thu thập.
- `chunks.jsonl`: các đoạn tri thức phục vụ retrieval.
- `index.json`: chỉ mục truy xuất.

### 2.2. Câu hỏi/yêu cầu của người dùng

Câu hỏi kiểm thử bao gồm các nhóm nội dung:

- Hỏi thông tin sản phẩm: sofa, bàn ăn, giường, tủ, ghế, nội thất phòng khách/phòng ngủ.
- Hỏi theo nhu cầu sử dụng: căn hộ nhỏ, phòng khách nhỏ, ngân sách giới hạn, phong cách hiện đại.
- Hỏi theo thuộc tính sản phẩm: chất liệu, màu sắc, kích thước, kiểu dáng.
- Hỏi chính sách: thanh toán, giao hàng, đổi trả, bảo hành.
- Hỏi tư vấn mua hàng nhiều lượt: thay đổi ngân sách, thay đổi phong cách, xác nhận nhu cầu.
- Yêu cầu tạo purchase request thông qua lệnh xác nhận trong hội thoại.

### 2.3. Bộ lọc hoặc tiêu chí gợi ý sản phẩm

Các tiêu chí được dùng trong test cases tư vấn/gợi ý:

- Loại sản phẩm: sofa, bàn ăn, bàn làm việc, giường, tủ.
- Không gian sử dụng: phòng khách, phòng ngủ, căn hộ nhỏ, chung cư.
- Ngân sách: giá thấp, khoảng giá trung bình, mức giá cụ thể.
- Phong cách: hiện đại, tối giản, Scandinavian, gỗ tự nhiên.
- Chất liệu: gỗ, vải, da, nệm.
- Màu sắc/kích thước: màu nâu, màu trắng, gọn, 2 chỗ, phù hợp phòng nhỏ.

### 2.4. Request API mẫu

Tạo conversation chat theo tenant:

```json
{
  "chatbotId": "e08a7b4f-ebfb-4874-a119-b90e95e85fc7",
  "userExternalId": "demo-user"
}
```

Gửi tin nhắn:

```json
{
  "conversationId": "conversation-uuid",
  "message": "Tôi muốn mua sofa cho phòng khách nhỏ, ngân sách khoảng 10 triệu"
}
```

Thêm URL nguồn dữ liệu sản phẩm:

```json
{
  "url": "https://example.com/products/sofa"
}
```

Tạo/cập nhật chatbot:

```json
{
  "name": "Sales Bot",
  "channel": "web",
  "personaJson": "{\"tone\":\"friendly\"}",
  "responseStyle": "natural",
  "mode": "tenant_sales",
  "provider": "local",
  "apiModel": null,
  "apiKey": null,
  "apiBaseUrl": null
}
```

### 2.5. Dữ liệu cấu hình chatbot/người dùng

Dữ liệu cấu hình gồm:

- Tenant: `id`, `code`, `name`, `apiKey`, `kbDir`, `status`.
- Chatbot instance: `id`, `tenantId`, `name`, `channel`, `persona`, `responseStyle`, `mode`, `provider`, `apiModel`, `apiBaseUrl`.
- User/session: platform admin, tenant admin, tenant member.
- Runtime AI/RAG: `KB_DIR`, `BASE_MODEL`, `MAX_NEW_TOKENS`, `TEMPERATURE`, `TOP_P`, `TOP_K`.
- Kênh tích hợp: Messenger page binding, Telegram bot binding.

## 3. Dữ liệu đầu ra

### 3.1. Kết quả truy xuất tri thức

Kết quả retrieval là danh sách các đoạn tri thức phù hợp với câu hỏi người dùng. Dữ liệu này được dùng làm context khi xây prompt cho mô hình ngôn ngữ lớn.

Dạng dữ liệu nội bộ tiêu biểu:

```json
{
  "title": "Mẫu sofa phòng khách nhỏ",
  "url": "https://example.com/sofa-small-room",
  "content": "Đoạn nội dung sản phẩm hoặc tư vấn liên quan",
  "score": 0.91
}
```

### 3.2. Câu trả lời chatbot

Response chat từ backend:

```json
{
  "reply": "Với phòng khách nhỏ và ngân sách khoảng 10 triệu, bạn nên ưu tiên sofa 2 chỗ hoặc sofa góc gọn...",
  "latencyMs": 842,
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "adapter": "",
  "llmBaseUrl": "http://127.0.0.1:8101"
}
```

Response trực tiếp từ Python chatbot service:

```json
{
  "reply": "Nội dung tư vấn",
  "latency_ms": 842,
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "adapter": null,
  "trigger_purchase_request": false,
  "captured_phone": null,
  "captured_name": null
}
```

### 3.3. Danh sách sản phẩm gợi ý

Danh sách gợi ý được trình bày trong nội dung `reply`, thường gồm:

- Tên/nhóm sản phẩm phù hợp.
- Lý do phù hợp với nhu cầu người dùng.
- Tiêu chí nên ưu tiên: kích thước, chất liệu, ngân sách, phong cách.
- Câu hỏi tiếp theo để làm rõ nhu cầu tư vấn.

### 3.4. Kết quả so sánh/tham chiếu sản phẩm

Các kết quả tham chiếu gồm:

- Khoảng giá tham chiếu theo nhóm sản phẩm từ `price_reference.json`.
- Sản phẩm hoặc nội dung tương tự từ knowledge base.
- Kết quả benchmark retrieval theo mode `keyword`, `vector`, `hybrid`, `hybrid_rerank`.

### 3.5. Response API

Các response API chính:

- Conversation: `conversationId`, `id`, `title`, `createdAt`, `messageCount`, `lastPreview`.
- Message: `role`, `content`, `createdAt`.
- Knowledge base source URLs: `tenantId`, `urls`.
- Purchase request: `id`, `customer_name`, `phone`, `shipping_address`, `status`, `assigned_to_member_id`, `claimed_at`, `created_at`.
- Runtime/ops: runtime status, KB status, bot list, thống kê purchase request.

### 3.6. Kết quả kiểm thử

Kết quả kiểm thử được ghi nhận theo:

- Kết quả pass/fail của test case.
- Kết quả benchmark retrieval: Recall@k và MRR.
- Response API thực tế.
- Log hội thoại và log feedback.
- Trạng thái dữ liệu sau khi thực hiện test, ví dụ conversation, message, lead, purchase request.

## 4. Danh sách test cases

| Test ID | Nhóm chức năng | Mục tiêu kiểm thử | Dữ liệu đầu vào | Các bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Kết luận |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-01 | Khởi động hệ thống và health check | Kiểm tra backend, database và Python service hoạt động | Docker Compose, PostgreSQL, backend, Python runtime | Chạy `docker compose up --build`; gọi `GET /healthz`; mở `http://localhost:8080/login` | Backend phản hồi UI, Python `/healthz` trả `ready` hoặc `loading` có cấu trúc hợp lệ, database sẵn sàng nhận kết nối | API health trả đúng schema; UI login truy cập được; runtime có thông tin `ready`, `kb_loaded`, `cached_pipelines` | Đạt |
| TC-02 | Khởi động hệ thống và health check | Kiểm tra runtime LLM theo tenant | Tenant có `kbDir`, chatbot active | Đăng nhập admin; gọi `GET /api/runtime/llm` sau một lượt chat tenant | Runtime được quản lý theo tenant, có `baseUrl`, `pid`, `lastUsedAt` | Response runtime có map tenant id tới process phục vụ tenant | Đạt |
| TC-03 | Quản lý dữ liệu sản phẩm | Kiểm tra thêm URL nguồn sản phẩm | `{ "url": "https://example.com/products/sofa" }` | Đăng nhập tenant admin; gọi `POST /api/kb/source-urls`; gọi `GET /api/kb/source-urls` | URL được validate và xuất hiện trong danh sách `urls` | API trả `tenantId` và danh sách URL chứa URL vừa thêm | Đạt |
| TC-04 | Quản lý dữ liệu sản phẩm | Kiểm tra xóa URL nguồn sản phẩm | `{ "url": "https://example.com/products/sofa" }` | Gọi `DELETE /api/kb/source-urls`; gọi lại `GET /api/kb/source-urls` | URL bị loại khỏi `raw_urls.txt` | Response trả danh sách URL sau khi xóa | Đạt |
| TC-05 | Xử lý/import dữ liệu sản phẩm | Kiểm tra pipeline tạo knowledge base | `raw_urls.txt`, `docs.jsonl`, `chunks.jsonl`, `index.json` | Chạy `POST /api/kb/rebuild` hoặc chạy `tools/scrape_site.py` và `tools/build_kb.py` | Dữ liệu sản phẩm được crawl, chunk và tạo index; runtime tenant được evict để nạp KB mới | Response rebuild trả `success`, `lastRebuildStatus`, `lastRebuildStartedAt`, `lastRebuildFinishedAt` | Đạt |
| TC-06 | Xử lý/import dữ liệu sản phẩm | Kiểm tra dữ liệu KB đầu ra | Thư mục `chatbot/kb/noithatcaco` | Kiểm tra tồn tại `raw_urls.txt`, `docs.jsonl`, `chunks.jsonl`, `index.json`; nạp KB qua `KB_DIR` | Python service load KB và `kb_loaded` là `true` khi file hợp lệ | `/healthz` phản ánh `kb_dir` và trạng thái `kb_loaded` | Đạt |
| TC-07 | Truy xuất thông tin sản phẩm | Kiểm tra retrieval câu hỏi sofa căn hộ nhỏ | Câu hỏi: `tôi cần sofa gọn cho căn hộ nhỏ`; KB `noithatcaco` | Chạy `python chatbot/eval/runner.py --dataset chatbot/eval/dataset.jsonl --kb-dir chatbot/kb/noithatcaco --top-k 5 --compare` | Kết quả top-k chứa nội dung liên quan sofa/phòng nhỏ/căn hộ | Benchmark ghi nhận Recall@5 cho mode keyword là `0.7917` | Đạt |
| TC-08 | Truy xuất thông tin sản phẩm | Kiểm tra retrieval câu hỏi chính sách | Câu hỏi về thanh toán, giao hàng, đổi trả, bảo hành | Chạy benchmark retrieval và kiểm tra nhóm policy | Kết quả retrieval trỏ đến nội dung chính sách liên quan | Bộ đánh giá có các nhóm payment, delivery, return, warranty; kết quả được tổng hợp bằng Recall@5/MRR | Đạt |
| TC-09 | Hỏi đáp sản phẩm bằng chatbot | Kiểm tra tạo conversation tenant | `chatbotId`, `userExternalId` | Gọi `POST /api/chat/start` với tenant context hợp lệ | API trả `conversationId` | Conversation được tạo và response có field `conversationId` | Đạt |
| TC-10 | Hỏi đáp sản phẩm bằng chatbot | Kiểm tra gửi câu hỏi sản phẩm | `conversationId`, message: `Tôi muốn mua sofa cho phòng khách nhỏ` | Gọi `POST /api/chat/send`; kiểm tra response và message lưu trong DB | Response có `reply`, `latencyMs`, `model`, `adapter`, `llmBaseUrl`; conversation có user/assistant message | API trả đúng schema chat và lưu lịch sử hội thoại | Đạt |
| TC-11 | Gợi ý/tư vấn sản phẩm | Kiểm tra tư vấn theo nhu cầu/ngân sách | Message: `Tôi cần sofa phòng khách nhỏ, ngân sách khoảng 10 triệu` | Gửi nhiều lượt chat tenant | Chatbot hỏi/ghi nhận tiêu chí và gợi ý sản phẩm hoặc hướng lựa chọn phù hợp | Reply bám nhu cầu phòng nhỏ/ngân sách và đưa câu hỏi tiếp theo để tư vấn | Đạt |
| TC-12 | Gợi ý/tư vấn sản phẩm | Kiểm tra tư vấn chung | Message: `Tôi nên chọn sofa kích thước nào cho căn hộ nhỏ?` | Gọi `POST /api/general/chat/start`; gọi `POST /api/general/chat/send` | General chat trả lời tư vấn lựa chọn nội thất không phụ thuộc tenant cụ thể | API general chat trả `reply`, `latencyMs`, `model`, `llmBaseUrl` | Đạt |
| TC-13 | So sánh/tham chiếu sản phẩm | Kiểm tra tham chiếu giá | Câu hỏi: `Sofa khoảng 10 triệu có hợp lý không?` | Gửi câu hỏi tới Python `/chat` hoặc backend `/api/chat/send` | Chatbot sử dụng tham chiếu giá để nhận xét mức giá theo nhóm sản phẩm | Reply thể hiện đánh giá mức giá theo khoảng tham chiếu | Đạt |
| TC-14 | So sánh/tham chiếu sản phẩm | So sánh hiệu quả retrieval theo mode | `chatbot/eval/dataset.jsonl`, KB `noithatcaco`, top-k 5 | Chạy benchmark với `--compare` | Có bảng Recall@5 và MRR cho `keyword`, `vector`, `hybrid`, `hybrid_rerank` | Kết quả summary ghi 48 câu hỏi, 4 mode và chỉ số Recall@5/MRR | Đạt |
| TC-15 | Kiểm tra lỗi đầu vào | Kiểm tra thiếu `conversationId` khi gửi chat | `{ "message": "Tôi cần sofa" }` | Gọi `POST /api/chat/send` | API trả lỗi `BadRequest` với message `conversationId is required` | Format lỗi tuân theo `ApiExceptionHandler` | Đạt |
| TC-16 | Kiểm tra lỗi đầu vào | Kiểm tra URL nguồn không hợp lệ | `{ "url": "ftp://example.com/products" }` | Gọi `POST /api/kb/source-urls` | API từ chối URL không thuộc `http/https` | Response lỗi có `error: BadRequest`, `message: Source URL must use http or https` | Đạt |
| TC-17 | Kiểm tra lỗi đầu vào | Kiểm tra đăng nhập sai | `{ "name": "admin", "code": "wrong" }` | Gọi `POST /api/login/admin` | Response `ok=false`, message báo credential không hợp lệ | API trả `LoginResponse` đúng schema | Đạt |
| TC-18 | Kiểm tra giao diện demo | Kiểm tra trang login/admin/tenant/chat | Browser, backend port 8080 | Mở `/login`, `/admin`, `/tenant`, `/tenant/purchase-requests`, `/chat`, `/chat/general` | Giao diện tải đúng file static, gọi API tương ứng và hiển thị dữ liệu | Các route UI được phục vụ bởi Spring Boot static controller | Đạt |
| TC-19 | Tích hợp frontend - backend - AI/RAG service | Kiểm tra full flow chat tenant | Tenant demo, chatbot id, KB `noithatcaco`, câu hỏi sofa | Mở web chat; tạo conversation; gửi câu hỏi; backend gọi Python; Python truy xuất KB; response hiển thị trên UI | Luồng hoàn chỉnh từ UI tới backend, Python service, KB và quay lại UI | Response chat hiển thị trên giao diện và message được lưu trong database | Đạt |
| TC-20 | Tích hợp frontend - backend - AI/RAG service | Kiểm tra tạo purchase request từ hội thoại | Hội thoại có tên, số điện thoại, địa chỉ và xác nhận `CONFIRM` | Chat tới bước xác nhận; gửi `CONFIRM`; mở `/tenant/purchase-requests` | Hệ thống tạo purchase request tenant-scoped và hiển thị trong màn hình xử lý | API `/api/purchase-requests` trả request có `customer_name`, `phone`, `shipping_address`, `status` | Đạt |
| TC-21 | Quản lý hội thoại | Kiểm tra xem, đổi tên, xóa conversation | `conversationId`, title mới | Gọi list conversations, get messages, rename, delete | Conversation list/message đúng tenant; rename trả title mới; delete trả `deleted=true` | Các API conversation trả đúng schema và áp dụng tenant ownership | Đạt |
| TC-22 | Tích hợp kênh ngoài | Kiểm tra binding Messenger/Telegram | `chatbotId`, page id/token hoặc bot token | Gọi API tạo binding; gửi webhook payload mẫu | Binding lưu tenant/chatbot; webhook nhận event, lưu message và gọi chatbot | API binding trả entity active; webhook trả `ok` khi nhận payload hợp lệ | Đạt |

## 5. Kết quả thử nghiệm

### 5.1. Tổng hợp theo nhóm chức năng

| Nhóm chức năng | Số test cases | Số test đạt | Nhận xét |
| --- | ---: | ---: | --- |
| Khởi động hệ thống và health check | 2 | 2 | Health check và runtime status có schema rõ ràng, hỗ trợ kiểm tra backend/Python service. |
| Quản lý dữ liệu sản phẩm | 2 | 2 | API source URL quản lý dữ liệu đầu vào theo tenant và validate URL đúng quy tắc. |
| Xử lý/import dữ liệu sản phẩm | 2 | 2 | Pipeline tạo `docs.jsonl`, `chunks.jsonl`, `index.json` phục vụ retrieval. |
| Truy xuất thông tin sản phẩm | 2 | 2 | Retrieval benchmark bao phủ sản phẩm, phòng nhỏ, chất liệu/phong cách và chính sách. |
| Hỏi đáp sản phẩm bằng chatbot | 2 | 2 | API chat trả đúng schema và lưu hội thoại theo tenant. |
| Gợi ý/tư vấn sản phẩm | 2 | 2 | Chatbot xử lý tiêu chí nhu cầu và general chat cho tư vấn nội thất tổng quát. |
| So sánh/tham chiếu sản phẩm | 2 | 2 | Có tham chiếu giá và benchmark so sánh các mode retrieval. |
| Kiểm tra lỗi đầu vào | 3 | 3 | Các lỗi phổ biến trả response có cấu trúc phù hợp controller. |
| Kiểm tra giao diện demo | 1 | 1 | Các route UI chính được phục vụ qua backend và gọi API tương ứng. |
| Tích hợp frontend - backend - AI/RAG service | 4 | 4 | Luồng end-to-end bao phủ chat, KB, purchase request, conversation và kênh ngoài. |
| Tổng cộng | 22 | 22 | Bộ test cases bao phủ các luồng chính của sản phẩm. |

### 5.2. Kết quả benchmark retrieval

Nguồn kết quả: `chatbot/eval/results-summary.md`.

Thông tin bộ câu hỏi đánh giá:

- Số lượng câu hỏi: 48.
- Knowledge base: `chatbot/kb/noithatcaco`.
- Top-k: 5.
- Nhóm câu hỏi: gợi ý sản phẩm, căn hộ/phòng nhỏ, chất liệu/phong cách, thanh toán, giao hàng, đổi trả, bảo hành, thông tin chung.

Kết quả chỉ số:

| Mode | Recall@5 | MRR |
| --- | ---: | ---: |
| keyword | 0.7917 | 0.7333 |
| vector | 0.6667 | 0.4639 |
| hybrid | 0.7917 | 0.6708 |
| hybrid_rerank | 0.7708 | 0.6285 |

Nhận xét:

- Mode `keyword` đạt Recall@5 và MRR cao nhất trong bộ câu hỏi đánh giá hiện dùng.
- Mode `hybrid` có Recall@5 tương đương `keyword` và MRR thấp hơn.
- Mode `hybrid_rerank` có Recall@5 gần với `keyword`, phù hợp để so sánh trong các thử nghiệm retrieval.
- Mode `vector` có MRR thấp hơn trong bộ câu hỏi tiếng Việt, thể hiện retrieval theo từ khóa/heuristic phù hợp với dữ liệu sản phẩm/chính sách của hệ thống.

### 5.3. Kết quả API và hội thoại

Các nhóm response chính:

- Chat tenant trả `reply`, `latencyMs`, `model`, `adapter`, `llmBaseUrl`.
- Python service trả `reply`, `latency_ms`, `model`, `adapter`, `trigger_purchase_request`.
- Knowledge base source URL trả `tenantId`, `urls`.
- Purchase request trả `id`, `customer_name`, `phone`, `shipping_address`, `status`, `assigned_to_member_id`, `claimed_at`, `created_at`.
- Ops API trả runtime status, KB status, bot list và thống kê purchase request.

Các luồng dữ liệu chính:

- User message được lưu trong bảng `messages` với role `user`.
- Assistant response được lưu trong bảng `messages` với role `assistant`.
- Conversation có title sinh từ tin nhắn đầu tiên hoặc được cập nhật qua API rename.
- Purchase request được tạo từ hội thoại có đủ thông tin khách hàng và xác nhận nhu cầu.

## 6. Nhận xét đánh giá

### 6.1. Tính đúng của dữ liệu trả về

Các API chính dùng schema nhất quán với controller/DTO:

- Backend sử dụng `camelCase` cho phần lớn response như `conversationId`, `latencyMs`, `messageCount`, `lastPreview`.
- Python service sử dụng `snake_case` theo Pydantic như `latency_ms`, `trigger_purchase_request`, `captured_phone`.
- Purchase request response dùng `snake_case` cho các field được annotate bằng `@JsonProperty`, ví dụ `customer_name`, `shipping_address`, `assigned_to_member_id`.

Dữ liệu trả về thể hiện đúng tenant context, conversation ownership và trạng thái xử lý của purchase request.

### 6.2. Mức độ phù hợp của câu trả lời

Chatbot sử dụng context truy xuất từ knowledge base, lịch sử hội thoại và cấu hình chatbot để tạo câu trả lời. Với các câu hỏi về sản phẩm, phòng nhỏ, chất liệu, phong cách và chính sách, hệ thống ưu tiên thông tin nằm trong KB của tenant. Các câu hỏi tư vấn chung được xử lý qua mode `general_consumer`.

### 6.3. Khả năng truy xuất đúng thông tin sản phẩm

Kết quả benchmark trên 48 câu hỏi cho thấy mode `keyword` và `hybrid` đạt Recall@5 `0.7917`. Điều này thể hiện hệ thống có khả năng đưa đoạn tri thức liên quan vào top 5 kết quả trong phần lớn câu hỏi đánh giá. Các nhóm câu hỏi chính sách và thông tin sản phẩm đều được đưa vào coverage.

### 6.4. Khả năng gợi ý sản phẩm

Luồng tư vấn sử dụng các tiêu chí như loại sản phẩm, không gian, ngân sách, phong cách, màu sắc và chất liệu. Chatbot có thể đặt câu hỏi bổ sung, gợi ý hướng lựa chọn và chuyển sang luồng tạo yêu cầu mua hàng khi người dùng xác nhận nhu cầu.

### 6.5. Tính ổn định khi gọi API

Backend có cơ chế:

- Quản lý Python runtime theo tenant.
- Kiểm tra health bằng `/healthz`.
- Timeout và fallback khi upstream chatbot gặp lỗi.
- Lưu conversation/message trước và sau khi gọi AI/RAG service.
- Evict runtime khi rebuild KB để lần chat kế tiếp dùng knowledge base mới.

### 6.6. Khả năng xử lý lỗi đầu vào

Các lỗi đầu vào phổ biến được xử lý bằng exception handler hoặc validation trong service:

- Thiếu `conversationId` hoặc `message` khi gửi chat.
- URL nguồn không hợp lệ hoặc không dùng `http/https`.
- Tenant không tồn tại hoặc thiếu tenant context.
- Chatbot không thuộc tenant.
- Sai thông tin đăng nhập.
- Role không đủ quyền khi gọi API quản trị.

Format lỗi nghiệp vụ chính:

```json
{
  "error": "BadRequest",
  "message": "message"
}
```

Format lỗi xác thực/phân quyền theo Spring Security/Spring Boot sử dụng HTTP status tương ứng như `401` hoặc `403`.
