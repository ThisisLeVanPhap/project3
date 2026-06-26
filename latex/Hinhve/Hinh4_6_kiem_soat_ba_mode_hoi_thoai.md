# Hình 4.6 - Kiểm soát ba chế độ hội thoại

## Mô tả

Hình vẽ ba chế độ hội thoại (tenant_sales, general_compare, market_price) và sự khác nhau về nguồn dữ liệu được phép truy xuất và tác động nghiệp vụ được phép tạo.

## Sơ đồ (dọc - Top to Bottom)

```
                         ┌──────────────────────────┐
                         │    Tin nhắn từ người dùng │
                         └────────────┬─────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
   ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
   │  tenant_sales       │ │  general_compare    │ │  market_price       │
   │  Bán hàng theo      │ │  Tư vấn chung      │ │  Tham khảo giá      │
   │  cửa hàng           │ │  / so sánh          │ │  thị trường         │
   └──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘
              │                       │                       │
              ▼                       ▼                       ▼
   ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
   │  Nguồn dữ liệu:     │ │  Nguồn dữ liệu:     │ │  Nguồn dữ liệu:     │
   │  Tenant-bound KB   │ │  General Corpus     │ │  Dữ liệu quan sát  │
   │  Active Version     │ │                     │ │  / có cấu trúc      │
   └──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘
              │                       │                       │
              ▼                       ▼                       ▼
   ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
   │  Tác động NV:       │ │  Tác động NV:       │ │  Tác động NV:       │
   │  Lead / Purchase    │ │  Không tạo          │ │  Không tạo          │
   │  Request            │ │                     │ │                     │
   └─────────────────────┘ └─────────────────────┘ └─────────────────────┘
```

## Cách vẽ (draw.io)

### Layout
- Hướng: Dọc (TB), chia 3 luồng song song

### Các khối

Hàng 1: 1 khối trung tâm

| Nhãn |
|------|
| **Tin nhắn từ người dùng** |

Hàng 2: 3 khối cạnh nhau

| Cột trái | Cột giữa | Cột phải |
|----------|----------|----------|
| **tenant_sales** — Bán hàng theo cửa hàng | **general_compare** — Tư vấn chung / so sánh | **market_price** — Tham khảo giá thị trường |

Hàng 3: 3 khối — Nguồn dữ liệu

| Cột trái | Cột giữa | Cột phải |
|----------|----------|----------|
| Tenant-bound KB / Active Version | General Corpus | Dữ liệu quan sát / có cấu trúc |

Hàng 4: 3 khối — Tác động nghiệp vụ

| Cột trái | Cột giữa | Cột phải |
|----------|----------|----------|
| Lead / Purchase Request | Không tạo | Không tạo |

### Các đường nối

| Từ | Đến |
|----|-----|
| Tin nhắn | tenant_sales |
| Tin nhắn | general_compare |
| Tin nhắn | market_price |
| tenant_sales | Tenant-bound KB |
| general_compare | General Corpus |
| market_price | Dữ liệu quan sát |
| Tenant-bound KB | Lead / Purchase Request |
| General Corpus | Không tạo |
| Dữ liệu quan sát | Không tạo |

### Ghi chú
- Cả 3 mode đều do hệ thống tự xây dựng
- tenant_sales là mode đầy đủ nhất (có tenant-bound KB + có tác động nghiệp vụ)
- general_compare và market_price đang ở mức thiết kế, chưa có implementation đầy đủ
