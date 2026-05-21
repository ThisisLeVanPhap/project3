# Tổng Kết Tính Năng - Chatbot Đa Tenant

## 1. Giới Thiệu Sản Phẩm

Đây là hệ thống chatbot AI đa tenant (đa cửa hàng) được thiết kế cho các cửa hàng nội thất và có thể mở rộng sang các ngành hàng khác. Hệ thống cho phép:

- **Cửa hàng** có chatbot tư vấn riêng, được huấn luyện trên dữ liệu sản phẩm của cửa hàng đó
- **Khách hàng** có thể tương tác với chatbot qua web, Messenger, Telegram
- **Quản trị viên** có thể tạo và cấu hình chatbot cho từng cửa hàng

Hệ thống sử dụng mô hình Claude (Anthropic) làm provider chính, đảm bảo chất lượng trả lời và khả năng xử lý ngôn ngữ tự nhiên.

---

## 2. Các Tính Năng Chính

### 2.1 Chat Tư Vấn Theo Cửa Hàng (Tenant Sales)

**Mô tả**: Khách hàng chat với chatbot của một cửa hàng cụ thể để được tư vấn mua sản phẩm.

**Luồng làm việc**:
1. Khách hàng bắt đầu chat qua web, Messenger hoặc Telegram
2. Chatbot hỏi nhu cầu: loại sản phẩm, kích thước, phong cách, màu sắc, chất liệu, ngân sách
3. Chatbot ghi nhận preferences và gợi ý sản phẩm phù hợp từ kho sản phẩm của cửa hàng
4. Khi khách hàng muốn mua, chatbot thu thập thông tin liên hệ (tên, số điện thoại, địa chỉ)
5. Chatbot tạo yêu cầu mua hàng (purchase request/lead) để nhân viên cửa hàng liên hệ lại

**Điểm nổi bật**:
- Chatbot theo dõi tiến trình tư vấn (stage) từ khám phá → xác định nhu cầu → xem lại → hoàn tất
- Chatbot chỉ tạo đơn hàng khi khách hàng xác nhận (confirm)
- Chatbot không khẳng định chắc chắn về thời gian giao hàng hay chính sách bảo hành (chuyển cho nhân viên xác nhận)

**Kênh hỗ trợ**:
- Web chat (trang quản trị)
- Messenger (Facebook)
- Telegram

---

### 2.2 Chat Tư Vấn/So Sánh Chung (General Compare)

**Mô tả**: Người dùng có thể hỏi về sản phẩm, so sánh các sản phẩm mà không cần gắn với một cửa hàng cụ thể.

**Luồng làm việc**:
1. Người dùng nhập câu hỏi so sánh (ví dụ: "So sánh 3 sofa theo giá, chất liệu, kích thước")
2. Chatbot tìm kiếm sản phẩm phù hợp trong dữ liệu có sẵn
3. Chatbot trả về bảng so sánh với các tiêu chí được hỏi
4. Nếu thiếu thông tin cho một sản phẩm, chatbot ghi rõ "chưa có dữ liệu" thay vì bịa thông tin

**Điểm nổi bật**:
- So sánh trung lập, dựa trên dữ liệu thực tế
- Không bịa thông tin sản phẩm
- Không tạo đơn hàng trong chế độ so sánh chung
- Hỗ trợ so sánh theo nhiều tiêu chí: giá, chất liệu, kích thước, phong cách

**URL truy cập**: `http://SERVER_IP:8080/chat/` hoặc `http://SERVER_IP:8080/general-chat/`

---

### 2.3 Chat Khảo Giá (Market Price)

**Mô tả**: Người dùng hỏi về giá thị trường của sản phẩm để tham khảo trước khi mua.

**Luồng làm việc**:
1. Người dùng nhập câu hỏi về giá (ví dụ: "Sofa SFG041 giá 14 triệu có cao không?")
2. Chatbot tra cứu khoảng giá từ nguồn dữ liệu giá
3. Chatbot trả về khoảng giá tham khảo và nhận xét (cao/thấp/bình thường)
4. Nếu không có đủ dữ liệu giá, chatbot nói rõ "chưa có đủ dữ liệu" thay vì đưa ra con số giả định

**Điểm nổi bật**:
- Cung cấp khoảng giá tham khảo dựa trên dữ liệu
- Cảnh báo khi dữ liệu là mock/demo (chưa phải giá thị trường thật)
- Không khẳng định tuyệt đối về giá thị trường khi chưa đủ nguồn
- Không tạo đơn hàng trong chế độ khảo giá

**URL truy cập**: `http://SERVER_IP:8080/price-check/`

---

### 2.4 Quản Trị Chatbot và Provider

**Mô tả**: Quản trị viên có thể tạo, chỉnh sửa và cấu hình chatbot cho từng cửa hàng.

**Chức năng**:
- Tạo mới chatbot với các thông tin: tên, mô tả, cửa hàng liên kết
- Chọn provider cho chatbot:
  - **Claude**: Sử dụng Claude API (provider chính, chất lượng cao)
  - **Local**: Sử dụng mô hình local Qwen (fallback, yêu cầu GPU hoặc CPU mạnh)
- Xem lịch sử conversation của khách hàng
- Xem và xử lý các lead (yêu cầu mua hàng)

**Lưu ý**:
- Claude là provider chính, được khuyến nghị cho môi trường production
- Cấu hình Claude được quản lý ở cấp độ hệ thống (không nhập API key cho từng chatbot)
- Local model chỉ nên dùng cho mục đích test/development

---

### 2.5 Bảo Mật Dữ Liệu Lead

**Mô tả**: Hệ thống đảm bảo không tạo lead/yêu cầu mua hàng sai ngữ cảnh.

**Quy tắc**:
- Chế độ `general_compare` (so sánh chung): KHÔNG tạo purchase request
- Chế độ `market_price` (khảo giá): KHÔNG tạo purchase request
- Chế độ `tenant_sales` (tư vấn cửa hàng): Chỉ tạo purchase request khi:
  - Khách hàng đã ở stage `close` (giai đoạn hoàn tất)
  - Khách hàng gửi intent `confirm` (xác nhận mua)
  - Đã thu thập đủ thông tin liên hệ

**Lợi ích**:
- Tránh spam lead không thực sự muốn mua
- Nhân viên cửa hàng chỉ liên hệ với khách hàng có ý định mua thực sự
- Dữ liệu lead có chất lượng cao hơn

---

### 2.6 Triển Khai Docker và VPS

**Mô tả**: Hệ thống được thiết kế để dễ dàng triển khai trên VPS CPU-only, không yêu cầu GPU.

**Cấu hình VPS khuyến nghị**:
- CPU: 4 vCPU
- RAM: 8GB
- Storage: 80GB SSD
- GPU: KHÔNG yêu cầu (Claude API được gọi qua HTTP)

**Quy trình deploy**:
1. Cài Docker và Docker Compose trên VPS Ubuntu
2. Clone repository
3. Tạo file `.env` từ `.env.example` và điền API key
4. Chạy `docker compose up -d --build`
5. Hệ thống khởi động trong < 5 phút

**Lợi ích**:
- Chi phí thấp (không cần GPU expensive)
- Startup nhanh (không download/load mô hình local)
- Dễ dàng backup/restore qua Docker volumes

---

## 3. Luồng Người Dùng Điển Hình

### 3.1 Khách Hàng Muốn Mua Sofa Qua Messenger

1. Khách nhắn tin cho Fanpage cửa hàng trên Messenger
2. Chatbot chào và hỏi: "Chào bạn, mình có thể giúp gì cho bạn hôm nay?"
3. Khách: "Tôi muốn mua sofa cho phòng khách 40m2"
4. Chatbot: "Bạn thích phong cách nào: hiện đại, cổ điển, Scandinavian, Industrial?"
5. Khách: "Phong cách hiện đại, màu be, ngân sách 15-20 triệu"
6. Chatbot ghi nhận preferences và gợi ý sản phẩm phù hợp
7. Chatbot: "Bạn có muốn tạo đơn hàng không? Mình cần tên và số điện thoại để liên hệ."
8. Khách: "Tên Nguyễn Văn A, số 0901234567"
9. Chatbot: "Cảm ơn bạn. Bạn có confirm tạo đơn hàng sofa [chi tiết sản phẩm] không? Reply CONFIRM để xác nhận."
10. Khách: "CONFIRM"
11. Chatbot: "Đơn hàng đã được tạo. Nhân viên sẽ liên hệ sớm!"

### 3.2 Người Dùng Muốn So Sánh Sản Phẩm

1. Truy cập `http://SERVER_IP:8080/chat/`
2. Nhập: "So sánh sofa SFG041, SFG040, SFG039 theo giá và chất liệu"
3. Chatbot trả về bảng so sánh:
   | Sản phẩm | Giá | Chất liệu |
   |----------|-----|-----------|
   | SFG041 | chưa có dữ liệu | gỗ sồi |
   | SFG040 | chưa có dữ liệu | gỗ công nghiệp |
   | SFG039 | chưa có dữ liệu | gỗ tự nhiên |
4. Chatbot: "Hiện tại chưa có thông tin giá cho các sản phẩm này. Bạn có thể liên hệ cửa hàng để được báo giá chi tiết."

### 3.3 Người Dùng Muốn Khảo Giá

1. Truy cập `http://SERVER_IP:8080/price-check/`
2. Nhập: "Sofa SFG041 giá 14 triệu có cao không?"
3. Chatbot tra cứu và trả về:
   - Khoảng giá tham khảo: 12-16 triệu VND (nếu có dữ liệu)
   - Nhận xét: "Mức giá 14 triệu đang trong khoảng tham khảo bình thường"
   - Cảnh báo: "Dữ liệu hiện tại là mock/demo, không phải giá thị trường xác nhận"

---

## 4. Giới Hạn Hiện Tại

### 4.1 Dữ Liệu Sản Phẩm Còn Hạn Chế

- Số lượng sản phẩm trong kho dữ liệu chưa nhiều
- Một số trường thông tin (giá, kích thước, warranty) có thể chưa đầy đủ
- Chatbot sẽ ghi rõ "chưa có dữ liệu" thay vì bịa thông tin

**Khắc phục**: Bổ sung dữ liệu sản phẩm từ cửa hàng thật, tích hợp với hệ thống ERP/CRM của cửa hàng.

### 4.2 Market Price Chưa Phải Giá Thị Trường Tuyệt Đối

- Hiện tại đang dùng dữ liệu mock/demo cho một số trường hợp
- Chưa tích hợp đầy đủ external price provider từ nhiều nguồn
- Chatbot sẽ cảnh báo khi dùng mock data

**Khắc phục**: Tích hợp API giá từ các sàn thương mại điện tử, khảo sát giá thị trường định kỳ.

### 4.3 Qwen Fallback Không Phải Đường Demo Chính

- Qwen local model chỉ được dùng khi Claude API không khả dụng
- Fallback này yêu cầu GPU hoặc CPU mạnh, startup chậm
- Không khuyến khích dùng cho demo production

**Khắc phục**: Tập trung vào Claude API làm provider chính, xem xét các model cloud khác như backup.

### 4.4 Tích Hợp Messenger/Telegram Cần Cấu Hình

- Cần tạo Facebook App và Telegram Bot để webhook hoạt động
- Webhook URL cần HTTPS cho production (có thể dùng Caddy/Nginx reverse proxy)

**Khắc phục**: Cung cấp hướng dẫn chi tiết từng bước cấu hình Messenger/Telegram.

---

## 5. Điểm Đã Verify

### 5.1 Chức Năng Chính

| Tính năng | Status | Ghi chú |
|-----------|--------|---------|
| Chat tư vấn cửa hàng (tenant_sales) | ✅ Verified | Stage flow, lead capture, purchase request |
| So sánh sản phẩm (general_compare) | ✅ Verified | Không bịa data, trung lập |
| Khảo giá (market_price) | ✅ Verified | Cảnh báo khi thiếu data |
| Không tạo lead sai mode | ✅ Verified | general_compare/market_price không tạo purchase request |
| Claude API provider | ✅ Verified | model=claude-sonnet-4-6 |

### 5.2 Triển Khai

| Thành phần | Status | Ghi chú |
|------------|--------|---------|
| Docker Compose startup | ✅ Verified | postgres, chatbot-api, app |
| Chatbot-api Claude-only | ✅ Verified | Không load Qwen khi FALLBACK_TO_LOCAL_ENABLED=false |
| Flyway database migration | ✅ Verified | V26 applied successfully |
| VPS CPU-only deployment | ✅ Verified | Không cần GPU, startup < 5 phút |

### 5.3 Test Coverage

| Loại test | Kết quả | Ghi chú |
|-----------|---------|---------|
| Python unit tests | 11/11 passed | test_server_rag_stub.py, test_market_data_providers.py |
| Direct Claude API test | ✅ Passed | market_price, general_compare |
| Environment config | ✅ Verified | has_key=true, fallback_to_local=false |

---

## 6. Hướng Phát Triển Tương Lai

### 6.1 Mở Rộng Dữ Liệu
- Tích hợp với hệ thống quản lý sản phẩm (PIM) của cửa hàng
- Import dữ liệu sản phẩm từ Excel/CSV
- Tự động đồng bộ tồn kho, giá cả

### 6.2 Nâng Cao Khả Năng Trả Lời
- Tích hợp external price provider từ nhiều nguồn
- Thêm khả năng trả lời bằng hình ảnh (visual search)
- Personalization theo lịch sử mua hàng

### 6.3 Cải Thiện Trải Nghiệm
- Multi-language support (Anh, Việt, Trung)
- Voice chat qua Messenger/Telegram
- Tích hợp thanh toán trực tuyến

### 6.4 Analytics và Reporting
- Dashboard cho cửa hàng: số lead, conversion rate
- Phân tích preferences khách hàng
- A/B testing cho các chiến dịch marketing

---

## 7. Thông Tin Kỹ Thuật (Tóm Tắt)

| Thành phần | Công nghệ |
|------------|-----------|
| Backend | Java 21, Spring Boot |
| AI/Chatbot | Python, FastAPI, Claude API |
| Database | PostgreSQL |
| Deployment | Docker, Docker Compose |
| Provider chính | Claude (Anthropic) |
| Model | claude-sonnet-4-6 |

---

**Tài liệu này được tạo để phục vụ việc viết báo cáo đồ án tốt nghiệp.**

**Ngày tạo**: 2026-05-20
**Phiên bản**: 1.0
