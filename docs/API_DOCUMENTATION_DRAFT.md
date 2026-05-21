# API Documentation (Draft)

**Version**: 1.0
**Last Updated**: 2026-05-20

---

## 1. General Chat API (Không tạo purchase request)

Dành cho người dùng chat tư vấn chung, so sánh sản phẩm, hoặc khảo giá mà không gắn với cửa hàng cụ thể.

### 1.1 POST /api/general/chat/start

**Mô tả**: Tạo mới một conversation cho chat tư vấn chung.

**Request Body**:
```json
{
  "userExternalId": "user-123",
  "mode": "general_compare"
}
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| userExternalId | string | Yes | ID người dùng từ phía client |
| mode | string | No | `general_compare` (default) hoặc `market_price` |

**Response**:
```json
{
  "conversationId": "uuid-conv-123"
}
```

**Lưu ý**:
- `mode=general_compare`: So sánh sản phẩm, KHÔNG tạo purchase request
- `mode=market_price`: Khảo giá, KHÔNG tạo purchase request

---

### 1.2 POST /api/general/chat/send

**Mô tả**: Gửi tin nhắn và nhận phản hồi từ chatbot.

**Request Body**:
```json
{
  "conversationId": "uuid-conv-123",
  "userExternalId": "user-123",
  "message": "So sánh sofa SFG041 và SFG040",
  "mode": "general_compare"
}
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| conversationId | string | Yes | ID conversation từ /start |
| userExternalId | string | Yes | ID người dùng |
| message | string | Yes | Nội dung tin nhắn |
| mode | string | No | `general_compare` hoặc `market_price` |

**Response**:
```json
{
  "reply": "## So sánh Sofa SFG041, SFG040...\n\n| Tiêu chí | SFG041 | SFG040 |\n|----------|--------|--------|...",
  "latencyMs": 5230,
  "model": "claude-sonnet-4-6",
  "adapter": "",
  "llmBaseUrl": "http://chatbot-api:8000"
}
```

**Lưu ý quan trọng**:
- Mode `general_compare` và `market_price` KHÔNG tạo purchase request/lead
- Bot sẽ trả về so sánh trung lập, không bịa thông tin
- Nếu thiếu dữ liệu, bot trả về "chưa có dữ liệu"

---

### 1.3 GET /api/general/chat/conversations

**Mô tả**: Liệt kê các conversation của người dùng.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| userExternalId | string | Yes | ID người dùng |
| mode | string | No | `general_compare` hoặc `market_price` |
| limit | int | No | Số lượng conversation (default: 50) |

**Response**:
```json
[
  {
    "id": "uuid-conv-123",
    "title": "So sánh sofa SFG041 và SFG040",
    "createdAt": "2026-05-20T10:30:00Z",
    "messageCount": 5,
    "lastPreview": "So sánh sofa SFG041 và SFG040 theo chất liệu..."
  }
]
```

---

### 1.4 GET /api/general/chat/conversation/{conversationId}/messages

**Mô tả**: Lấy lịch sử tin nhắn của một conversation.

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| conversationId | UUID | ID conversation |

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| userExternalId | string | Yes | ID người dùng |
| mode | string | No | `general_compare` hoặc `market_price` |

**Response**:
```json
[
  {
    "role": "user",
    "content": "So sánh sofa SFG041 và SFG040",
    "createdAt": "2026-05-20T10:30:00Z"
  },
  {
    "role": "assistant",
    "content": "## So sánh Sofa SFG041, SFG040...",
    "createdAt": "2026-05-20T10:30:05Z"
  }
]
```

---

### 1.5 PUT /api/general/chat/conversation/{conversationId}/rename

**Mô tả**: Đổi tên title của conversation.

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| conversationId | UUID | ID conversation |

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| userExternalId | string | Yes | ID người dùng |
| mode | string | No | `general_compare` hoặc `market_price` |

**Request Body**:
```json
{
  "title": "So sánh sofa theo giá và chất liệu"
}
```

**Response**:
```json
{
  "id": "uuid-conv-123",
  "title": "So sánh sofa theo giá và chất liệu"
}
```

---

### 1.6 DELETE /api/general/chat/conversation/{conversationId}

**Mô tả**: Xóa conversation và tất cả tin nhắn.

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| conversationId | UUID | ID conversation |

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| userExternalId | string | Yes | ID người dùng |
| mode | string | No | `general_compare` hoặc `market_price` |

**Response**:
```json
{
  "deleted": true,
  "id": "uuid-conv-123"
}
```

---

## 2. Tenant Chat API (Có thể tạo purchase request)

Dành cho chat với chatbot của cửa hàng cụ thể, có thể tạo purchase request khi đủ điều kiện.

### 2.1 POST /api/chat/start

**Mô tả**: Tạo mới conversation cho chatbot của cửa hàng.

**Request Body**:
```json
{
  "chatbotId": "uuid-bot-123",
  "userExternalId": "user-123"
}
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| chatbotId | string | Yes | ID chatbot của cửa hàng |
| userExternalId | string | Yes | ID người dùng |

**Response**:
```json
{
  "conversationId": "uuid-conv-123"
}
```

---

### 2.2 POST /api/chat/send

**Mô tả**: Gửi tin nhắn và nhận phản hồi từ chatbot cửa hàng.

**Request Body**:
```json
{
  "conversationId": "uuid-conv-123",
  "userExternalId": "user-123",
  "message": "Tôi muốn mua sofa SFG041"
}
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| conversationId | string | Yes | ID conversation |
| userExternalId | string | Yes | ID người dùng |
| message | string | Yes | Nội dung tin nhắn |

**Response**:
```json
{
  "reply": "Mình đã ghi nhận yêu cầu mua hàng của bạn rồi.\n\nThông tin mình thu thập được:\n- Họ tên: Nguyễn Văn A\n- SĐT: 0901234567\n- Địa chỉ: 123 đường ABC\n\nNhân viên cửa hàng sẽ sớm liên hệ với bạn!",
  "latencyMs": 5230,
  "model": "claude-sonnet-4-6",
  "adapter": "",
  "llmBaseUrl": "http://chatbot-api:8000"
}
```

**Purchase Request Behavior**:
- Chatbot chỉ tạo purchase request khi:
  - Mode = `tenant_sales`
  - User ở stage `close` và gửi `confirm`
  - Đã thu thập đủ thông tin (name, phone, address)
- Nếu chưa đủ điều kiện, bot sẽ hỏi thêm thông tin thay vì tạo đơn hàng

---

### 2.3 GET /api/chat/conversations

**Mô tả**: Liệt kê conversation của người dùng với chatbot cụ thể.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| chatbotId | UUID | Yes | ID chatbot |
| userExternalId | string | Yes | ID người dùng |
| limit | int | No | Số lượng (default: 50) |

---

### 2.4 GET /api/chat/conversation/{conversationId}/messages

**Mô tả**: Lấy lịch sử tin nhắn.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| userExternalId | string | Yes | ID người dùng |

---

### 2.5 PUT /api/chat/conversation/{conversationId}/rename

**Mô tả**: Đổi tên conversation.

---

### 2.6 DELETE /api/chat/conversation/{conversationId}

**Mô tả**: Xóa conversation.

---

## 3. Chatbot Admin API

Quản trị tạo/cập nhật/xóa chatbot.

### 3.1 POST /api/chatbots

**Mô tả**: Tạo mới chatbot.

**Request Body**:
```json
{
  "name": "Chatbot Tư Vấn Sofa",
  "channel": "web",
  "personaJson": "{}",
  "responseStyle": "natural",
  "mode": "tenant_sales",
  "provider": "claude"
}
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Tên chatbot |
| channel | string | No | Kênh (web, messenger, telegram) |
| personaJson | string | No | JSON config persona |
| responseStyle | string | No | `natural`, `balanced`, hoặc `fast` |
| mode | string | No | `tenant_sales`, `general_compare`, `market_price` |
| provider | string | No | `claude` (default) hoặc `local` |

**Lưu ý**:
- `provider=claude`: API key được quản lý ở cấp hệ thống (env variable), không nhập per-chatbot
- Các field `apiModel`, `apiKey`, `apiBaseUrl` không còn được lưu nữa

**Response**:
```json
{
  "id": "uuid-bot-123",
  "name": "Chatbot Tư Vấn Sofa",
  "channel": "web",
  "status": "ACTIVE",
  "mode": "tenant_sales",
  "provider": "claude"
}
```

---

### 3.2 PUT /api/chatbots/{id}

**Mô tả**: Cập nhật chatbot.

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| id | UUID | ID chatbot |

**Request Body**: Tương tự POST /api/chatbots

---

### 3.3 DELETE /api/chatbots/{id}

**Mô tả**: Xóa chatbot.

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| id | UUID | ID chatbot |

**Response**:
```json
{
  "deleted": true,
  "id": "uuid-bot-123"
}
```

---

### 3.4 GET /api/chatbots

**Mô tả**: Liệt kê tất cả chatbot của tenant.

**Response**:
```json
[
  {
    "id": "uuid-bot-123",
    "name": "Chatbot Tư Vấn Sofa",
    "channel": "web",
    "status": "ACTIVE",
    "mode": "tenant_sales",
    "provider": "claude"
  }
]
```

---

## 4. Messenger Webhook

### 4.1 GET /webhook/messenger

**Mô tả**: Verify webhook với Facebook.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| hub.mode | string | `subscribe` |
| hub.verify_token | string | Verify token từ config |
| hub.challenge | string | Challenge từ Facebook |

**Response**: Trả về challenge string.

---

### 4.2 POST /webhook/messenger

**Mô tả**: Nhận webhook event từ Facebook Messenger.

**Request Body**: (Facebook Messenger webhook format)

**Response**:
```json
{
  "status": "ok"
}
```

**Lưu ý**:
- Webhook xử lý async, trả về ngay
- Bot trả lời qua Messenger Send API
- CONFIRM → tạo purchase request (nếu mode=tenant_sales)
- general_compare/market_price: KHÔNG tạo purchase request

---

## 5. Health/Status Endpoints

### 5.1 GET /healthz (Python Chatbot API)

**Mô tả**: Check health status của chatbot API.

**Response**:
```json
{
  "status": "ready",
  "ready": true,
  "error": null,
  "cached_pipelines": 0,
  "kb_dir": "/app/kb/article",
  "kb_loaded": true,
  "retrieval_mode": "keyword",
  "test_mode": false
}
```

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| status | string | `ready` hoặc `loading` |
| ready | boolean | True nếu server sẵn sàng |
| cached_pipelines | int | Số pipelines local model đang cache |
| kb_loaded | boolean | True nếu knowledge base đã load |

---

### 5.2 GET /actuator/health (Spring Boot)

**Mô tả**: Spring Boot health check.

---

## 6. Price Check UI Route

### 6.1 GET /price-check/

**Mô tả**: UI page cho market_price chat.

**Lưu ý**: Đây là UI route, không phải API. API calls đi qua `/api/general/chat/start` và `/api/general/chat/send` với `mode=market_price`.

---

## 7. Mode Contract Summary

| Mode | Có tạo purchase request? | Mô tả |
|------|--------------------------|-------|
| `tenant_sales` | Có (khi confirm) | Chat tư vấn cửa hàng, tạo lead/purchase request |
| `general_compare` | Không | So sánh sản phẩm, trung lập |
| `market_price` | Không | Khảo giá, cảnh báo khi thiếu data |

---

## 8. Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad request (thiếu required field) |
| 404 | Resource not found |
| 403 | Forbidden (không có quyền) |
| 500 | Internal server error |
| 503 | Service unavailable (model đang loading) |

---

## 9. Authentication

- Tất cả API endpoints (trừ webhook verify) đều require authentication
- Session-based authentication qua Spring Security
- Tenant context được inject từ session

---

## 10. Notes

### 10.1 Purchase Request Guardrails

- `general_compare` và `market_price` KHÔNG tạo purchase request bất kể user input
- `tenant_sales` chỉ tạo purchase request khi:
  - User ở stage `close`
  - User gửi `confirm`
  - Đã thu thập đủ name, phone, address

### 10.2 Claude Provider

- Claude là system-level provider (env-only config)
- Không cần nhập API key cho từng chatbot
- Model: `claude-sonnet-4-6`

### 10.3 Local Fallback

- Local model (Qwen) chỉ được load khi `FALLBACK_TO_LOCAL_ENABLED=true`
- Mặc định là `false` cho VPS CPU-only deployment

---

**Created**: 2026-05-20
**Status**: Draft (cần review lại một số endpoints)
