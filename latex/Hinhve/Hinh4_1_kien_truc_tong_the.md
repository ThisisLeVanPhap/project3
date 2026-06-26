# Hình 4.1 - Kiến trúc tổng thể Multi-tenant RAG Chatbot

## Sơ đồ kiến trúc

```
  ┌──────────────────┐  ┌──────────┐  ┌──────────┐
  │  Web Chat &      │  │          │  │          │
  │  Admin UI        │  │Messenger │  │ Telegram │
  │  (Browser)       │  │(Meta)    │  │(Bot)     │
  └────────┬─────────┘  └─────┬────┘  └─────┬────┘
           │                  │              │
           │ HTTP API         │ Webhook      │ Webhook
           │                  │ (bên ngoài)  │ (bên ngoài)
           │                  │              │
           ▼                  ▼              ▼
  ┌────────────────────────────────────────────────────┐
  │                 Spring Boot Backend                │
  │  - Controller nhận webhook Messenger/Telegram      │
  │  - Controller REST cho Web UI                      │
  │  - Xác định tenant, conversation, channel          │
  │  - Xử lý nghiệp vụ (lead, purchase)                │
  │  - Quản lý Product Dataset, KB binding             │
  └────┬──────────────┬────────────────────┬──────────┘
       │              │                    │
       │ Đọc/ghi      │ Quản lý            │ Yêu cầu chat
       │ dữ liệu      │ artifact path      │
       ▼              ▼                    ▼
  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐
  │PostgreSQL│  │KB Artifact   │  │  FastAPI Chatbot  │
  │          │  │Storage       │  │  Runtime          │
  │Tenant,   │  │(File System) │  │                   │
  │conv, msg,│  │              │  │  - Retrieval      │
  │lead,     │  │catalog, rag, │  │    top-k          │
  │purchase, │  │manifest      │  │  - Prompt         │
  │artifact  │  │              │  │    building        │
  │metadata  │  │              │  │  - Rule fallback  │
  └──────────┘  └──────────────┘  └────────┬─────────┘
                                           │
                                           │ Gọi API
                                           │ (nét đứt)
                                           ▼
                                  ┌──────────────────┐
                                  │  Claude API       │
                                  │  (Anthropic)      │
                                  │  External Service │
                                  └──────────────────┘
                                ←── runtime đọc KB dir
```

## Giải thích các thành phần

### Tầng 1: Kênh truy cập
- **Web Chat & Admin UI**: Giao diện trong trình duyệt, gọi HTTP API vào backend
- **Messenger**: Nền tảng Meta, gửi tin nhắn qua **webhook** (cần public URL, ví dụ ngrok)
- **Telegram**: Gửi tin nhắn qua **webhook** (cần public URL)

### Tầng 2: Backend (Spring Boot)
Tiếp nhận từ cả 3 kênh. Với Messenger/Telegram, backend có `@RestController` mapping endpoint `/webhook/messenger` và `/webhook/telegram/{secretPath}` để nhận dữ liệu từ webhook.

### Tầng 3: Lưu trữ
- **PostgreSQL**: Chứa dữ liệu tenant, hội thoại, product dataset, artifact metadata, lead, purchase request
- **KB Artifact Storage**: Lưu trên **file system** — thư mục chứa catalog, rag products, manifest. Backend chỉ quản lý đường dẫn (artifactPath, kb_dir)

### Tầng 4: Chatbot Runtime (FastAPI)
- Retrieval top-k từ KB của tenant
- Prompt building
- Gọi Claude API hoặc dùng rule/template fallback

### Tầng 5: External Service
- **Claude API (Anthropic)**: Dịch vụ LLM do Anthropic cung cấp

## Các đường nối chính

| # | Từ | Đến | Mô tả |
|---|-----|-----|--------|
| 1 | Web Chat & Admin UI | Spring Boot Backend | HTTP API: REST request từ trình duyệt |
| 2 | Messenger | Spring Boot Backend | Webhook: Meta gửi POST đến `/webhook/messenger` |
| 3 | Telegram | Spring Boot Backend | Webhook: Telegram gửi POST đến `/webhook/telegram/{secretPath}` |
| 4 | Spring Boot Backend | PostgreSQL | Đọc/ghi dữ liệu vận hành |
| 5 | Spring Boot Backend | KB Artifact Storage | Ghi file khi build artifact; lưu đường dẫn vào DB |
| 6 | Spring Boot Backend | FastAPI Chatbot Runtime | Gửi yêu cầu chat (tenant, conversation, message) |
| 7 | FastAPI Chatbot Runtime | Claude API | Gọi API sinh phản hồi |
| 8 | KB Artifact Storage | FastAPI Chatbot Runtime | Đọc file KB từ thư mục (theo kb_dir) — mũi tên ngược |

## Ghi chú
- **Phần tự làm**: Spring Boot Backend, FastAPI Runtime, PostgreSQL schema, KB pipeline, Web UI
- **Phần external**: Claude API (gọi API), Webhook infrastructure (Messenger/Telegram tự gửi request đến server)
- Vẽ Claude API và các đường nối đến nó bằng nét đứt để phân biệt external
