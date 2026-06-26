# Hình 4.4 - Luồng online RAG cho chế độ tenant_sales

## Mô tả

Hình vẽ luồng xử lý tin nhắn từ người dùng đến khi nhận phản hồi, qua các bước: Backend xác định tenant/conversation → Resolve active KB version → FastAPI retrieval + prompt → Claude API → Backend ghi hội thoại + kiểm tra nghiệp vụ.

## Sơ đồ luồng (ngang - Left to Right)

```
  ┌──────────────────────────┐
  │  Người dùng              │
  │  (Web / Messenger /      │
  │   Telegram)              │
  └────────────┬─────────────┘
               │ Tin nhắn
               ▼
  ┌─────────────────────────────┐
  │  Backend:                   │
  │  Xác định tenant,           │
  │  conversation, channel      │
  └────────────┬────────────────┘
               │
               ▼
  ┌─────────────────────────────┐
  │  Backend:                   │
  │  Resolve active KB version  │←──── Active KB Version (database)
  └────────────┬────────────────┘
               │ Yêu cầu chat
               ▼
  ┌─────────────────────────────┐
  │  FastAPI:                   │
  │  Retrieval top-k            │
  │  + Prompt Building          │
  └────────────┬────────────────┘
               │ Prompt
               ▼
  ┌─────────────────────────────┐
  │  Claude API (Anthropic)     │
  │  External Service           │──── Nét đứt
  └────────────┬────────────────┘
               │ Phản hồi
               ▼
  ┌─────────────────────────────┐
  │  Backend:                   │
  │  Ghi hội thoại,             │────→ PostgreSQL (Message, Lead,
  │  kiểm tra nghiệp vụ         │      Purchase Request)
  └────────────┬────────────────┘
               │ Phản hồi
               ▼
  ┌─────────────────────────────┐
  │  Người dùng                 │
  └─────────────────────────────┘
```

## Cách vẽ (draw.io)

### Layout
- Hướng: Trái → Phải (LR)
- 6 cột: User → Backend (2 bước) → FastAPI → Claude API → Backend → User

### Các khối

| Vị trí | Nhãn | Ghi chú |
|--------|------|---------|
| Cột 1 | **Người dùng** (Web / Messenger / Telegram) | Đầu vào |
| Cột 2 | **Backend: Xác định tenant, conversation, channel** | Xác định context |
| Cột 2 (phía dưới) | **Active KB Version** (database) | Lưu kb_dir, được backend resolve |
| Cột 3 | **Backend: Resolve active KB version** | Lấy kb_dir từ TenantKbVersion |
| Cột 4 | **FastAPI: Retrieval top-k + Prompt Building** | Đọc KB file từ kb_dir, build prompt |
| Cột 5 | **Claude API (Anthropic)** | External service — nét đứt |
| Cột 6 | **Backend: Ghi hội thoại, kiểm tra nghiệp vụ** | Lưu message, check lead/purchase |
| Bên dưới | **PostgreSQL** (Message, Lead, Purchase Request) | Database |

### Các đường nối

| Từ | Đến | Nhãn | Kiểu |
|----|-----|------|------|
| Người dùng | Backend: Xác định tenant | Tin nhắn | Mũi tên phải |
| Backend: Xác định tenant | Backend: Resolve KB | (không nhãn) | Mũi tên phải |
| Active KB Version | Backend: Resolve KB | KB dir | Mũi tên lên |
| Backend: Resolve KB | FastAPI | Yêu cầu chat | Mũi tên phải |
| FastAPI | Claude API | Prompt | Mũi tên phải, nét đứt |
| Claude API | FastAPI | Phản hồi | Mũi tên trái, nét đứt |
| FastAPI | Backend: Ghi hội thoại | Kết quả | Mũi tên phải |
| Backend: Ghi hội thoại | PostgreSQL | (không nhãn) | Mũi tên xuống |
| Backend: Ghi hội thoại | Người dùng | Phản hồi | Mũi tên phải (vòng về) |

### Phân biệt
- **Phần tự làm**: Backend, FastAPI Runtime, PostgreSQL, Active KB Version
- **External**: Claude API (Anthropic) — vẽ nét đứt
