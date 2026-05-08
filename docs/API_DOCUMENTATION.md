# API Documentation

Tài liệu này được tổng hợp từ route/controller/schema trong mã nguồn:

- Backend Spring Boot: `multitenant/src/main/java/com/app/**`
- Python FastAPI chatbot service: `chatbot/app/server.py`
- DTO Java: `multitenant/src/main/java/com/app/**/dto`, request/response record và entity trả trực tiếp từ controller

Backend không cấu hình SpringDoc/OpenAPI trong `pom.xml`; vì vậy endpoint, request và response được đối chiếu trực tiếp từ controller, DTO và model. Python service dùng FastAPI/Pydantic nên các schema `/chat`, `/feedback`, `/healthz`, `/state` khớp với class trong `chatbot/app/server.py`.

## Quy ước chung

- Base URL backend: `http://localhost:8080`
- Base URL Python chatbot service khi chạy độc lập: `http://localhost:8000`
- Content-Type cho request JSON: `application/json`
- Backend dùng session sau khi đăng nhập qua `/api/login/admin` hoặc `/api/login/tenant`.
- Các API tenant-scoped có thể nhận tenant context qua `X-Tenant-Id` hoặc `X-API-Key` theo `TenantResolver`; các API quản trị vẫn yêu cầu principal phù hợp trong session.
- Response lỗi nghiệp vụ từ `ApiExceptionHandler` thường có dạng:

```json
{
  "error": "BadRequest",
  "message": "message"
}
```

- Response lỗi validation từ Spring có dạng:

```json
{
  "error": "ValidationError",
  "message": "field message"
}
```

- Một số lỗi bảo mật hoặc lỗi `ResponseStatusException` do Spring Security/Spring Boot xử lý theo status HTTP tương ứng.

## [GET] /healthz

- Nhóm API: System / Health check
- Mục đích: Kiểm tra trạng thái Python chatbot service.
- Mô tả: Trả trạng thái nạp model, số pipeline cache và thông tin knowledge base.
- Authentication: Không yêu cầu.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Không bắt buộc.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "status": "ready",
  "ready": true,
  "error": null,
  "cached_pipelines": 1,
  "kb_dir": "F:/20251/prj3/chatbot/kb/noithatcaco",
  "kb_loaded": true
}
```

* Response lỗi:

```json
{
  "status": "loading",
  "ready": false,
  "error": "error message",
  "cached_pipelines": 0,
  "kb_dir": null,
  "kb_loaded": false
}
```

* Status codes: `200`
* Ghi chú: Endpoint thuộc Python FastAPI service.

## [POST] /api/login/admin

- Nhóm API: Authentication / User
- Mục đích: Đăng nhập platform admin.
- Mô tả: Tạo session admin khi thông tin đăng nhập hợp lệ.
- Authentication: Không yêu cầu.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`
- Request body:

```json
{
  "name": "admin",
  "code": "admin-password"
}
```

* Response thành công:

```json
{
  "ok": true,
  "message": "OK",
  "userId": "platform-admin",
  "role": "PLATFORM_ADMIN",
  "tenantId": null,
  "displayName": "Platform Admin",
  "email": "admin"
}
```

* Response lỗi:

```json
{
  "ok": false,
  "message": "Invalid admin credentials",
  "userId": null,
  "role": null,
  "tenantId": null,
  "displayName": null,
  "email": null
}
```

* Status codes: `200`
* Ghi chú: Không đưa mật khẩu thật vào tài liệu/API client dùng chung.

## [POST] /api/login/tenant

- Nhóm API: Authentication / User
- Mục đích: Đăng nhập thành viên tenant.
- Mô tả: Xác thực email và password của tenant member, sau đó tạo session.
- Authentication: Không yêu cầu.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`
- Request body:

```json
{
  "name": "staff@example.com",
  "code": "member-password"
}
```

* Response thành công:

```json
{
  "ok": true,
  "message": "OK",
  "userId": "member-uuid",
  "role": "TENANT_ADMIN",
  "tenantId": "tenant-uuid",
  "displayName": "Tenant Admin",
  "email": "staff@example.com"
}
```

* Response lỗi:

```json
{
  "ok": false,
  "message": "Invalid tenant member credentials",
  "userId": null,
  "role": null,
  "tenantId": null,
  "displayName": null,
  "email": null
}
```

* Status codes: `200`
* Ghi chú: Field request giữ theo `LoginRequest(name, code)`.

## [POST] /api/login/logout

- Nhóm API: Authentication / User
- Mục đích: Đăng xuất session hiện hành.
- Mô tả: Invalidate HTTP session nếu tồn tại.
- Authentication: Session.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{}
```

* Response lỗi:

```json
{
  "status": 401,
  "error": "Unauthorized"
}
```

* Status codes: `200`, `401`
* Ghi chú: Controller trả `void`.

## [GET] /api/me

- Nhóm API: Authentication / User
- Mục đích: Lấy principal hiện hành.
- Mô tả: Trả thông tin người dùng từ session.
- Authentication: Session.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "userId": "member-uuid",
  "role": "TENANT_ADMIN",
  "tenantId": "tenant-uuid",
  "displayName": "Tenant Admin",
  "email": "staff@example.com"
}
```

* Response lỗi:

```json
{
  "status": 401,
  "error": "Unauthorized"
}
```

* Status codes: `200`, `401`
* Ghi chú: Response là `AppPrincipal`.

## [GET] /api/admin/tenants

- Nhóm API: Authentication / User
- Mục đích: Liệt kê tenant.
- Mô tả: Trả danh sách cửa hàng/tenant trên nền tảng.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": "tenant-uuid",
    "code": "demo_caco",
    "name": "Demo CaCo",
    "apiKey": "tenant-api-key",
    "kbDir": "F:/20251/prj3/chatbot/kb/noithatcaco",
    "status": "ACTIVE"
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Controller yêu cầu `requirePlatformAdmin()`.

## [POST] /api/admin/tenants

- Nhóm API: Authentication / User
- Mục đích: Tạo tenant.
- Mô tả: Tạo tenant với code, name, apiKey, kbDir và status.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "code": "demo_store",
  "name": "Demo Store",
  "apiKey": "optional-api-key",
  "kbDir": "F:/20251/prj3/chatbot/kb/demo_store",
  "status": "ACTIVE"
}
```

* Response thành công:

```json
{
  "id": "tenant-uuid",
  "code": "demo_store",
  "name": "Demo Store",
  "apiKey": "generated-or-provided-api-key",
  "kbDir": "F:/20251/prj3/chatbot/kb/demo_store",
  "status": "ACTIVE"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Tenant code already exists"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Nếu `apiKey` rỗng, service tự tạo UUID dạng bỏ dấu `-`.

## [GET] /api/admin/tenants/{tenantId}

- Nhóm API: Authentication / User
- Mục đích: Lấy chi tiết tenant.
- Mô tả: Trả thông tin tenant theo UUID.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: `tenantId` UUID.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "id": "tenant-uuid",
  "code": "demo_store",
  "name": "Demo Store",
  "apiKey": "tenant-api-key",
  "kbDir": "F:/20251/prj3/chatbot/kb/demo_store",
  "status": "ACTIVE"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Tenant not found"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Endpoint thuộc `TenantAdminController`.

## [GET] /api/admin/tenant-members

- Nhóm API: Authentication / User
- Mục đích: Liệt kê thành viên tenant bởi platform admin.
- Mô tả: Trả danh sách thành viên của tenant theo query `tenantId`.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: `tenantId` UUID.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": "member-uuid",
    "tenantId": "tenant-uuid",
    "email": "staff@example.com",
    "displayName": "Staff",
    "role": "TENANT_MEMBER",
    "status": "ACTIVE"
  }
]
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Tenant not found"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Query `tenantId` là bắt buộc.

## [POST] /api/admin/tenant-members

- Nhóm API: Authentication / User
- Mục đích: Tạo thành viên tenant bởi platform admin.
- Mô tả: Tạo tài khoản tenant admin hoặc tenant member.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: `tenantId` UUID.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "email": "staff@example.com",
  "displayName": "Staff",
  "role": "TENANT_MEMBER",
  "status": "ACTIVE",
  "password": "member-password"
}
```

* Response thành công:

```json
{
  "id": "member-uuid",
  "tenantId": "tenant-uuid",
  "email": "staff@example.com",
  "displayName": "Staff",
  "role": "TENANT_MEMBER",
  "status": "ACTIVE"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "password must be at least 6 characters"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: `role` nhận `TENANT_ADMIN` hoặc `TENANT_MEMBER`.

## [GET] /api/tenant-members

- Nhóm API: Authentication / User
- Mục đích: Tenant admin liệt kê thành viên trong tenant của mình.
- Mô tả: Trả danh sách member theo tenant trong session.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": "member-uuid",
    "tenantId": "tenant-uuid",
    "email": "staff@example.com",
    "displayName": "Staff",
    "role": "TENANT_MEMBER",
    "status": "ACTIVE"
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Endpoint dùng `principalAccessor.requireTenantAdmin()`.

## [POST] /api/tenant-members

- Nhóm API: Authentication / User
- Mục đích: Tenant admin tạo thành viên trong tenant của mình.
- Mô tả: Tạo member và hash password bằng `PasswordEncoder`.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "email": "staff@example.com",
  "displayName": "Staff",
  "role": "TENANT_MEMBER",
  "status": "ACTIVE",
  "password": "member-password"
}
```

* Response thành công:

```json
{
  "id": "member-uuid",
  "tenantId": "tenant-uuid",
  "email": "staff@example.com",
  "displayName": "Staff",
  "role": "TENANT_MEMBER",
  "status": "ACTIVE"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Tenant member email already exists"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Tenant lấy từ session, không lấy từ body.

## [GET] /api/chatbots

- Nhóm API: Product management
- Mục đích: Liệt kê chatbot của tenant.
- Mô tả: Trả danh sách `ChatbotInstance` thuộc tenant trong context.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session; tenant context từ session hoặc header.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": "chatbot-uuid",
    "tenantId": "tenant-uuid",
    "name": "Sales Bot",
    "channel": "web",
    "persona": {
      "tone": "friendly"
    },
    "status": "ACTIVE",
    "baseModel": "Qwen/Qwen2.5-1.5B-Instruct",
    "adapterPath": null,
    "tokenizerPath": null,
    "systemPrompt": null,
    "maxNewTokens": null,
    "temperature": null,
    "topP": null,
    "topK": null,
    "responseStyle": "natural",
    "mode": "tenant_sales",
    "provider": "local",
    "apiModel": null,
    "apiBaseUrl": null
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: `apiKey` trong entity có `WRITE_ONLY`, không xuất hiện trong response.

## [POST] /api/chatbots

- Nhóm API: Product management
- Mục đích: Tạo chatbot cho tenant.
- Mô tả: Tạo `ChatbotInstance` với persona, style, mode và provider.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

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

* Response thành công:

```json
{
  "id": "chatbot-uuid",
  "tenantId": "tenant-uuid",
  "name": "Sales Bot",
  "channel": "web",
  "persona": {
    "tone": "friendly"
  },
  "status": "ACTIVE",
  "responseStyle": "natural",
  "mode": "tenant_sales",
  "provider": "local",
  "apiModel": null,
  "apiBaseUrl": null
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Unsupported responseStyle: custom"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: `responseStyle` nhận `natural`, `balanced`, `fast`.

## [PUT] /api/chatbots/{id}

- Nhóm API: Product management
- Mục đích: Cập nhật chatbot.
- Mô tả: Cập nhật các trường trong `SaveBotDto` cho chatbot thuộc tenant.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: `id` UUID.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "name": "Sales Bot",
  "channel": "web",
  "personaJson": "{\"tone\":\"balanced\"}",
  "responseStyle": "balanced",
  "mode": "tenant_sales",
  "provider": "claude",
  "apiModel": "provider-model-name",
  "apiKey": "provider-api-key",
  "apiBaseUrl": "https://provider.example"
}
```

* Response thành công:

```json
{
  "id": "chatbot-uuid",
  "tenantId": "tenant-uuid",
  "name": "Sales Bot",
  "channel": "web",
  "persona": {
    "tone": "balanced"
  },
  "status": "ACTIVE",
  "responseStyle": "balanced",
  "mode": "tenant_sales",
  "provider": "claude",
  "apiModel": "provider-model-name",
  "apiBaseUrl": "https://provider.example"
}
```

* Response lỗi:

```json
{
  "status": 404,
  "error": "Not Found"
}
```

* Status codes: `200`, `400`, `401`, `403`, `404`
* Ghi chú: Nếu `apiKey` rỗng, code giữ nguyên key cũ.

## [GET] /api/kb/source-urls

- Nhóm API: Data import / processing
- Mục đích: Liệt kê URL nguồn dữ liệu sản phẩm của tenant.
- Mô tả: Đọc file `raw_urls.txt` trong `kb_dir` của tenant.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "tenantId": "tenant-uuid",
  "urls": [
    "https://example.com/products/sofa"
  ]
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Tenant kb_dir is not configured"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Endpoint thuộc `TenantKbSourceController`.

## [POST] /api/kb/source-urls

- Nhóm API: Data import / processing
- Mục đích: Thêm URL nguồn.
- Mô tả: Validate URL `http/https` và ghi vào `raw_urls.txt`.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "url": "https://example.com/products/sofa"
}
```

* Response thành công:

```json
{
  "tenantId": "tenant-uuid",
  "urls": [
    "https://example.com/products/sofa"
  ]
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Source URL must use http or https"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Trùng URL được loại bằng `LinkedHashSet`.

## [DELETE] /api/kb/source-urls

- Nhóm API: Data import / processing
- Mục đích: Xóa URL nguồn.
- Mô tả: Xóa URL khỏi `raw_urls.txt` của tenant.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "url": "https://example.com/products/sofa"
}
```

* Response thành công:

```json
{
  "tenantId": "tenant-uuid",
  "urls": []
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Invalid source URL"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Body dùng cùng schema `SourceUrlRequest`.

## [POST] /api/kb/rebuild

- Nhóm API: Knowledge base / Retrieval
- Mục đích: Xử lý lại dữ liệu sản phẩm thành knowledge base.
- Mô tả: Chạy `tools/scrape_site.py` và `tools/build_kb.py`, sau đó evict runtime tenant.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "success": true,
  "message": "KB rebuilt successfully. The next tenant chat request will start with the updated KB.",
  "rebuiltAt": "2026-05-05T08:00:00Z",
  "lastRebuildStartedAt": "2026-05-05T07:59:30Z",
  "lastRebuildFinishedAt": "2026-05-05T08:00:00Z",
  "lastRebuildStatus": "SUCCESS",
  "lastRebuildMessage": "KB rebuilt successfully. The next tenant chat request will start with the updated KB."
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Tenant kb_dir is not configured"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Endpoint là API xử lý dữ liệu sản phẩm phục vụ RAG.

## [POST] /api/chat/start

- Nhóm API: Chatbot / Conversation
- Mục đích: Tạo conversation chat theo tenant.
- Mô tả: Tạo conversation mới cho chatbot thuộc tenant.
- Authentication: Session; tenant context qua session hoặc `X-Tenant-Id`/`X-API-Key`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session hoặc tenant header.
- Request body:

```json
{
  "chatbotId": "chatbot-uuid",
  "userExternalId": "optional-user-id"
}
```

* Response thành công:

```json
{
  "conversationId": "conversation-uuid"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "chatbotId is required"
}
```

* Status codes: `200`, `400`, `401`
* Ghi chú: `chatbotId` phải thuộc tenant hiện hành.

## [POST] /api/chat/send

- Nhóm API: Chatbot / Conversation
- Mục đích: Gửi tin nhắn chat theo tenant.
- Mô tả: Lưu user message, gọi Python chatbot service, lưu assistant message và trả reply.
- Authentication: Session; tenant context qua session hoặc `X-Tenant-Id`/`X-API-Key`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session hoặc tenant header.
- Request body:

```json
{
  "conversationId": "conversation-uuid",
  "message": "Tôi muốn mua sofa cho phòng khách nhỏ"
}
```

* Response thành công:

```json
{
  "reply": "Nội dung tư vấn",
  "latencyMs": 842,
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "adapter": "",
  "llmBaseUrl": "http://127.0.0.1:8101"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "conversationId is required"
}
```

* Status codes: `200`, `400`, `401`, `404`
* Ghi chú: Khi Python trả trigger tạo purchase request, backend tạo lead/purchase request và trả thông báo trong `reply`.

## [GET] /api/chat/conversations

- Nhóm API: Chatbot / Conversation
- Mục đích: Liệt kê conversation theo chatbot.
- Mô tả: Trả danh sách conversation mới nhất của chatbot trong tenant.
- Authentication: Session; tenant context qua session hoặc tenant header.
- Request params / path params: Không có.
- Query params: `chatbotId` UUID, `limit` integer, `userExternalId` string.
- Request headers: Cookie session hoặc tenant header.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": "conversation-uuid",
    "title": "Tôi muốn mua sofa",
    "createdAt": "2026-05-05T08:00:00Z",
    "messageCount": 4,
    "lastPreview": "Nội dung tin nhắn gần nhất"
  }
]
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Missing tenant context"
}
```

* Status codes: `200`, `400`, `401`
* Ghi chú: `limit` mặc định `50`.

## [GET] /api/chat/conversation/{conversationId}/messages

- Nhóm API: Chatbot / Conversation
- Mục đích: Lấy message trong conversation.
- Mô tả: Trả tối đa 200 messages theo thứ tự thời gian tăng dần.
- Authentication: Session; tenant context qua session hoặc tenant header.
- Request params / path params: `conversationId` UUID.
- Query params: Không có.
- Request headers: Cookie session hoặc tenant header.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "role": "user",
    "content": "Tôi muốn mua sofa",
    "createdAt": "2026-05-05T08:00:00Z"
  },
  {
    "role": "assistant",
    "content": "Bạn muốn sofa cho không gian nào?",
    "createdAt": "2026-05-05T08:00:01Z"
  }
]
```

* Response lỗi:

```json
{
  "status": 404,
  "error": "Not Found"
}
```

* Status codes: `200`, `401`, `404`
* Ghi chú: Conversation phải thuộc tenant hiện hành.

## [PUT] /api/chat/conversation/{conversationId}/rename

- Nhóm API: Chatbot / Conversation
- Mục đích: Đổi tên conversation.
- Mô tả: Cập nhật `title`, cắt tối đa 200 ký tự.
- Authentication: Session; tenant context qua session hoặc tenant header.
- Request params / path params: `conversationId` UUID.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session hoặc tenant header.
- Request body:

```json
{
  "title": "Tư vấn sofa phòng khách"
}
```

* Response thành công:

```json
{
  "id": "conversation-uuid",
  "title": "Tư vấn sofa phòng khách"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "title is required"
}
```

* Status codes: `200`, `400`, `401`, `404`
* Ghi chú: Endpoint dùng `Map<String, String>` làm request body.

## [DELETE] /api/chat/conversation/{conversationId}

- Nhóm API: Chatbot / Conversation
- Mục đích: Xóa conversation.
- Mô tả: Xóa messages trước, sau đó xóa conversation.
- Authentication: Session; tenant context qua session hoặc tenant header.
- Request params / path params: `conversationId` UUID.
- Query params: Không có.
- Request headers: Cookie session hoặc tenant header.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "deleted": true,
  "id": "conversation-uuid"
}
```

* Response lỗi:

```json
{
  "status": 404,
  "error": "Not Found"
}
```

* Status codes: `200`, `401`, `404`
* Ghi chú: Endpoint thuộc `ChatController`.

## [POST] /api/general/chat/start

- Nhóm API: Product recommendation / advising
- Mục đích: Tạo conversation tư vấn chung.
- Mô tả: Tạo conversation cho system tenant và chatbot mode `general_consumer`.
- Authentication: Không yêu cầu.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Không bắt buộc.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "conversationId": "conversation-uuid"
}
```

* Response lỗi:

```json
{
  "status": 404,
  "error": "Not Found"
}
```

* Status codes: `200`, `404`
* Ghi chú: Endpoint được permit trong Spring Security.

## [POST] /api/general/chat/send

- Nhóm API: Product recommendation / advising
- Mục đích: Gửi tin nhắn tư vấn chung.
- Mô tả: Gọi Python service với mode `general_consumer`, lưu message và trả reply.
- Authentication: Không yêu cầu.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`
- Request body:

```json
{
  "conversationId": "conversation-uuid",
  "message": "Tôi nên chọn sofa kích thước nào cho căn hộ nhỏ?"
}
```

* Response thành công:

```json
{
  "reply": "Nội dung tư vấn",
  "latencyMs": 842,
  "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "adapter": "",
  "llmBaseUrl": "http://127.0.0.1:8101"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "message is required"
}
```

* Status codes: `200`, `400`, `404`
* Ghi chú: Endpoint cũng có thể tạo purchase request nếu Python response có trigger và phone.

## [GET] /api/general/chat/conversations

- Nhóm API: Product recommendation / advising
- Mục đích: Liệt kê conversation tư vấn chung.
- Mô tả: Trả danh sách conversation của chatbot `general_consumer`.
- Authentication: Không yêu cầu.
- Request params / path params: Không có.
- Query params: `limit` integer, mặc định `50`.
- Request headers: Không bắt buộc.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": "conversation-uuid",
    "title": "Chọn sofa cho căn hộ nhỏ",
    "createdAt": "2026-05-05T08:00:00Z",
    "messageCount": 2,
    "lastPreview": "Nội dung gần nhất"
  }
]
```

* Response lỗi:

```json
{
  "status": 404,
  "error": "Not Found"
}
```

* Status codes: `200`, `404`
* Ghi chú: Dùng system tenant cố định.

## [GET] /api/general/chat/conversation/{conversationId}/messages

- Nhóm API: Product recommendation / advising
- Mục đích: Lấy message của conversation tư vấn chung.
- Mô tả: Trả tối đa 200 messages theo thứ tự thời gian tăng dần.
- Authentication: Không yêu cầu.
- Request params / path params: `conversationId` UUID.
- Query params: Không có.
- Request headers: Không bắt buộc.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "role": "user",
    "content": "Tôi nên chọn sofa kích thước nào?",
    "createdAt": "2026-05-05T08:00:00Z"
  }
]
```

* Response lỗi:

```json
{
  "status": 404,
  "error": "Not Found"
}
```

* Status codes: `200`, `404`
* Ghi chú: Conversation phải thuộc system tenant và chatbot general.

## [PUT] /api/general/chat/conversation/{conversationId}/rename

- Nhóm API: Product recommendation / advising
- Mục đích: Đổi tên conversation tư vấn chung.
- Mô tả: Cập nhật `title`.
- Authentication: Không yêu cầu.
- Request params / path params: `conversationId` UUID.
- Query params: Không có.
- Request headers: `Content-Type: application/json`
- Request body:

```json
{
  "title": "Tư vấn sofa căn hộ"
}
```

* Response thành công:

```json
{
  "id": "conversation-uuid",
  "title": "Tư vấn sofa căn hộ"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "title is required"
}
```

* Status codes: `200`, `400`, `404`
* Ghi chú: Title cắt tối đa 200 ký tự.

## [DELETE] /api/general/chat/conversation/{conversationId}

- Nhóm API: Product recommendation / advising
- Mục đích: Xóa conversation tư vấn chung.
- Mô tả: Xóa messages và conversation thuộc system tenant.
- Authentication: Không yêu cầu.
- Request params / path params: `conversationId` UUID.
- Query params: Không có.
- Request headers: Không bắt buộc.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "deleted": true,
  "id": "conversation-uuid"
}
```

* Response lỗi:

```json
{
  "status": 404,
  "error": "Not Found"
}
```

* Status codes: `200`, `404`
* Ghi chú: Endpoint thuộc `GeneralChatController`.

## [POST] /chat

- Nhóm API: Chatbot / Conversation
- Mục đích: Sinh câu trả lời từ Python chatbot service.
- Mô tả: Nhận message, history, cấu hình sinh câu trả lời và metadata; trả reply cho backend hoặc client kiểm thử.
- Authentication: Không yêu cầu ở Python service.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`
- Request body:

```json
{
  "message": "Tôi muốn tìm bàn ăn gỗ",
  "history": [
    "Tôi cần nội thất cho phòng ăn"
  ],
  "gen": {
    "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
    "adapter": null,
    "tokenizer_path": null,
    "system_prompt": "You are a helpful furniture sales assistant.",
    "max_new_tokens": 256,
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 50,
    "stop": [
      "</s>"
    ],
    "provider": "local",
    "api_model": null,
    "api_key": null,
    "api_base_url": null,
    "mode": "tenant_sales"
  },
  "conversation_id": "conversation-id",
  "channel": "web",
  "tenant_id": "tenant-id"
}
```

* Response thành công:

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

* Response lỗi:

```json
{
  "detail": "Model is still loading"
}
```

* Status codes: `200`, `422`, `503`
* Ghi chú: Field Python dùng `snake_case` theo Pydantic model.

## [POST] /feedback

- Nhóm API: Demo / Test API
- Mục đích: Ghi feedback cho câu trả lời.
- Mô tả: Ghi feedback vào log Python.
- Authentication: Không yêu cầu ở Python service.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`
- Request body:

```json
{
  "conversation_id": "conversation-id",
  "tenant_id": "tenant-id",
  "channel": "web",
  "question": "Câu hỏi",
  "answer": "Câu trả lời",
  "is_correct": true,
  "note": ""
}
```

* Response thành công:

```json
{
  "ok": true
}
```

* Response lỗi:

```json
{
  "detail": [
    {
      "loc": [
        "body",
        "question"
      ],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

* Status codes: `200`, `422`
* Ghi chú: Endpoint thuộc Python service.

## [GET] /state

- Nhóm API: Demo / Test API
- Mục đích: Đọc state hội thoại của Python service.
- Mô tả: Trả stage, slots và turn gần nhất theo `conversation_id`.
- Authentication: Không yêu cầu ở Python service.
- Request params / path params: Không có.
- Query params: `conversation_id` string.
- Request headers: Không bắt buộc.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "stage": "discover",
  "slots": {},
  "updated_at": 1711477000.0,
  "last_question": "Tôi cần sofa",
  "last_answer": "Bạn muốn sofa cho phòng nào?"
}
```

* Response lỗi:

```json
{
  "detail": [
    {
      "loc": [
        "query",
        "conversation_id"
      ],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

* Status codes: `200`, `422`
* Ghi chú: Backend dùng endpoint này khi tạo lead snapshot.

## [GET] /api/purchase-requests

- Nhóm API: Chatbot / Conversation
- Mục đích: Liệt kê yêu cầu mua hàng.
- Mô tả: Trả purchase requests của tenant, có thể lọc theo status.
- Authentication: Session `TENANT_ADMIN` hoặc `TENANT_MEMBER`.
- Request params / path params: Không có.
- Query params: `tenantId` optional, `status` optional.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": 1,
    "customer_name": "Nguyen Van A",
    "phone": "0912345678",
    "shipping_address": "123 Nguyen Trai, Ha Noi",
    "status": "NEW",
    "assigned_to_member_id": null,
    "assigned_to_display_name": null,
    "claimed_at": null,
    "created_at": "2026-05-05T08:00:00Z"
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Response dùng `snake_case` theo `@JsonProperty`.

## [PUT] /api/purchase-requests/{id}/status

- Nhóm API: Chatbot / Conversation
- Mục đích: Cập nhật trạng thái purchase request.
- Mô tả: Cập nhật `status` của yêu cầu mua hàng trong tenant hiện hành.
- Authentication: Session `TENANT_ADMIN` hoặc `TENANT_MEMBER`.
- Request params / path params: `id` long.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "status": "CONTACTED"
}
```

* Response thành công:

```json
{
  "id": 1,
  "customer_name": "Nguyen Van A",
  "phone": "0912345678",
  "shipping_address": "123 Nguyen Trai, Ha Noi",
  "status": "CONTACTED",
  "assigned_to_member_id": null,
  "assigned_to_display_name": null,
  "claimed_at": null,
  "created_at": "2026-05-05T08:00:00Z"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Invalid purchase request status"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Body schema là `PurchaseRequestStatusUpdateRequest`.

## [PUT] /api/purchase-requests/{id}/claim

- Nhóm API: Chatbot / Conversation
- Mục đích: Nhận xử lý purchase request.
- Mô tả: Gán request cho member trong session hiện hành.
- Authentication: Session `TENANT_ADMIN` hoặc `TENANT_MEMBER`.
- Request params / path params: `id` long.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "id": 1,
  "customer_name": "Nguyen Van A",
  "phone": "0912345678",
  "shipping_address": "123 Nguyen Trai, Ha Noi",
  "status": "NEW",
  "assigned_to_member_id": "member-uuid",
  "assigned_to_display_name": "Staff",
  "claimed_at": "2026-05-05T08:10:00Z",
  "created_at": "2026-05-05T08:00:00Z"
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Member id lấy từ principal session.

## [PUT] /api/purchase-requests/{id}/assign

- Nhóm API: Chatbot / Conversation
- Mục đích: Phân công purchase request.
- Mô tả: Tenant admin gán request cho một tenant member.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: `id` long.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "member_id": "member-uuid"
}
```

* Response thành công:

```json
{
  "id": 1,
  "customer_name": "Nguyen Van A",
  "phone": "0912345678",
  "shipping_address": "123 Nguyen Trai, Ha Noi",
  "status": "NEW",
  "assigned_to_member_id": "member-uuid",
  "assigned_to_display_name": "Staff",
  "claimed_at": "2026-05-05T08:10:00Z",
  "created_at": "2026-05-05T08:00:00Z"
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Request body dùng field `member_id`.

## [GET] /api/messenger/bindings

- Nhóm API: Chatbot / Conversation
- Mục đích: Liệt kê binding Messenger.
- Mô tả: Trả các page binding của tenant.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": "binding-uuid",
    "tenantId": "tenant-uuid",
    "pageId": "page-id",
    "chatbotId": "chatbot-uuid",
    "pageAccessToken": "token-value",
    "status": "ACTIVE"
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Không đưa token thật vào tài liệu public.

## [POST] /api/messenger/bindings

- Nhóm API: Chatbot / Conversation
- Mục đích: Tạo binding Messenger page với chatbot.
- Mô tả: Liên kết `pageId` với chatbot thuộc tenant.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "pageId": "page-id",
  "chatbotId": "chatbot-uuid",
  "pageAccessToken": "page-access-token"
}
```

* Response thành công:

```json
{
  "id": "binding-uuid",
  "tenantId": "tenant-uuid",
  "pageId": "page-id",
  "chatbotId": "chatbot-uuid",
  "pageAccessToken": "page-access-token",
  "status": "ACTIVE"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "This pageId is already bound"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Body schema là `CreateMessengerBindingDto`.

## [DELETE] /api/messenger/bindings/{id}

- Nhóm API: Chatbot / Conversation
- Mục đích: Ngưng kích hoạt Messenger binding.
- Mô tả: Set `status` thành `INACTIVE`.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: `id` UUID.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "Binding not found"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Controller trả `void`.

## [GET] /webhook/messenger

- Nhóm API: Chatbot / Conversation
- Mục đích: Verify webhook Messenger.
- Mô tả: Kiểm tra `hub.mode`, `hub.verify_token`, trả `hub.challenge`.
- Authentication: Verify token qua query param.
- Request params / path params: Không có.
- Query params: `hub.mode`, `hub.verify_token`, `hub.challenge`.
- Request headers: Không bắt buộc.
- Request body:

```json
{}
```

* Response thành công:

```json
"challenge-value"
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `403`
* Ghi chú: Token lấy từ cấu hình `messenger.verify-token`.

## [POST] /webhook/messenger

- Nhóm API: Chatbot / Conversation
- Mục đích: Nhận event Messenger.
- Mô tả: Nhận payload webhook, xử lý bất đồng bộ và trả `ok`.
- Authentication: Theo page binding và cấu hình webhook.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`
- Request body:

```json
{
  "entry": [
    {
      "id": "page-id",
      "messaging": [
        {
          "sender": {
            "id": "psid"
          },
          "message": {
            "mid": "message-id",
            "text": "I need a sofa"
          }
        }
      ]
    }
  ]
}
```

* Response thành công:

```json
"ok"
```

* Response lỗi:

```json
{
  "status": 400,
  "error": "Bad Request"
}
```

* Status codes: `200`, `400`
* Ghi chú: Controller trả `ok` ngay sau khi đưa event vào worker pool. Text `RATE GOOD`, `RATE BAD`, `CONFIRM`, `CANCEL` có xử lý riêng trong webhook.

## [GET] /api/telegram/bindings

- Nhóm API: Chatbot / Conversation
- Mục đích: Liệt kê Telegram binding.
- Mô tả: Trả các bot binding của tenant.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": "binding-uuid",
    "tenantId": "tenant-uuid",
    "chatbotId": "chatbot-uuid",
    "botToken": "bot-token",
    "secretPath": "generated-secret-path",
    "status": "ACTIVE"
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Không đưa bot token thật vào tài liệu public.

## [POST] /api/telegram/bindings

- Nhóm API: Chatbot / Conversation
- Mục đích: Tạo Telegram binding.
- Mô tả: Liên kết chatbot với bot token và sinh `secretPath`.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "chatbotId": "chatbot-uuid",
  "botToken": "telegram-bot-token"
}
```

* Response thành công:

```json
{
  "id": "binding-uuid",
  "tenantId": "tenant-uuid",
  "chatbotId": "chatbot-uuid",
  "botToken": "telegram-bot-token",
  "secretPath": "generated-secret-path",
  "status": "ACTIVE"
}
```

* Response lỗi:

```json
{
  "error": "BadRequest",
  "message": "This chatbot is already bound to Telegram"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Body schema là `CreateTelegramBindingDto`.

## [POST] /webhook/telegram/{secretPath}

- Nhóm API: Chatbot / Conversation
- Mục đích: Nhận Telegram update.
- Mô tả: Nhận update webhook, tìm binding theo `secretPath`, lưu message và gọi chatbot.
- Authentication: `secretPath`.
- Request params / path params: `secretPath` string.
- Query params: Không có.
- Request headers: `Content-Type: application/json`
- Request body:

```json
{
  "update_id": 1000,
  "message": {
    "text": "I need a sofa",
    "chat": {
      "id": 123456
    }
  }
}
```

* Response thành công:

```json
"ok"
```

* Response lỗi:

```json
{
  "status": 400,
  "error": "Bad Request"
}
```

* Status codes: `200`, `400`
* Ghi chú: Controller trả `ok` ngay sau khi đưa update vào worker pool; lỗi xử lý event được ghi log trong worker. Text `RATE GOOD`, `RATE BAD`, `CONFIRM`, `CANCEL` có xử lý riêng trong webhook.

## [GET] /api/runtime/llm

- Nhóm API: System / Health check
- Mục đích: Liệt kê Python runtime hoạt động trong hệ thống.
- Mô tả: Trả map tenant id tới runtime info.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "tenant-uuid": {
    "baseUrl": "http://127.0.0.1:8101",
    "pid": 12345,
    "lastUsedAt": "2026-05-05T08:00:00Z"
  }
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Endpoint thuộc `LlmRuntimeController`.

## [GET] /api/ops/platform

- Nhóm API: System / Health check
- Mục đích: Lấy snapshot vận hành toàn nền tảng.
- Mô tả: Trả số tenant, runtime hoạt động, thống kê purchase request và snapshot từng tenant.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "generatedAt": "2026-05-05T08:00:00Z",
  "tenantCount": 2,
  "activeRuntimeSessionCount": 1,
  "purchaseRequestStats": {},
  "tenants": []
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Response DTO nằm trong `com.app.ops.dto`.

## [GET] /api/ops/tenant

- Nhóm API: System / Health check
- Mục đích: Lấy snapshot vận hành tenant.
- Mô tả: Trả runtime, KB status, bots và thống kê purchase request của tenant trong session.
- Authentication: Session `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "tenantId": "tenant-uuid",
  "tenantCode": "demo_caco",
  "tenantName": "Demo CaCo",
  "generatedAt": "2026-05-05T08:00:00Z",
  "runtime": {
    "active": true,
    "status": "RUNNING",
    "baseUrl": "http://127.0.0.1:8101",
    "pid": 12345,
    "lastUsedAt": "2026-05-05T08:00:00Z"
  },
  "kb": {
    "kbDir": "F:/20251/prj3/chatbot/kb/noithatcaco",
    "status": "READY",
    "lastRebuildAt": "2026-05-05T08:00:00Z",
    "artifactCount": 4
  },
  "bots": [],
  "purchaseRequestStats": {}
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Endpoint thuộc `OperationsController`.

## [GET] /api/ops/benchmark-summary

- Nhóm API: Demo / Test API
- Mục đích: Lấy tổng hợp kết quả thử nghiệm retrieval.
- Mô tả: Đọc và trả benchmark summary cho các mode retrieval.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: Không có.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "generatedAt": "2026-05-05T08:00:00Z",
  "modes": []
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: DTO cụ thể nằm trong `BenchmarkSummaryDto`.

## [POST] /api/ops/runtime/evict

- Nhóm API: System / Health check
- Mục đích: Evict runtime chatbot của tenant.
- Mô tả: Dừng process Python runtime để request kế tiếp tạo runtime mới.
- Authentication: Session `PLATFORM_ADMIN` hoặc `TENANT_ADMIN`.
- Request params / path params: Không có.
- Query params: `tenantId` optional với tenant admin, bắt buộc với platform admin.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "success": true,
  "action": "EVICT_RUNTIME",
  "tenantId": "tenant-uuid",
  "message": "Tenant runtime evicted. The next request will cold start a fresh runtime if needed.",
  "executedAt": "2026-05-05T08:00:00Z"
}
```

* Response lỗi:

```json
{
  "status": 400,
  "error": "Bad Request"
}
```

* Status codes: `200`, `400`, `401`, `403`
* Ghi chú: Platform admin phải truyền `tenantId`.

## [GET] /admin/api/stats/overview

- Nhóm API: Demo / Test API
- Mục đích: Lấy thống kê tổng quan admin.
- Mô tả: Trả tổng conversation, lead, conversion rate, shipped rate, feedback positive rate.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: `days` integer, mặc định `7`.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "totalConversations": 10,
  "totalLeads": 3,
  "leadConversionRate": 0.3,
  "shippedRate": 0.0,
  "feedbackPositiveRate": 1.0,
  "leadStatusBreakdown": {
    "NEW": 3
  }
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Endpoint thuộc `AdminStatsController`.

## [GET] /admin/api/stats/by-tenant

- Nhóm API: Demo / Test API
- Mục đích: Lấy thống kê theo tenant.
- Mô tả: Trả số conversation, lead, contacted, shipped và feedback positive rate theo tenant.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: `days` integer, mặc định `30`.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "tenantId": "tenant-uuid",
    "conversations": 10,
    "leads": 3,
    "contacted": 1,
    "shipped": 0,
    "feedbackPosRate": 1.0
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Sắp xếp giảm theo số leads.

## [GET] /admin/api/stats/timeseries

- Nhóm API: Demo / Test API
- Mục đích: Lấy thống kê theo ngày.
- Mô tả: Trả số lead tạo mới, shipped, feedback good/bad theo từng ngày.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: `days` integer, mặc định `30`.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "day": "2026-05-05",
    "leadsCreated": 2,
    "shipped": 1,
    "feedbackGood": 1,
    "feedbackBad": 0
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Dữ liệu được tính từ repository trong backend.

## [GET] /admin/api/leads

- Nhóm API: Demo / Test API
- Mục đích: Platform admin liệt kê leads.
- Mô tả: Trả tối đa 200 leads mới nhất theo tenant.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: Không có.
- Query params: `tenantId` string.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": 1,
    "tenantId": "tenant-uuid",
    "channel": "web",
    "conversationId": "conversation-uuid",
    "customerHandle": "",
    "status": "NEW",
    "slotsJson": "{}",
    "transcript": "transcript",
    "orderInfo": "",
    "shippingStatus": "NEW",
    "stage": "HANDOFF",
    "createdAt": "2026-05-05T08:00:00Z"
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: Endpoint phục vụ quản trị/demo lead.

## [POST] /admin/api/leads/{id}/status

- Nhóm API: Demo / Test API
- Mục đích: Platform admin cập nhật lead status.
- Mô tả: Cập nhật field `status` của lead.
- Authentication: Session `PLATFORM_ADMIN`.
- Request params / path params: `id` long.
- Query params: `status` string.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "id": 1,
  "tenantId": "tenant-uuid",
  "status": "CONTACTED"
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`, `500`
* Ghi chú: Controller dùng `orElseThrow()` nếu lead id không tồn tại.

## [GET] /tenant/api/leads

- Nhóm API: Demo / Test API
- Mục đích: Tenant operator liệt kê leads.
- Mô tả: Trả tối đa 200 leads mới nhất của tenant.
- Authentication: Session `TENANT_ADMIN` hoặc `TENANT_MEMBER`.
- Request params / path params: Không có.
- Query params: `tid` string.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
[
  {
    "id": 1,
    "tenantId": "tenant-uuid",
    "channel": "web",
    "conversationId": "conversation-uuid",
    "status": "NEW",
    "shippingStatus": "NEW",
    "stage": "HANDOFF"
  }
]
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`
* Ghi chú: `tid` phải khớp tenant trong session.

## [POST] /tenant/api/leads/{id}/status

- Nhóm API: Demo / Test API
- Mục đích: Tenant operator cập nhật lead status.
- Mô tả: Cập nhật field `status` của lead thuộc tenant.
- Authentication: Session `TENANT_ADMIN` hoặc `TENANT_MEMBER`.
- Request params / path params: `id` long.
- Query params: `tid` string, `status` string.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "id": 1,
  "tenantId": "tenant-uuid",
  "status": "CONTACTED"
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`, `500`
* Ghi chú: Kiểm tra tenant ownership trong controller.

## [POST] /tenant/api/reply

- Nhóm API: Demo / Test API
- Mục đích: Nhân viên trả lời khách qua kênh ngoài.
- Mô tả: Gửi message tới Messenger hoặc Telegram dựa trên channel của lead.
- Authentication: Session `TENANT_ADMIN` hoặc `TENANT_MEMBER`.
- Request params / path params: Không có.
- Query params: `tid` string.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "leadId": 1,
  "message": "Nhân viên liên hệ xác nhận đơn hàng."
}
```

* Response thành công:

```json
{}
```

* Response lỗi:

```json
{
  "status": 500,
  "error": "Internal Server Error"
}
```

* Status codes: `200`, `401`, `403`, `500`
* Ghi chú: Controller trả `void`; channel hỗ trợ là `messenger` và `telegram`.

## [POST] /tenant/api/leads-ops/order-info

- Nhóm API: Demo / Test API
- Mục đích: Lưu thông tin đơn hàng cho lead.
- Mô tả: Cập nhật `orderInfo` và set `shippingStatus` thành `READY`.
- Authentication: Session `TENANT_ADMIN` hoặc `TENANT_MEMBER`.
- Request params / path params: Không có.
- Query params: `tid` string.
- Request headers: `Content-Type: application/json`, Cookie session.
- Request body:

```json
{
  "leadId": 1,
  "orderInfo": "Sofa 2 chỗ, giao tại 123 Nguyễn Trãi"
}
```

* Response thành công:

```json
{
  "id": 1,
  "tenantId": "tenant-uuid",
  "orderInfo": "Sofa 2 chỗ, giao tại 123 Nguyễn Trãi",
  "shippingStatus": "READY"
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`, `500`
* Ghi chú: Request body là `OrderInfoReq`.

## [POST] /tenant/api/leads-ops/{id}/ship

- Nhóm API: Demo / Test API
- Mục đích: Cập nhật đơn hàng sang trạng thái giao hàng.
- Mô tả: Set `shippingStatus` thành `SHIPPED`, gửi thông báo qua channel và set `stage` thành `FULFILLED`.
- Authentication: Session `TENANT_ADMIN` hoặc `TENANT_MEMBER`.
- Request params / path params: `id` long.
- Query params: `tid` string.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "id": 1,
  "tenantId": "tenant-uuid",
  "shippingStatus": "SHIPPED",
  "stage": "FULFILLED"
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`, `500`
* Ghi chú: Có gửi outbox cho Messenger/Telegram nếu channel tương ứng.

## [POST] /tenant/api/leads-ops/{id}/reset

- Nhóm API: Demo / Test API
- Mục đích: Reset stage hội thoại lead.
- Mô tả: Set `stage` của lead thành `DISCOVER`.
- Authentication: Session `TENANT_ADMIN` hoặc `TENANT_MEMBER`.
- Request params / path params: `id` long.
- Query params: `tid` string.
- Request headers: Cookie session.
- Request body:

```json
{}
```

* Response thành công:

```json
{
  "id": 1,
  "tenantId": "tenant-uuid",
  "stage": "DISCOVER"
}
```

* Response lỗi:

```json
{
  "status": 403,
  "error": "Forbidden"
}
```

* Status codes: `200`, `401`, `403`, `500`
* Ghi chú: Endpoint phục vụ vận hành hội thoại sau handoff.

## Bảng tổng hợp API

| Nhóm API | Method | Endpoint | Mục đích |
| -------- | ------ | -------- | -------- |
| System / Health check | GET | `/healthz` | Kiểm tra Python chatbot service |
| Authentication / User | POST | `/api/login/admin` | Đăng nhập platform admin |
| Authentication / User | POST | `/api/login/tenant` | Đăng nhập tenant member |
| Authentication / User | POST | `/api/login/logout` | Đăng xuất |
| Authentication / User | GET | `/api/me` | Lấy principal hiện hành |
| Authentication / User | GET | `/api/admin/tenants` | Liệt kê tenant |
| Authentication / User | POST | `/api/admin/tenants` | Tạo tenant |
| Authentication / User | GET | `/api/admin/tenants/{tenantId}` | Lấy chi tiết tenant |
| Authentication / User | GET | `/api/admin/tenant-members` | Liệt kê member bởi platform admin |
| Authentication / User | POST | `/api/admin/tenant-members` | Tạo member bởi platform admin |
| Authentication / User | GET | `/api/tenant-members` | Tenant admin liệt kê member |
| Authentication / User | POST | `/api/tenant-members` | Tenant admin tạo member |
| Product management | GET | `/api/chatbots` | Liệt kê chatbot |
| Product management | POST | `/api/chatbots` | Tạo chatbot |
| Product management | PUT | `/api/chatbots/{id}` | Cập nhật chatbot |
| Data import / processing | GET | `/api/kb/source-urls` | Liệt kê URL nguồn |
| Data import / processing | POST | `/api/kb/source-urls` | Thêm URL nguồn |
| Data import / processing | DELETE | `/api/kb/source-urls` | Xóa URL nguồn |
| Knowledge base / Retrieval | POST | `/api/kb/rebuild` | Xử lý lại knowledge base |
| Chatbot / Conversation | POST | `/api/chat/start` | Tạo conversation theo tenant |
| Chatbot / Conversation | POST | `/api/chat/send` | Gửi tin nhắn theo tenant |
| Chatbot / Conversation | GET | `/api/chat/conversations` | Liệt kê conversation theo tenant |
| Chatbot / Conversation | GET | `/api/chat/conversation/{conversationId}/messages` | Lấy message theo tenant |
| Chatbot / Conversation | PUT | `/api/chat/conversation/{conversationId}/rename` | Đổi tên conversation theo tenant |
| Chatbot / Conversation | DELETE | `/api/chat/conversation/{conversationId}` | Xóa conversation theo tenant |
| Product recommendation / advising | POST | `/api/general/chat/start` | Tạo conversation tư vấn chung |
| Product recommendation / advising | POST | `/api/general/chat/send` | Gửi tin nhắn tư vấn chung |
| Product recommendation / advising | GET | `/api/general/chat/conversations` | Liệt kê conversation tư vấn chung |
| Product recommendation / advising | GET | `/api/general/chat/conversation/{conversationId}/messages` | Lấy message tư vấn chung |
| Product recommendation / advising | PUT | `/api/general/chat/conversation/{conversationId}/rename` | Đổi tên conversation tư vấn chung |
| Product recommendation / advising | DELETE | `/api/general/chat/conversation/{conversationId}` | Xóa conversation tư vấn chung |
| Chatbot / Conversation | POST | `/chat` | Python chatbot sinh câu trả lời |
| Demo / Test API | POST | `/feedback` | Ghi feedback Python |
| Demo / Test API | GET | `/state` | Đọc state Python conversation |
| Chatbot / Conversation | GET | `/api/purchase-requests` | Liệt kê purchase request |
| Chatbot / Conversation | PUT | `/api/purchase-requests/{id}/status` | Cập nhật status purchase request |
| Chatbot / Conversation | PUT | `/api/purchase-requests/{id}/claim` | Nhận xử lý purchase request |
| Chatbot / Conversation | PUT | `/api/purchase-requests/{id}/assign` | Phân công purchase request |
| Chatbot / Conversation | GET | `/api/messenger/bindings` | Liệt kê Messenger binding |
| Chatbot / Conversation | POST | `/api/messenger/bindings` | Tạo Messenger binding |
| Chatbot / Conversation | DELETE | `/api/messenger/bindings/{id}` | Ngưng kích hoạt Messenger binding |
| Chatbot / Conversation | GET | `/webhook/messenger` | Verify Messenger webhook |
| Chatbot / Conversation | POST | `/webhook/messenger` | Nhận Messenger event |
| Chatbot / Conversation | GET | `/api/telegram/bindings` | Liệt kê Telegram binding |
| Chatbot / Conversation | POST | `/api/telegram/bindings` | Tạo Telegram binding |
| Chatbot / Conversation | POST | `/webhook/telegram/{secretPath}` | Nhận Telegram update |
| System / Health check | GET | `/api/runtime/llm` | Liệt kê runtime LLM |
| System / Health check | GET | `/api/ops/platform` | Snapshot vận hành nền tảng |
| System / Health check | GET | `/api/ops/tenant` | Snapshot vận hành tenant |
| Demo / Test API | GET | `/api/ops/benchmark-summary` | Kết quả thử nghiệm retrieval |
| System / Health check | POST | `/api/ops/runtime/evict` | Evict runtime tenant |
| Demo / Test API | GET | `/admin/api/stats/overview` | Thống kê tổng quan |
| Demo / Test API | GET | `/admin/api/stats/by-tenant` | Thống kê theo tenant |
| Demo / Test API | GET | `/admin/api/stats/timeseries` | Thống kê theo ngày |
| Demo / Test API | GET | `/admin/api/leads` | Admin liệt kê leads |
| Demo / Test API | POST | `/admin/api/leads/{id}/status` | Admin cập nhật lead status |
| Demo / Test API | GET | `/tenant/api/leads` | Tenant liệt kê leads |
| Demo / Test API | POST | `/tenant/api/leads/{id}/status` | Tenant cập nhật lead status |
| Demo / Test API | POST | `/tenant/api/reply` | Nhân viên trả lời qua kênh ngoài |
| Demo / Test API | POST | `/tenant/api/leads-ops/order-info` | Lưu thông tin đơn hàng |
| Demo / Test API | POST | `/tenant/api/leads-ops/{id}/ship` | Đánh dấu shipped |
| Demo / Test API | POST | `/tenant/api/leads-ops/{id}/reset` | Reset stage lead |
