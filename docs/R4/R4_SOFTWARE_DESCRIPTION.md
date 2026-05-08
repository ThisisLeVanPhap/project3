# R.4 Mô tả phần mềm

## 1. Tên phần mềm

Hệ thống chatbot tư vấn và gợi ý sản phẩm nội thất sử dụng truy xuất tri thức và mô hình ngôn ngữ lớn.

## 2. Mục tiêu

Phần mềm hỗ trợ người dùng tìm kiếm, hỏi đáp, so sánh tham chiếu và nhận gợi ý sản phẩm nội thất dựa trên dữ liệu sản phẩm của từng tenant. Hệ thống kết hợp backend quản trị đa tenant, service AI/RAG và giao diện web để phục vụ demo, kiểm thử và vận hành nghiệp vụ tư vấn.

Các mục tiêu chính:

- Quản lý tenant, tài khoản, chatbot và dữ liệu sản phẩm nội thất.
- Xử lý dữ liệu sản phẩm thành knowledge base phục vụ truy xuất tri thức.
- Cung cấp chatbot hỏi đáp thông tin sản phẩm theo ngữ cảnh hội thoại.
- Gợi ý sản phẩm theo nhu cầu người dùng như loại sản phẩm, không gian, ngân sách, chất liệu và phong cách.
- Tích hợp mô hình ngôn ngữ lớn thông qua API hoặc runtime cục bộ.
- Cung cấp giao diện web và backend API cho sử dụng, quản trị, demo và kiểm thử.

## 3. Người dùng

| Nhóm người dùng | Mục đích sử dụng |
| --- | --- |
| Người dùng cuối | Hỏi đáp sản phẩm, nhận tư vấn lựa chọn và gửi nhu cầu mua hàng |
| Tenant admin | Quản trị chatbot, nguồn tri thức, hội thoại, lead và yêu cầu mua hàng của tenant |
| Tenant member | Xử lý hội thoại, phản hồi lead và cập nhật yêu cầu mua hàng |
| Platform admin | Quản lý tenant, tài khoản tenant, thống kê và vận hành runtime |
| Người kiểm thử/demo | Thực hiện test cases, kiểm tra API và đánh giá chất lượng truy xuất/câu trả lời |

## 4. Chức năng chính

| Nhóm chức năng | Mô tả |
| --- | --- |
| Quản lý tenant | Tạo, cập nhật, kích hoạt và quản lý thông tin tenant |
| Quản lý tài khoản | Đăng nhập, phân quyền platform admin, tenant admin và tenant member |
| Quản lý chatbot | Cấu hình chatbot theo tenant, API key, thư mục KB và runtime |
| Quản lý dữ liệu sản phẩm | Lưu, nhập và chuẩn hóa nguồn dữ liệu sản phẩm nội thất |
| Xử lý knowledge base | Tạo tài liệu chuẩn hóa, chunks và chỉ mục phục vụ retrieval |
| Retrieval/RAG | Tìm kiếm đoạn tri thức liên quan và đưa vào ngữ cảnh trả lời |
| Chatbot hỏi đáp | Trả lời câu hỏi về sản phẩm, giá, chất liệu, kích thước, công dụng và chính sách liên quan |
| Gợi ý sản phẩm | Đề xuất sản phẩm phù hợp theo nhu cầu người dùng |
| Tham chiếu thông tin sản phẩm | Đối chiếu tên sản phẩm, mức giá, thuộc tính và nguồn dữ liệu liên quan |
| Quản lý hội thoại | Lưu session, tin nhắn, lead và trạng thái xử lý |
| Yêu cầu mua hàng | Ghi nhận nhu cầu, phân công xử lý, cập nhật trạng thái và phản hồi |
| Tích hợp kênh | Kết nối Messenger và Telegram thông qua webhook |
| Kiểm thử và đánh giá | Cung cấp test cases, script chạy thử và kết quả thử nghiệm retrieval/API |

## 5. Kiến trúc phần mềm

Hệ thống gồm các lớp chính:

- Frontend web: giao diện đăng nhập, quản trị, web chat, general chat và quản lý yêu cầu mua hàng.
- Backend service: Spring Boot cung cấp API nghiệp vụ, phân quyền, quản lý tenant/chatbot, hội thoại và tích hợp kênh.
- AI/RAG service: Python FastAPI/runtime cục bộ xử lý retrieval, tạo ngữ cảnh và gọi mô hình ngôn ngữ lớn.
- Database: PostgreSQL lưu dữ liệu tenant, người dùng, chatbot, hội thoại, lead và yêu cầu mua hàng.
- Knowledge base: thư mục dữ liệu sản phẩm, tài liệu chuẩn hóa, chunks và chỉ mục truy xuất.
- Integration layer: API gọi runtime cục bộ hoặc provider mô hình ngôn ngữ lớn, webhook Messenger/Telegram.

## 6. Dữ liệu đầu vào

| Dữ liệu đầu vào | Nguồn | Mục đích |
| --- | --- | --- |
| Dữ liệu sản phẩm nội thất | URL nguồn, file KB, dữ liệu chuẩn hóa | Cung cấp tri thức cho chatbot |
| Câu hỏi người dùng | Web chat, general chat, Messenger, Telegram, API | Truy vấn thông tin và yêu cầu tư vấn |
| Tiêu chí gợi ý | Nội dung chat hoặc request API | Lọc và chọn sản phẩm phù hợp |
| Cấu hình tenant/chatbot | Giao diện quản trị hoặc API backend | Xác định phạm vi dữ liệu, API key và runtime |
| Test cases | Tài liệu C.3, Postman collection, test source | Kiểm tra chức năng và chất lượng phản hồi |

## 7. Dữ liệu đầu ra

| Dữ liệu đầu ra | Mô tả |
| --- | --- |
| Câu trả lời chatbot | Nội dung trả lời dựa trên dữ liệu sản phẩm và ngữ cảnh truy xuất |
| Danh sách sản phẩm gợi ý | Sản phẩm phù hợp với nhu cầu, ngân sách và tiêu chí người dùng |
| Kết quả truy xuất tri thức | Các đoạn dữ liệu liên quan dùng làm ngữ cảnh trả lời |
| Tham chiếu sản phẩm | Thông tin tên sản phẩm, giá, thuộc tính và nguồn dữ liệu |
| Lịch sử hội thoại | Session, tin nhắn, trạng thái và metadata hội thoại |
| Lead/yêu cầu mua hàng | Thông tin nhu cầu khách hàng và tiến trình xử lý |
| Response API | JSON trả về cho backend, frontend hoặc công cụ kiểm thử |
| Kết quả thử nghiệm | Kết quả test cases và chỉ số retrieval |

## 8. Môi trường sử dụng

| Thành phần | Công nghệ |
| --- | --- |
| Backend | Java 21, Spring Boot, Maven |
| Frontend | Static web UI phục vụ bởi Spring Boot |
| AI/RAG service | Python, FastAPI, Uvicorn |
| Database | PostgreSQL, Flyway migration |
| Container | Docker, Docker Compose |
| Kiểm thử | JUnit/Spring test, Python tests, Postman collection, script đánh giá retrieval |
| Tích hợp ngoài | Messenger webhook, Telegram webhook, API/runtime mô hình ngôn ngữ lớn |
