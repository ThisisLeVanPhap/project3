# Requirements Table

| Mã | Loại | Nội dung | Actor/Thành phần |
| --- | --- | --- | --- |
| FR-01 | Chức năng | Đăng nhập, đăng xuất, kiểm tra phiên và phân quyền | Admin, tenant user |
| FR-02 | Chức năng | Quản lý tenant và trạng thái hoạt động | Platform admin |
| FR-03 | Chức năng | Quản lý thành viên tenant và vai trò | Platform admin |
| FR-04 | Chức năng | Quản lý cấu hình chatbot, API key và runtime | Tenant admin |
| FR-05 | Chức năng | Quản lý nguồn dữ liệu sản phẩm phục vụ KB | Tenant admin |
| FR-06 | Chức năng | Xử lý dữ liệu sản phẩm thành tài liệu, chunks và chỉ mục | System |
| FR-07 | Chức năng | Rebuild knowledge base và theo dõi trạng thái | Tenant admin |
| FR-08 | Chức năng | Truy xuất tri thức từ knowledge base | AI/RAG service |
| FR-09 | Chức năng | Chat hỏi đáp thông tin sản phẩm | Người dùng cuối |
| FR-10 | Chức năng | Gợi ý sản phẩm theo nhu cầu và tiêu chí | Người dùng cuối |
| FR-11 | Chức năng | Tham chiếu/so sánh thông tin sản phẩm trong phạm vi dữ liệu | Người dùng cuối |
| FR-12 | Chức năng | Lưu lịch sử hội thoại, tin nhắn và metadata | Backend |
| FR-13 | Chức năng | Quản lý lead và yêu cầu mua hàng | Tenant admin/member |
| FR-14 | Chức năng | Tích hợp Messenger và Telegram qua webhook | Backend |
| FR-15 | Chức năng | Cung cấp API vận hành runtime và thống kê | Platform admin |
| NFR-01 | Phi chức năng | Tách biệt dữ liệu theo tenant | Backend, database |
| NFR-02 | Phi chức năng | Bảo mật bằng session hoặc API key theo nhóm endpoint | Backend |
| NFR-03 | Phi chức năng | Triển khai được bằng Docker Compose hoặc chạy từng service | Deployment |
| NFR-04 | Phi chức năng | Có log, health check và trạng thái xử lý để vận hành | Operations |
| NFR-05 | Phi chức năng | Có test cases, request mẫu và kết quả thử nghiệm | Testing |

