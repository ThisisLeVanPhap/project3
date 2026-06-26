# Hình 4.2 - Luồng offline xây dựng Product Dataset và KB Artifact

## Mô tả

Hình vẽ luồng xử lý offline từ lúc nhập dữ liệu nguồn (URL, sitemap) đến khi tạo ra KB Artifact sẵn sàng để bind vào tenant. Hình thể hiện các bước: crawl/materialize → quality gate → register dataset → build artifact.

## Sơ đồ luồng (ngang - Left to Right)

```
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │  Nguồn dữ liệu│────>│  Crawl &     │────>│  Quality     │
  │  URL / Sitemap│     │  Materialize │     │  Gate        │
  └──────────────┘     └──────────────┘     └──────┬───────┘
                                                   │
                                        ┌──────────┴
                                        │                   
                                        ▼                   
                                  ┌──────────────┐
                                  │  Product     │
                                  │  Dataset     │
                                  │  (registered)│
                                  └──────┬───────┘
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │  Build KB     │
                                  │               │
                                  └──────┬───────┘
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │  KB Artifact  │
                                  │  (file system)│
                                  │          │
                                  │              │
                                  │                 │
                                  └──────────────┘
```

## Cách vẽ (draw.io)

### Layout
- Hướng: Trái → Phải (LR)
- Sắp xếp thành 5 cột dọc

### Các khối

Kéo 6 khối hình chữ nhật bo tròn góc, đặt theo hàng ngang từ trái sang phải:

| Vị trí | Nhãn | Ghi chú |
|--------|------|---------|
| Cột 1 | **Nguồn dữ liệu** (URL / Sitemap) | Khối đầu vào |
| Cột 2 | **Crawl & Materialize** | Xử lý: crawl từ URL, materialize thành file catalog, rag |
| Cột 3 | **Quality Gate** | Kiểm tra chất lượng: manifest count, mojibake, duplicate URL, price coverage... |
| Cột 4 (rẽ nhánh) | **Product Dataset** (registered) | Đăng ký dataset thành ProductDataset trong DB |
| Cột 4 (rẽ nhánh dưới) | **Fail / Warn** | Nếu quality gate không đạt |
| Cột 5 | **Build KB** | Build artifact từ dataset |
| Cột 6 | **KB Artifact** (file system: catalog, rag, manifest) | Kết quả cuối, lưu trên file system |

### Các đường nối

| Từ | Đến | Nhãn | Ghi chú |
|----|-----|------|---------|
| Nguồn dữ liệu | Crawl & Materialize | Import | Mũi tên phải |
| Crawl & Materialize | Quality Gate | (không nhãn) | Mũi tên phải |
| Quality Gate | Product Dataset | Kiểm tra chất lượng | Mũi tên xuống dưới → sang phải |
| Quality Gate | Fail / Warn | Fail / Warn | Mũi tên xuống dưới (rẽ nhánh) |
| Product Dataset | Build KB | Build | Mũi tên phải |
| Build KB | KB Artifact | (không nhãn) | Mũi tên phải |

### Phân biệt
- **Trong hệ thống**: Tất cả các khối đều do hệ thống tự xây dựng
- **Không có external service** ở hình này (toàn bộ pipeline là backend tự làm)
