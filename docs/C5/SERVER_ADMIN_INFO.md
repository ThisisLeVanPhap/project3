# C.5 Thông tin quản trị server

## 1. Mục đích

Tài liệu này mô tả thông tin quản trị server, service, port, biến môi trường, vai trò tài khoản và nhóm chức năng kiểm thử của hệ thống chatbot tư vấn/gợi ý sản phẩm nội thất.

## 2. Thông tin môi trường vận hành

| Hạng mục | Giá trị |
| --- | --- |
| Server/host | `<SERVER_HOST>` |
| Hệ điều hành | `<SERVER_OS>` |
| Thư mục triển khai | `<DEPLOYMENT_DIRECTORY>` |
| Chế độ triển khai | Docker Compose hoặc chạy local theo service |
| Backend base URL | `<SERVER_PUBLIC_URL>` |
| AI/RAG API URL | `<CHATBOT_API_URL>` |
| Database | PostgreSQL |

## 3. Service và port

| Service | Port mặc định | Vai trò |
| --- | --- | --- |
| Spring Boot backend | `8080` | Cung cấp web UI, backend API, quản trị tenant và tích hợp runtime AI/RAG |
| PostgreSQL | `5432` | Lưu dữ liệu nghiệp vụ, tenant, chatbot, hội thoại và yêu cầu mua hàng |
| Python chatbot runtime theo tenant | `8101-8199` | Runtime phục vụ truy xuất tri thức và sinh câu trả lời theo từng chatbot |
| FastAPI chatbot API độc lập | `8000` | API thử nghiệm trực tiếp cho AI/RAG service |
| Messenger webhook | `8080` qua backend | Nhận và xử lý sự kiện hội thoại từ Messenger |
| Telegram webhook | `8080` qua backend | Nhận và xử lý sự kiện hội thoại từ Telegram |

## 4. Biến môi trường chính

| Tên biến | Ý nghĩa | Ví dụ giá trị giả lập | Bắt buộc/Tùy chọn |
| --- | --- | --- | --- |
| `POSTGRES_DB` | Tên database PostgreSQL | `multitenant_chatbot` | Bắt buộc |
| `POSTGRES_USER` | Tài khoản database | `app_user` | Bắt buộc |
| `POSTGRES_PASSWORD` | Mật khẩu database | `<DB_PASSWORD>` | Bắt buộc |
| `POSTGRES_PORT` | Port expose database | `5432` | Tùy chọn |
| `APP_PORT` | Port expose backend | `8080` | Tùy chọn |
| `SPRING_DATASOURCE_URL` | JDBC URL tới PostgreSQL | `jdbc:postgresql://postgres:5432/multitenant_chatbot` | Bắt buộc |
| `SPRING_DATASOURCE_USERNAME` | Username backend dùng để kết nối database | `app_user` | Bắt buộc |
| `SPRING_DATASOURCE_PASSWORD` | Password backend dùng để kết nối database | `<DB_PASSWORD>` | Bắt buộc |
| `PYTHON_BIN` | Python binary dùng để khởi chạy runtime chatbot | `/usr/bin/python3` | Bắt buộc |
| `MODEL_SERVER_DIR` | Thư mục mã nguồn AI/RAG service | `/opt/app/chatbot` | Bắt buộc |
| `BASE_MODEL` | Tên model/runtime cục bộ hoặc provider được cấu hình | `<BASE_MODEL_NAME>` | Bắt buộc |
| `LLM_HOST` | Host runtime AI/RAG | `127.0.0.1` | Bắt buộc |
| `LLM_PORT_START` | Port bắt đầu cho runtime theo tenant | `8101` | Bắt buộc |
| `LLM_PORT_END` | Port kết thúc cho runtime theo tenant | `8199` | Bắt buộc |
| `LLM_STARTUP_TIMEOUT_MS` | Thời gian chờ runtime khởi động | `180000` | Tùy chọn |
| `MESSENGER_VERIFY_TOKEN` | Token xác minh webhook Messenger | `<MESSENGER_VERIFY_TOKEN>` | Tùy chọn |
| `CHATBOT_KB_DIR` | Thư mục knowledge base của FastAPI service độc lập | `/app/kb` | Tùy chọn |
| `CHATBOT_BASE_MODEL` | Model/runtime cho FastAPI service độc lập | `<BASE_MODEL_NAME>` | Tùy chọn |
| `CHATBOT_LORA_ADAPTER` | Đường dẫn adapter runtime nếu môi trường sử dụng | `<ADAPTER_PATH>` | Tùy chọn |
| `CHATBOT_TOKENIZER_PATH` | Đường dẫn tokenizer nếu tách riêng khỏi model | `<TOKENIZER_PATH>` | Tùy chọn |

## 5. Vai trò quản trị

| Vai trò | Phạm vi quyền |
| --- | --- |
| Platform admin | Quản lý tenant, tài khoản tenant, thống kê hệ thống, runtime và tác vụ vận hành |
| Tenant admin | Quản lý chatbot, nguồn tri thức, rebuild KB, hội thoại, lead, yêu cầu mua hàng và cấu hình kênh tích hợp |
| Tenant member | Xử lý hội thoại, phản hồi lead và yêu cầu mua hàng trong phạm vi tenant |
| Người dùng cuối | Chat hỏi đáp sản phẩm, nhận tư vấn và gửi nhu cầu mua hàng |

## 6. Volume và dữ liệu triển khai

| Volume/Thư mục | Vai trò |
| --- | --- |
| `chatbot/kb` | Lưu dữ liệu tri thức, chunks, chỉ mục và file nguồn theo tenant/chatbot |
| `chatbot/adapters` | Lưu cấu hình hoặc adapter runtime cục bộ nếu môi trường sử dụng |
| `chatbot/out` | Lưu output chạy thử và kết quả sinh trong quá trình kiểm thử |
| `chatbot/logs` | Lưu log service AI/RAG |
| `.hf-cache` | Cache model/runtime cục bộ nếu môi trường cần |
| PostgreSQL data volume | Lưu dữ liệu nghiệp vụ của backend |

## 7. Lệnh vận hành

| Tác vụ | Lệnh |
| --- | --- |
| Build và chạy toàn bộ service | `docker compose up -d --build` |
| Xem trạng thái service | `docker compose ps` |
| Xem log backend | `docker compose logs --no-color --tail=200 app` |
| Xem log database | `docker compose logs --no-color --tail=100 postgres` |
| Dừng service | `docker compose down` |
| Chạy kiểm thử backend | `mvn test` trong thư mục `multitenant` |
| Gọi health AI/RAG service | `GET <CHATBOT_API_URL>/healthz` |

## 8. Chức năng kiểm thử trên server

| Nhóm chức năng | Điểm kiểm tra |
| --- | --- |
| Đăng nhập và phân quyền | Platform admin, tenant admin, tenant member, phiên đăng nhập |
| Quản lý tenant | Tạo, cập nhật, kích hoạt tenant và cấu hình API key |
| Quản lý chatbot | Cấu hình chatbot theo tenant, runtime và knowledge base |
| Quản lý nguồn tri thức | Thêm URL nguồn, rebuild KB, theo dõi trạng thái rebuild |
| Chatbot hỏi đáp | Gửi câu hỏi sản phẩm, nhận câu trả lời có tham chiếu dữ liệu |
| Gợi ý sản phẩm | Gửi nhu cầu về loại sản phẩm, không gian, ngân sách, chất liệu và nhận gợi ý |
| Yêu cầu mua hàng | Tạo, xem, phân công, cập nhật trạng thái và phản hồi yêu cầu |
| Tích hợp kênh | Binding Messenger/Telegram và nhận webhook |
| Vận hành runtime | Kiểm tra trạng thái runtime, thống kê, tác vụ operational |

