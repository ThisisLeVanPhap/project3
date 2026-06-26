# Hình 4.7 - Nhận diện khách hàng liên kênh Web, Messenger và Telegram

## Mô tả

Hình vẽ cơ chế nhận diện khách hàng qua nhiều kênh. Mỗi kênh có external identity riêng, được CustomerIdentityService tiếp nhận, ghi vào customer_identities và merge vào unified_customers nếu có phone/email.

## Sơ đồ (dọc - Top to Bottom, 4 tầng)

```
  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
  │  Web Chat        │    │  Messenger       │    │  Telegram        │
  │  session_id      │    │  pageId +        │    │  chatId /        │
  │                  │    │  senderId        │    │  userId          │
  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
           │                      │                       │
           │  Tìm/tạo             │  Tìm/tạo              │  Tìm/tạo
           ▼                      ▼                       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                    CustomerIdentityService                      │
  │  - Tìm hoặc tạo identity theo tenant, channel, external_id     │
  │  - Chuẩn hóa phone/email nếu có                                │
  └──────────┬──────────────────────────────────────┬──────────────┘
             │                                      │
             │  Ghi identity                        │  Merge nếu có
             │                                      │  phone/email
             ▼                                      ▼
  ┌──────────────────────┐              ┌──────────────────────┐
  │  customer_identities │              │  unified_customers   │
  │  (database)          │              │  (database)          │
  │  tenant_id, channel, │              │  tenant_id,          │
  │  external_id         │              │  phone/email         │
  └──────────────────────┘              └──────────┬───────────┘
                                                   │
                                                   │ Liên kết hội thoại
                                                   ▼
                                          ┌──────────────────────┐
                                          │  conversations       │
                                          │  (database)          │
                                          │  unified_customer_id │
                                          └──────────────────────┘
```

## Cách vẽ (draw.io)

### Layout
- Hướng: Dọc (TB)
- 4 tầng: Channels → Service → Database records

### Các khối

#### Tầng 1: Kênh truy cập (3 khối ngang)

| Cột trái | Cột giữa | Cột phải |
|----------|----------|----------|
| **Web Chat** — session_id | **Messenger** — pageId + senderId | **Telegram** — chatId / userId |

#### Tầng 2: Service (1 khối rộng)

| Nhãn |
|------|
| **CustomerIdentityService** — Tìm hoặc tạo identity theo tenant, channel, external_id; Chuẩn hóa phone/email nếu có |

#### Tầng 3: Database records (2 khối cạnh nhau)

| Cột trái | Cột phải |
|----------|----------|
| **customer_identities** — tenant_id, channel, external_id | **unified_customers** — tenant_id, phone/email |

#### Tầng 4: Kết quả liên kết (1 khối)

| Nhãn |
|------|
| **conversations** — unified_customer_id |

### Các đường nối

| Từ | Đến | Nhãn |
|----|-----|------|
| Web Chat | CustomerIdentityService | Tìm/tạo |
| Messenger | CustomerIdentityService | Tìm/tạo |
| Telegram | CustomerIdentityService | Tìm/tạo |
| CustomerIdentityService | customer_identities | Ghi identity |
| CustomerIdentityService | unified_customers | Merge nếu có phone/email |
| unified_customers | conversations | Liên kết hội thoại |

### Ghi chú
- Không merge chỉ dựa trên displayName
- Tenant isolation: cùng phone/email nhưng khác tenant không bị merge
- Mỗi UnifiedCustomer thuộc phạm vi một tenant
