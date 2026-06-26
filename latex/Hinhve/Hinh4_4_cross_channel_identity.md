# Hình 4.4 — Nhận diện khách hàng liên kênh

## Mục tiêu hình

Cho người đọc thấy hệ thống tiếp nhận khách hàng từ Messenger và Telegram nhưng không gộp khách hàng tùy tiện. Việc liên kết về một hồ sơ khách hàng chỉ xảy ra khi có đủ thông tin nhận diện đáng tin cậy, và luôn nằm trong phạm vi của một cửa hàng.

## Sơ đồ luồng (dọc — Top to Bottom)

```
              ┌──────────────┐    ┌──────────────┐
              │  Messenger   │    │  Telegram    │
              └──────┬───────┘    └──────┬───────┘
                     │                   │
                     └─────────┬─────────┘
                               │
                               ▼
                  ┌──────────────────────────────────────┐
                  │  Nhận định danh theo từng kênh       │
                  └──────────────────┬───────────────────┘
                                     │
                                     ▼
                  ┌──────────────────────────────────────┐
                  │  Chuẩn hóa số điện thoại / email     │
                  │  nếu có                               │
                  └──────────────────┬───────────────────┘
                                     │
                                     ▼
                  ┌──────────────────────────────────────┐
                  │  Liên kết về hồ sơ khách hàng        │
                  │  trong cửa hàng                       │
                  └──────────────────┬───────────────────┘
                                     │
                                     ▼
                  ┌──────────────────────────────────────┐
                  │  Gắn với hội thoại, lead,            │
                  │  yêu cầu mua hàng                    │
                  └──────────────────────────────────────┘
```

## Cách vẽ (draw.io)

### Layout

- Hướng: Dọc (TB)
- Tầng trên cùng là hai khối kênh đặt cạnh nhau, các tầng dưới là một khối ở giữa

### Các khối

#### Tầng 1: Kênh truy cập (2 khối ngang)

| Cột trái | Cột phải |
|----------|----------|
| **Messenger** | **Telegram** |

#### Tầng 2 đến tầng 5 (mỗi tầng 1 khối, đặt giữa)

| Khối | Nhãn |
|------|------|
| 2 | **Nhận định danh theo từng kênh** |
| 3 | **Chuẩn hóa số điện thoại / email nếu có** |
| 4 | **Liên kết về hồ sơ khách hàng trong cửa hàng** |
| 5 | **Gắn với hội thoại, lead, yêu cầu mua hàng** |

### Các đường nối

| Từ | Đến | Nhãn |
|----|-----|------|
| Messenger | Nhận định danh theo từng kênh | (không nhãn) |
| Telegram | Nhận định danh theo từng kênh | (không nhãn) |
| Nhận định danh theo từng kênh | Chuẩn hóa số điện thoại / email nếu có | (không nhãn) |
| Chuẩn hóa số điện thoại / email nếu có | Liên kết về hồ sơ khách hàng trong cửa hàng | (không nhãn) |
| Liên kết về hồ sơ khách hàng trong cửa hàng | Gắn với hội thoại, lead, yêu cầu mua hàng | (không nhãn) |

### Ghi chú

- Hai kênh có cách định danh khác nhau, nhưng đi qua cùng một bước nhận định danh để hệ thống xử lý đồng nhất
- Bước chuẩn hóa số điện thoại / email là điều kiện cần để có thể liên kết hai kênh về cùng một hồ sơ
- Phạm vi liên kết luôn nằm trong một cửa hàng — cùng số điện thoại nhưng ở hai cửa hàng khác nhau vẫn là hai hồ sơ tách biệt
- Lead và yêu cầu mua hàng phát sinh trong hội thoại sẽ được gắn vào hồ sơ khách hàng tương ứng
