# C.5 Server access

## 1. Mục đích

Tài liệu này cung cấp mẫu thông tin truy cập hệ thống khi triển khai demo hoặc triển khai trên server. Nội dung bao gồm URL truy cập, API endpoint chính, tài khoản demo theo vai trò và các điểm cần kiểm tra trước khi bàn giao.

Các giá trị chứa trong dấu `<...>` là placeholder dùng cho từng môi trường triển khai. Không ghi secret thật, API key thật hoặc mật khẩu thật trong tài liệu này.

## 2. Thông tin server

| Hạng mục | Giá trị |
| --- | --- |
| Tên môi trường | `<ENVIRONMENT_NAME>` |
| Server public URL | `<SERVER_PUBLIC_URL>` |
| Ngrok URL | `<NGROK_URL>` |
| Backend base URL | `<SERVER_PUBLIC_URL>` |
| Python chatbot API URL | `<CHATBOT_API_URL>` |
| Database host | `<DB_HOST>` |
| Người phụ trách vận hành | `<ADMIN_CONTACT>` |

## 3. URL truy cập

| Nhóm truy cập | URL | Mục đích |
| --- | --- | --- |
| Trang đăng nhập | `<SERVER_PUBLIC_URL>/login` | Đăng nhập platform admin, tenant admin hoặc tenant member |
| Trang platform admin | `<SERVER_PUBLIC_URL>/admin` | Quản trị tenant, thống kê và vận hành hệ thống |
| Trang tenant admin | `<SERVER_PUBLIC_URL>/tenant` | Quản trị chatbot, nguồn tri thức và hội thoại của tenant |
| Trang yêu cầu mua hàng | `<SERVER_PUBLIC_URL>/tenant/purchase-requests` | Theo dõi và xử lý yêu cầu tư vấn/mua hàng |
| Web chat theo tenant | `<SERVER_PUBLIC_URL>/chat` | Người dùng hỏi đáp và nhận tư vấn sản phẩm |
| General chat | `<SERVER_PUBLIC_URL>/chat/general` | Chat thử nghiệm không gắn chặt vào một tenant cụ thể |
| Backend health/API | `<SERVER_PUBLIC_URL>/api/me` | Kiểm tra phiên đăng nhập và kết nối backend |
| Python chatbot health | `<CHATBOT_API_URL>/healthz` | Kiểm tra AI/RAG service độc lập |
| FastAPI docs | `<CHATBOT_API_URL>/docs` | Tài liệu tương tác của Python chatbot API |
| Messenger webhook | `<SERVER_PUBLIC_URL>/webhook/messenger` | Webhook nhận sự kiện từ Facebook Messenger |
| Telegram webhook | `<SERVER_PUBLIC_URL>/webhook/telegram/<SECRET_PATH_PLACEHOLDER>` | Webhook nhận sự kiện từ Telegram |

## 4. Tài khoản demo theo vai trò

| Vai trò | Tài khoản | Mật khẩu | Phạm vi sử dụng |
| --- | --- | --- | --- |
| Platform admin | `<PLATFORM_ADMIN_USERNAME>` | `<PLATFORM_ADMIN_PASSWORD>` | Quản trị tenant, tài khoản tenant, thống kê và runtime |
| Tenant admin | `<TENANT_ADMIN_USERNAME>` | `<TENANT_ADMIN_PASSWORD>` | Quản trị chatbot, nguồn tri thức, hội thoại và yêu cầu mua hàng của tenant |
| Tenant member | `<TENANT_MEMBER_USERNAME>` | `<TENANT_MEMBER_PASSWORD>` | Xử lý hội thoại, lead và yêu cầu mua hàng được phân quyền |
| Người dùng chat | Không yêu cầu đăng nhập | Không áp dụng | Hỏi đáp sản phẩm, tư vấn lựa chọn và gửi thông tin liên hệ |

## 5. API key demo

| Tenant | API key placeholder | Ghi chú |
| --- | --- | --- |
| Tenant demo nội thất | `<TENANT_DEMO_API_KEY>` | Dùng cho request API có header `X-Api-Key` |
| Tenant demo bài viết | `<TENANT_ARTICLE_API_KEY>` | Dùng cho kiểm thử chatbot theo nguồn tri thức dạng bài viết |

## 6. Header truy cập API

| Header | Giá trị mẫu | Mục đích |
| --- | --- | --- |
| `Content-Type` | `application/json` | Định dạng request body |
| `X-Api-Key` | `<TENANT_DEMO_API_KEY>` | Xác thực một số API chat theo tenant |
| `Cookie` | `JSESSIONID=<SESSION_ID>` | Xác thực phiên đăng nhập trên giao diện quản trị |

## 7. Checklist kiểm tra truy cập

| Mục kiểm tra | Cách kiểm tra | Kết quả hợp lệ |
| --- | --- | --- |
| Server phản hồi | Mở `<SERVER_PUBLIC_URL>/login` | Giao diện đăng nhập hiển thị |
| Đăng nhập platform admin | Đăng nhập bằng tài khoản platform admin | Truy cập được trang `/admin` |
| Đăng nhập tenant admin | Đăng nhập bằng tài khoản tenant admin | Truy cập được trang `/tenant` |
| Web chat | Mở `/chat` và gửi câu hỏi sản phẩm | Hệ thống trả lời theo dữ liệu sản phẩm |
| Python chatbot API | Gọi `GET <CHATBOT_API_URL>/healthz` | Response trạng thái service hợp lệ |
| Webhook public URL | Dùng ngrok hoặc domain public | URL webhook nhận được request từ nền tảng bên ngoài |

