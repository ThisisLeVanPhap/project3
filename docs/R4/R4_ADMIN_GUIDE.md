# R.4 Hướng dẫn quản trị hệ thống

## 1. Mục đích

Tài liệu này hướng dẫn platform admin, tenant admin và tenant member vận hành các chức năng quản trị của hệ thống chatbot tư vấn/gợi ý sản phẩm nội thất.

## 2. Đăng nhập

1. Mở `<SERVER_PUBLIC_URL>/login`.
2. Nhập tài khoản theo vai trò.
3. Sau khi đăng nhập, hệ thống điều hướng tới khu vực phù hợp với quyền truy cập.
4. Dùng chức năng logout để kết thúc phiên làm việc.

| Vai trò | Khu vực truy cập | Phạm vi |
| --- | --- | --- |
| Platform admin | `/admin` | Tenant, tài khoản tenant, thống kê, runtime và tác vụ vận hành |
| Tenant admin | `/tenant` | Chatbot, nguồn tri thức, hội thoại, lead, yêu cầu mua hàng |
| Tenant member | `/tenant` hoặc trang nghiệp vụ được phân quyền | Xử lý hội thoại, lead và yêu cầu mua hàng |

## 3. Quản trị tenant

Dành cho platform admin.

1. Mở trang quản trị tenant.
2. Tạo hoặc cập nhật thông tin tenant.
3. Kiểm tra trạng thái hoạt động và thông tin định danh tenant.
4. Quản lý thành viên tenant và vai trò tương ứng.

Các API liên quan:

- `GET /api/admin/tenants`
- `POST /api/admin/tenants`
- `PUT /api/admin/tenants/{id}`
- `GET /api/admin/tenant-members`
- `POST /api/admin/tenant-members`
- `PUT /api/admin/tenant-members/{id}`

## 4. Quản trị chatbot

Dành cho tenant admin hoặc platform admin theo phạm vi phân quyền.

1. Mở khu vực quản lý chatbot.
2. Kiểm tra tên chatbot, tenant, API key, knowledge base folder và runtime.
3. Cập nhật cấu hình khi thay đổi nguồn dữ liệu hoặc runtime.
4. Kiểm tra chat thử sau khi cấu hình.

API liên quan:

- `GET /api/chatbots`
- `POST /api/chatbots`
- `PUT /api/chatbots/{id}`
- `DELETE /api/chatbots/{id}`

## 5. Quản lý nguồn tri thức và rebuild KB

1. Mở khu vực nguồn tri thức của tenant.
2. Thêm hoặc cập nhật URL nguồn dữ liệu sản phẩm.
3. Kích hoạt rebuild knowledge base.
4. Theo dõi trạng thái xử lý.
5. Kiểm tra bằng câu hỏi sản phẩm trên web chat.

API liên quan:

- `GET /api/kb/source-urls`
- `POST /api/kb/source-urls`
- `DELETE /api/kb/source-urls/{id}`
- `POST /api/kb/rebuild`
- `GET /api/kb/rebuild/status`

## 6. Quản lý hội thoại và lead

Tenant admin/member dùng khu vực hội thoại để xem tin nhắn, kiểm tra nhu cầu người dùng và phản hồi khi cần.

Nhóm thao tác chính:

- Xem danh sách hội thoại theo tenant hoặc kênh.
- Mở chi tiết tin nhắn và ngữ cảnh.
- Ghi nhận lead từ hội thoại.
- Phản hồi hoặc chuyển xử lý cho người phụ trách.

API liên quan:

- `GET /api/chat/conversations`
- `GET /api/chat/conversations/{id}/messages`
- `GET /admin/api/leads`
- `GET /tenant/api/leads`
- `POST /tenant/api/reply`
- `POST /tenant/api/leads-ops/{id}/claim`

## 7. Quản lý yêu cầu mua hàng

1. Mở trang `/tenant/purchase-requests`.
2. Lọc danh sách theo trạng thái, người phụ trách hoặc thời gian.
3. Mở chi tiết yêu cầu để xem nhu cầu, sản phẩm quan tâm và thông tin liên hệ.
4. Phân công người xử lý nếu cần.
5. Cập nhật trạng thái và nội dung phản hồi.

API liên quan:

- `GET /api/purchase-requests`
- `POST /api/purchase-requests`
- `GET /api/purchase-requests/{id}`
- `PUT /api/purchase-requests/{id}`
- `POST /api/purchase-requests/{id}/assign`
- `POST /api/purchase-requests/{id}/status`
- `POST /api/purchase-requests/{id}/reply`

## 8. Quản lý runtime AI/RAG

Platform admin hoặc người vận hành kiểm tra runtime khi chatbot không phản hồi hoặc khi thay đổi cấu hình.

Nhóm thao tác:

- Kiểm tra trạng thái runtime theo chatbot/tenant.
- Xem thống kê vận hành.
- Kiểm tra log backend và AI/RAG service.
- Gọi health endpoint của FastAPI service độc lập khi sử dụng.

API liên quan:

- `GET /api/runtime/llm`
- `GET /api/ops/status`
- `POST /api/ops/restart`
- `GET /admin/api/stats/overview`

## 9. Tích hợp Messenger và Telegram

### Messenger

1. Cấu hình binding giữa page/channel và tenant/chatbot.
2. Cấu hình webhook URL `<SERVER_PUBLIC_URL>/webhook/messenger`.
3. Cấu hình verify token bằng placeholder được cấp riêng cho môi trường.
4. Gửi tin nhắn thử từ page để kiểm tra phản hồi.

API liên quan:

- `GET /api/messenger/bindings`
- `POST /api/messenger/bindings`
- `DELETE /api/messenger/bindings/{id}`
- `GET /webhook/messenger`
- `POST /webhook/messenger`

### Telegram

1. Cấu hình binding giữa bot/channel và tenant/chatbot.
2. Cấu hình webhook URL `<SERVER_PUBLIC_URL>/webhook/telegram/<SECRET_PATH_PLACEHOLDER>`.
3. Gửi tin nhắn thử từ Telegram để kiểm tra phản hồi.

API liên quan:

- `GET /api/telegram/bindings`
- `POST /api/telegram/bindings`
- `DELETE /api/telegram/bindings/{id}`
- `POST /webhook/telegram/{secretPath}`

## 10. Kiểm tra vận hành nhanh

| Mục kiểm tra | Cách kiểm tra |
| --- | --- |
| Backend | Mở `/login` hoặc gọi API đăng nhập/phiên |
| Database | Kiểm tra service `postgres` và migration Flyway |
| AI/RAG runtime | Gọi chat thử hoặc `GET <CHATBOT_API_URL>/healthz` |
| Knowledge base | Rebuild KB và hỏi câu hỏi liên quan đến sản phẩm |
| Hội thoại | Gửi chat và kiểm tra conversation/message |
| Yêu cầu mua hàng | Tạo request mẫu và kiểm tra danh sách |

