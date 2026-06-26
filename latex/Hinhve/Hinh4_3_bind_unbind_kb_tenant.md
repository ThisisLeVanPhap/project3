# Hình 4.3 - Luồng bind/unbind KB Artifact với tenant

## Mô tả

Hình vẽ luồng thao tác bind và unbind KB Artifact vào tenant. Thể hiện: Platform Admin gửi yêu cầu → Bind/Unbind Service xử lý → ghi vào TenantKbBinding và TenantKbVersion → evict runtime.

## Sơ đồ luồng (ngang - Left to Right)

```
  ┌────────────────┐
  │  Platform      │
  │  Admin         │
  └───────┬────────┘
          │ Bind / Unbind
          ▼
  ┌──────────────────────────────────────────────┐
  │           Bind / Unbind Service              │
  │  (Spring Boot backend)                       │
  └──────┬─────────────────────┬─────────────────┘
         │                     │
         │ Tạo/cập nhật        │ Tạo version
         ▼                     ▼
  ┌──────────────┐    ┌──────────────┐
  │TenantKb      │    │TenantKb      │
  │Binding       │    │Version       │
  │(database)    │    │(database)    │
  │              │    │trỏ tới       │
  │              │    │artifact_path │
  └──────────────┘    └──────┬───────┘
                             │
                             │ KB dir
                             ▼
                     ┌──────────────┐
                     │  Chatbot     │
                     │  Runtime     │
                     │              │
                     │  (evict nếu  │
                     │   có thay    │
                     │   đổi)       │
                     └──────────────┘
                Bind/Unbind Service ──── Evict runtime ────┘
```

## Cách vẽ (draw.io)

### Layout
- Hướng: Trái → Phải (LR)
- 4 cột: Admin → Service → Database records → Runtime

### Các khối

| Vị trí | Nhãn | Ghi chú |
|--------|------|---------|
| Cột 1 | **Platform Admin** | Người dùng, kích hoạt bind/unbind |
| Cột 2 | **Bind / Unbind Service** | Spring Boot backend xử lý logic bind/unbind |
| Cột 3 (trên) | **TenantKbBinding** (database) | Lưu liên kết tenant ↔ artifact, trạng thái active/inactive |
| Cột 3 (dưới) | **TenantKbVersion** (database) | Lưu version, trỏ tới artifact_path (kb_dir) |
| Cột 4 | **Chatbot Runtime** | FastAPI runtime; bị evict khi có thay đổi binding |

### Các đường nối

| Từ | Đến | Nhãn |
|----|-----|------|
| Platform Admin | Bind / Unbind Service | Bind / Unbind |
| Bind / Unbind Service | TenantKbBinding | Tạo/cập nhật |
| Bind / Unbind Service | TenantKbVersion | Tạo version |
| TenantKbVersion | Chatbot Runtime | KB dir |
| Bind / Unbind Service | Chatbot Runtime | Evict runtime |

### Ghi chú
- Tất cả đều là thành phần do hệ thống tự xây dựng
- Evict runtime = xoá runtime cũ khỏi bộ nhớ để lần chat sau lazy-load runtime mới
