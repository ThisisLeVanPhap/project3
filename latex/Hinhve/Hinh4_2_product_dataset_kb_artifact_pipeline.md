# Hình 4.2 — Luồng dữ liệu sản phẩm và knowledge base

## Mục tiêu hình

Cho người đọc thấy dữ liệu sản phẩm không đi thẳng từ nguồn vào chatbot, mà phải qua các bước chuẩn hóa, kiểm tra chất lượng, đóng gói và kích hoạt cho cửa hàng trước khi chatbot dùng để trả lời.

## Sơ đồ luồng (ngang — Left to Right)

```
  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
  │  Nguồn         │───>│  Thu thập      │───>│  Chuẩn hóa     │
  │  sản phẩm      │    │  / nhập        │    │  dữ liệu       │
  │                │    │  dữ liệu       │    │                │
  └────────────────┘    └────────────────┘    └────────┬───────┘
                                                       │
                                                       ▼
  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
  │  Chatbot       │<───│  Kích hoạt     │<───│  Kiểm tra      │
  │  sử dụng khi   │    │  cho cửa hàng  │    │  chất lượng    │
  │  trả lời       │    │                │    │  dữ liệu       │
  └────────────────┘    └────────┬───────┘    └────────┬───────┘
                                 ▲                     │
                                 │                     ▼
                        ┌────────┴───────┐    ┌────────────────┐
                        │  Tạo artifact  │<───│  Tạo bộ dữ     │
                        │  knowledge     │    │  liệu sản phẩm │
                        │  base          │    │                │
                        └────────────────┘    └────────────────┘
```

## Cách vẽ (draw.io)

### Layout

- Hướng: Trái → Phải, sau đó xuống hàng và quay ngược lại (zigzag)
- 8 khối hình chữ nhật bo góc, kích thước đều nhau
- Toàn bộ luồng nằm gọn trong một khung "Hệ thống"

### Các khối

| Thứ tự | Nhãn | Vai trò trong hệ thống |
|--------|------|------------------------|
| 1 | **Nguồn sản phẩm** | Đầu vào: website cửa hàng, danh mục sản phẩm |
| 2 | **Thu thập / nhập dữ liệu** | Lấy dữ liệu sản phẩm về hệ thống |
| 3 | **Chuẩn hóa dữ liệu** | Đưa dữ liệu về cùng một dạng để xử lý tiếp |
| 4 | **Kiểm tra chất lượng dữ liệu** | Phát hiện lỗi mã hóa, dữ liệu trùng, dữ liệu thiếu |
| 5 | **Tạo bộ dữ liệu sản phẩm** | Đăng ký một bộ dữ liệu chính thức để dùng được |
| 6 | **Tạo artifact knowledge base** | Đóng gói dữ liệu thành dạng chatbot có thể tra cứu |
| 7 | **Kích hoạt cho cửa hàng** | Gán artifact đã tạo cho một cửa hàng cụ thể |
| 8 | **Chatbot sử dụng khi trả lời** | Khi người dùng hỏi, chatbot tra cứu trên artifact đã được kích hoạt |

### Các đường nối

| Từ | Đến | Nhãn |
|----|-----|------|
| Nguồn sản phẩm | Thu thập / nhập dữ liệu | (không nhãn) |
| Thu thập / nhập dữ liệu | Chuẩn hóa dữ liệu | (không nhãn) |
| Chuẩn hóa dữ liệu | Kiểm tra chất lượng dữ liệu | (không nhãn) |
| Kiểm tra chất lượng dữ liệu | Tạo bộ dữ liệu sản phẩm | Nếu đạt |
| Tạo bộ dữ liệu sản phẩm | Tạo artifact knowledge base | (không nhãn) |
| Tạo artifact knowledge base | Kích hoạt cho cửa hàng | (không nhãn) |
| Kích hoạt cho cửa hàng | Chatbot sử dụng khi trả lời | (không nhãn) |

### Ghi chú

- Toàn bộ các bước trong hình đều thuộc hệ thống tự xây dựng
- Bước **Kiểm tra chất lượng dữ liệu** đóng vai trò chặn dữ liệu lỗi không đi tiếp
- Bước **Kích hoạt cho cửa hàng** là điểm tách rời giữa "đã có dữ liệu" và "cửa hàng đang dùng dữ liệu nào"
