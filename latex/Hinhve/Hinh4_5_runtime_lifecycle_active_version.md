# Hình 4.5 - Vòng đời runtime chatbot theo tenant sau publish KB

## Mô tả

Hình vẽ sequence các bước khi publish KB version mới: Publish → Cập nhật activeKbVersionId → Evict runtime → Chat request spawn runtime mới.

## Sơ đồ (dọc - Top to Bottom, đánh số bước)

```
                    ┌──────────────────────┐
                    │  Publish KB Version  │
                    └──────────┬───────────┘
                               │ 1. Publish
                               ▼
                    ┌──────────────────────┐
                    │  Cập nhật            │
                    │  activeKbVersionId   │──────5. desired──┐
                    │  trên tenant         │                  │
                    └──────────┬───────────┘                  │
                               │ 2.                           │
                               ▼                              ▼
                    ┌──────────────────────┐          ┌──────────────┐
                    │  Evict Runtime       │          │  Runtime     │
                    │                      │          │  Status      │
                    └──────────┬───────────┘          │  (desired,   │
                               │ 3.                    │   running,   │
                               ▼                      │   in_sync)   │
                    ┌──────────────────────┐          └──────────────┘
                    │  Runtime cũ bị xoá   │               ▲
                    │  khỏi bộ nhớ         │               │
                    │  (running rỗng,      │────4. Sync────┘
                    │   in_sync = false)   │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┘
          │ 6. Chat request → Spawn runtime mới
          ▼
┌──────────────────────┐
│  Chat Request        │
│  (người dùng gửi     │
│   tin nhắn)          │
└──────────────────────┘
```

## Cách vẽ (draw.io)

### Layout
- Hướng: Dọc (TB)
- Các bước đánh số 1→6

### Các khối

| Khối | Nhãn | Ghi chú |
|------|------|---------|
| 1 | **Publish KB Version** | Hành động: admin publish version mới |
| 2 | **Cập nhật activeKbVersionId** | Backend cập nhật trường activeKbVersionId trên tenant |
| 3 | **Evict Runtime** | Backend xoá runtime tenant khỏi bộ nhớ |
| 4 | **Chat Request** (người dùng gửi tin nhắn) | Kích hoạt spawn runtime mới |
| Phụ | **Runtime Status** (database) | Lưu trạng thái desired, running, in_sync |

### Các đường nối (đánh số)

| # | Từ | Đến | Nhãn |
|---|-----|-----|------|
| 1 | Publish KB Version | Cập nhật activeKbVersionId | 1 |
| 2 | Cập nhật activeKbVersionId | Evict Runtime | 2 |
| 3 | Evict Runtime | Runtime cũ bị xoá | 3 |
| 4 | Runtime cũ bị xoá | Runtime Status | 4. Sync |
| 5 | Cập nhật activeKbVersionId | Runtime Status | 5. desired (cập nhật desired) |
| 6 | Chat Request | Evict Runtime (vòng xuống) | 6. Spawn |

### Ghi chú
- Trước publish: Runtime Status có desired = version cũ, running = version cũ, in_sync = true
- Sau evict: desired = version mới, running = rỗng, in_sync = false
- Sau spawn: desired = version mới, running = version mới, in_sync = true
