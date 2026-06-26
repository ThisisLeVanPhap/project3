# Hình 4.3 — Luồng hội thoại và kiểm soát ba chế độ

## Mục tiêu hình

Cho người đọc thấy dù tin nhắn đi vào theo cùng một luồng, hệ thống chọn chế độ hội thoại trước rồi mới quyết định nguồn dữ liệu được dùng và quyền tạo dữ liệu bán hàng. Nhờ đó, chỉ chế độ tư vấn bán hàng mới được phép tạo lead hoặc yêu cầu mua hàng.

## Sơ đồ luồng (dọc — Top to Bottom, có rẽ ba nhánh)

```
                     ┌────────────────────────┐
                     │  Tin nhắn người dùng   │
                     └───────────┬────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │  Xác định cửa hàng, kênh và  │
                  │  phiên hội thoại             │
                  └───────────────┬──────────────┘
                                  │
                                  ▼
                  ┌──────────────────────────────┐
                  │  Xác định chế độ hội thoại   │
                  └─────┬──────────┬─────────┬───┘
                        │          │         │
        ┌───────────────┘          │         └────────────────┐
        ▼                          ▼                          ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Tư vấn bán hàng │    │  So sánh sản     │    │  Tham khảo giá   │
│  theo cửa hàng   │    │  phẩm chung      │    │                  │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Dùng knowledge  │    │  Dùng dữ liệu    │    │  Dùng dữ liệu    │
│  base của cửa    │    │  tham chiếu      │    │  giá / tham      │
│  hàng            │    │  được phép        │    │  chiếu nếu có    │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Truy xuất nội   │    │  Sinh phản hồi   │    │  Sinh phản hồi   │
│  dung liên quan  │    │                  │    │                  │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         ▼                       │                       │
┌──────────────────┐              │                       │
│  Sinh phản hồi   │              │                       │
└────────┬─────────┘              │                       │
         │                       │                       │
         ▼                       │                       │
┌──────────────────┐              │                       │
│  Có thể tạo lead │              │                       │
│  / yêu cầu mua   │    ┌─── Không tạo ───┐    ┌─── Không tạo ───┐
│  hàng nếu đủ     │    │  lead / yêu     │    │  lead / yêu     │
│  điều kiện       │    │  cầu mua hàng   │    │  cầu mua hàng   │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         └───────────────┬───────┴───────────────────────┘
                         ▼
                ┌──────────────────┐
                │  Lưu phản hồi    │
                └────────┬─────────┘
                         ▼
                ┌──────────────────┐
                │  Trả về đúng kênh│
                └──────────────────┘
```

## Cách vẽ (draw.io)

### Layout

- Hướng: Dọc (TB), có một đoạn rẽ ba nhánh ở giữa
- Đầu và cuối luồng là cột giữa, phần giữa hình chia làm ba cột song song

### Các khối

#### Phần đầu (cột giữa)

| Khối | Nhãn |
|------|------|
| 1 | **Tin nhắn người dùng** |
| 2 | **Xác định cửa hàng, kênh và phiên hội thoại** |
| 3 | **Xác định chế độ hội thoại** |

#### Phần giữa: ba nhánh song song

| Cột trái — Tư vấn bán hàng theo cửa hàng | Cột giữa — So sánh sản phẩm chung | Cột phải — Tham khảo giá |
|------------------------------------------|----------------------------------|--------------------------|
| Tư vấn bán hàng theo cửa hàng | So sánh sản phẩm chung | Tham khảo giá |
| Dùng knowledge base của cửa hàng | Dùng dữ liệu tham chiếu được phép | Dùng dữ liệu giá / tham chiếu nếu có |
| Truy xuất nội dung liên quan | (không có bước này) | (không có bước này) |
| Sinh phản hồi | Sinh phản hồi | Sinh phản hồi |
| Có thể tạo lead / yêu cầu mua hàng nếu đủ điều kiện | Không tạo lead / yêu cầu mua hàng | Không tạo lead / yêu cầu mua hàng |

#### Phần cuối (cột giữa)

| Khối | Nhãn |
|------|------|
| Cuối 1 | **Lưu phản hồi** |
| Cuối 2 | **Trả về đúng kênh** |

### Các đường nối

| Từ | Đến | Nhãn |
|----|-----|------|
| Tin nhắn người dùng | Xác định cửa hàng, kênh và phiên hội thoại | (không nhãn) |
| Xác định cửa hàng, kênh và phiên hội thoại | Xác định chế độ hội thoại | (không nhãn) |
| Xác định chế độ hội thoại | Tư vấn bán hàng theo cửa hàng | Bán hàng |
| Xác định chế độ hội thoại | So sánh sản phẩm chung | So sánh chung |
| Xác định chế độ hội thoại | Tham khảo giá | Giá |
| Tư vấn bán hàng theo cửa hàng | Dùng knowledge base của cửa hàng | (không nhãn) |
| Dùng knowledge base của cửa hàng | Truy xuất nội dung liên quan | (không nhãn) |
| Truy xuất nội dung liên quan | Sinh phản hồi (nhánh 1) | (không nhãn) |
| Sinh phản hồi (nhánh 1) | Có thể tạo lead / yêu cầu mua hàng | Đủ điều kiện |
| So sánh sản phẩm chung | Dùng dữ liệu tham chiếu được phép | (không nhãn) |
| Dùng dữ liệu tham chiếu được phép | Sinh phản hồi (nhánh 2) | (không nhãn) |
| Sinh phản hồi (nhánh 2) | Không tạo lead / yêu cầu mua hàng | (không nhãn) |
| Tham khảo giá | Dùng dữ liệu giá / tham chiếu nếu có | (không nhãn) |
| Dùng dữ liệu giá / tham chiếu nếu có | Sinh phản hồi (nhánh 3) | (không nhãn) |
| Sinh phản hồi (nhánh 3) | Không tạo lead / yêu cầu mua hàng | (không nhãn) |
| Có thể tạo lead / yêu cầu mua hàng | Lưu phản hồi | (không nhãn) |
| Không tạo lead / yêu cầu mua hàng (nhánh 2) | Lưu phản hồi | (không nhãn) |
| Không tạo lead / yêu cầu mua hàng (nhánh 3) | Lưu phản hồi | (không nhãn) |
| Lưu phản hồi | Trả về đúng kênh | (không nhãn) |

### Ghi chú

- Toàn bộ ba nhánh đều dùng chung phần xác định cửa hàng, kênh, phiên hội thoại ở đầu và phần lưu phản hồi, trả kênh ở cuối
- Chỉ nhánh **Tư vấn bán hàng theo cửa hàng** mới có bước truy xuất knowledge base và mới được phép tạo lead / yêu cầu mua hàng
- Hai nhánh còn lại có thể trả lời nhưng không tạo dữ liệu bán hàng
- Việc chọn chế độ nằm trước nguồn dữ liệu và trước quyền tạo dữ liệu, nên không có chuyện một câu trả lời "lỡ" tạo lead nhầm chế độ
