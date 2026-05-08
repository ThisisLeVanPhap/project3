# R.4 Đặc tả yêu cầu hệ thống

## 1. Mục đích

Tài liệu này đặc tả yêu cầu chức năng, phi chức năng, dữ liệu và giao diện của hệ thống chatbot tư vấn/gợi ý sản phẩm nội thất sử dụng RAG và tích hợp mô hình ngôn ngữ lớn thông qua API hoặc runtime cục bộ.

## 2. Phạm vi hệ thống

Hệ thống phục vụ quản lý dữ liệu sản phẩm, xử lý tri thức, hỏi đáp, gợi ý sản phẩm, quản trị tenant, quản lý hội thoại, yêu cầu mua hàng và tích hợp kênh chat bên ngoài. Phần tạo câu trả lời được thực hiện qua runtime/API mô hình ngôn ngữ lớn, không thay đổi tham số mô hình.

## 3. Yêu cầu chức năng

| Mã | Yêu cầu | Mô tả | Actor chính |
| --- | --- | --- | --- |
| FR-01 | Đăng nhập và phân quyền | Hệ thống hỗ trợ đăng nhập, đăng xuất, kiểm tra phiên và phân quyền theo platform admin, tenant admin, tenant member | Admin, tenant user |
| FR-02 | Quản lý tenant | Platform admin quản lý thông tin tenant, trạng thái và cấu hình truy cập | Platform admin |
| FR-03 | Quản lý thành viên tenant | Platform admin hoặc người có quyền quản trị quản lý tài khoản tenant admin/member | Platform admin |
| FR-04 | Quản lý chatbot | Tenant admin cấu hình chatbot, API key, thư mục knowledge base và runtime | Tenant admin |
| FR-05 | Quản lý nguồn tri thức | Tenant admin thêm, cập nhật, xóa hoặc xem URL nguồn dữ liệu sản phẩm | Tenant admin |
| FR-06 | Xử lý dữ liệu sản phẩm | Hệ thống chuẩn hóa dữ liệu sản phẩm thành tài liệu, chunks và chỉ mục phục vụ retrieval | Tenant admin, system |
| FR-07 | Rebuild knowledge base | Hệ thống cung cấp thao tác rebuild và trạng thái xử lý knowledge base theo tenant/chatbot | Tenant admin, system |
| FR-08 | Truy xuất tri thức | AI/RAG service truy xuất đoạn dữ liệu liên quan từ knowledge base theo câu hỏi người dùng | Người dùng, system |
| FR-09 | Chat hỏi đáp sản phẩm | Người dùng đặt câu hỏi và nhận câu trả lời dựa trên dữ liệu sản phẩm | Người dùng cuối |
| FR-10 | Gợi ý sản phẩm | Hệ thống tư vấn sản phẩm theo loại sản phẩm, nhu cầu, ngân sách, chất liệu, không gian và phong cách | Người dùng cuối |
| FR-11 | Tham chiếu sản phẩm | Hệ thống hỗ trợ đối chiếu thông tin sản phẩm, giá và thuộc tính khi dữ liệu có thông tin phù hợp | Người dùng cuối |
| FR-12 | Quản lý hội thoại | Backend lưu session, tin nhắn, nguồn kênh và metadata hội thoại | Người dùng cuối, tenant user |
| FR-13 | General chat | Hệ thống cung cấp luồng chat chung phục vụ demo và kiểm thử | Người dùng cuối, người kiểm thử |
| FR-14 | Quản lý lead | Tenant user xem và xử lý lead phát sinh từ hội thoại | Tenant admin, tenant member |
| FR-15 | Quản lý yêu cầu mua hàng | Hệ thống tạo, xem, phân công, cập nhật trạng thái và phản hồi yêu cầu mua hàng | Tenant admin, tenant member |
| FR-16 | Tích hợp Messenger | Hệ thống cấu hình binding và xử lý webhook Messenger | Tenant admin, system |
| FR-17 | Tích hợp Telegram | Hệ thống cấu hình binding và xử lý webhook Telegram | Tenant admin, system |
| FR-18 | Quản trị runtime | Platform admin kiểm tra trạng thái runtime, tác vụ vận hành và thống kê | Platform admin |
| FR-19 | API kiểm thử/demo | Hệ thống cung cấp API phục vụ kiểm thử backend, chat, RAG và quản trị | Người kiểm thử |
| FR-20 | Ghi nhận feedback | Hệ thống nhận feedback cho câu trả lời chatbot để phục vụ đánh giá chất lượng | Người dùng, người kiểm thử |

## 4. Yêu cầu phi chức năng

| Mã | Yêu cầu | Mô tả |
| --- | --- | --- |
| NFR-01 | Tách biệt tenant | Dữ liệu, chatbot, API key và hội thoại được xử lý theo phạm vi tenant |
| NFR-02 | Bảo mật truy cập | API quản trị yêu cầu phiên đăng nhập hoặc API key tùy nhóm endpoint |
| NFR-03 | Không lưu secret trong tài liệu | Tài liệu và mã nguồn mẫu chỉ sử dụng placeholder cho secret, token và mật khẩu |
| NFR-04 | Tính ổn định | Backend, database và runtime AI/RAG có health check hoặc điểm kiểm tra tương đương |
| NFR-05 | Khả năng triển khai | Hệ thống chạy được bằng Docker Compose hoặc theo từng service local |
| NFR-06 | Khả năng quan sát | Log service, trạng thái rebuild KB và trạng thái runtime hỗ trợ khoanh vùng lỗi |
| NFR-07 | Hiệu năng phản hồi | API chat trả phản hồi trong giới hạn phù hợp với runtime mô hình và kích thước knowledge base |
| NFR-08 | Tính mở rộng dữ liệu | Knowledge base tổ chức theo thư mục/tenant để bổ sung nguồn sản phẩm mới |
| NFR-09 | Khả năng kiểm thử | Có test source, Postman collection, bộ câu hỏi kiểm thử và tài liệu kết quả thử nghiệm |
| NFR-10 | Tính nhất quán API | Request/response JSON tuân theo convention của controller, DTO và service hiện có |
| NFR-11 | Khả năng phục hồi lỗi | Hệ thống trả lỗi rõ ràng khi request sai, thiếu quyền, runtime lỗi hoặc dữ liệu đầu vào không hợp lệ |
| NFR-12 | Dễ bảo trì | Kiến trúc tách backend, AI/RAG service, database và frontend để dễ thay đổi theo module |

## 5. Yêu cầu dữ liệu

| Mã | Yêu cầu | Mô tả |
| --- | --- | --- |
| DR-01 | Dữ liệu sản phẩm | Lưu tên, mô tả, thuộc tính, giá, URL nguồn và metadata khi có |
| DR-02 | Dữ liệu knowledge base | Lưu tài liệu chuẩn hóa, chunks, chỉ mục và metadata nguồn |
| DR-03 | Dữ liệu hội thoại | Lưu conversation, message, kênh chat, tenant và thời gian |
| DR-04 | Dữ liệu yêu cầu mua hàng | Lưu thông tin nhu cầu, liên hệ, trạng thái, người phụ trách và phản hồi |
| DR-05 | Dữ liệu kiểm thử | Lưu bộ câu hỏi kiểm thử, request mẫu, response mẫu và kết quả thử nghiệm |
| DR-06 | Dữ liệu cấu hình | Lưu tenant, chatbot, API key placeholder trong tài liệu và cấu hình runtime |

## 6. Yêu cầu giao diện

| Mã | Giao diện | Yêu cầu |
| --- | --- | --- |
| UI-01 | Trang đăng nhập | Cho phép người dùng quản trị đăng nhập theo vai trò |
| UI-02 | Platform admin | Quản lý tenant, tài khoản tenant, thống kê và runtime |
| UI-03 | Tenant admin | Quản lý chatbot, nguồn tri thức, hội thoại, lead và yêu cầu mua hàng |
| UI-04 | Web chat | Cho phép người dùng hỏi đáp và nhận tư vấn sản phẩm |
| UI-05 | General chat | Cho phép kiểm thử luồng chat chung |
| UI-06 | Purchase requests | Cho phép xem, lọc, phân công và cập nhật trạng thái yêu cầu mua hàng |

## 7. Yêu cầu API

| Mã | Nhóm API | Mô tả |
| --- | --- | --- |
| API-01 | System/Login | Health, đăng nhập, đăng xuất, kiểm tra phiên |
| API-02 | Admin/Tenant | Quản lý tenant và tenant member |
| API-03 | Chatbot | Cấu hình chatbot và API key |
| API-04 | Knowledge base | Nguồn tri thức và rebuild KB |
| API-05 | Chat | Web chat, general chat, conversation và message |
| API-06 | Purchase request | Tạo, xem, cập nhật, phân công và phản hồi yêu cầu |
| API-07 | Channel integration | Messenger/Telegram binding và webhook |
| API-08 | Runtime/Ops | Kiểm tra runtime, thống kê và tác vụ vận hành |

Chi tiết endpoint, request và response được trình bày trong `docs/API_DOCUMENTATION.md`.
