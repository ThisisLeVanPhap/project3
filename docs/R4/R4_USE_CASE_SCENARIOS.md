# R.4 Kịch bản sử dụng

## UC-01: Người dùng hỏi thông tin sản phẩm

| Thuộc tính | Nội dung |
| --- | --- |
| Actor | Người dùng cuối |
| Mục tiêu | Nhận câu trả lời về sản phẩm nội thất dựa trên dữ liệu sản phẩm của tenant |
| Tiền điều kiện | Chatbot có knowledge base phù hợp và backend kết nối được AI/RAG service |
| Luồng chính | 1. Người dùng mở trang web chat. 2. Người dùng nhập câu hỏi về sản phẩm. 3. Backend gửi request tới runtime chatbot. 4. AI/RAG service truy xuất đoạn tri thức liên quan. 5. Mô hình ngôn ngữ lớn tạo câu trả lời dựa trên ngữ cảnh. 6. Giao diện hiển thị câu trả lời và lưu lịch sử hội thoại. |
| Ngoại lệ | Câu hỏi rỗng, API key không hợp lệ, runtime không phản hồi, dữ liệu sản phẩm không có thông tin phù hợp |
| Kết quả | Người dùng nhận câu trả lời có căn cứ từ dữ liệu sản phẩm và có thể tiếp tục hỏi theo ngữ cảnh |

## UC-02: Người dùng nhận gợi ý sản phẩm

| Thuộc tính | Nội dung |
| --- | --- |
| Actor | Người dùng cuối |
| Mục tiêu | Nhận danh sách sản phẩm phù hợp với nhu cầu, ngân sách, không gian và phong cách |
| Tiền điều kiện | Dữ liệu sản phẩm có mô tả đủ về loại sản phẩm, giá, chất liệu hoặc thuộc tính liên quan |
| Luồng chính | 1. Người dùng mô tả nhu cầu mua hàng. 2. Chatbot nhận diện các tiêu chí chính. 3. Hệ thống truy xuất sản phẩm liên quan trong knowledge base. 4. Mô hình tạo câu trả lời tư vấn theo tiêu chí. 5. Người dùng nhận danh sách gợi ý kèm lý do chọn. |
| Ngoại lệ | Tiêu chí quá mơ hồ, thiếu ngân sách, thiếu loại sản phẩm, dữ liệu không có sản phẩm khớp hoàn toàn |
| Kết quả | Người dùng có các lựa chọn sản phẩm và thông tin tham khảo để ra quyết định |

## UC-03: Người dùng sử dụng general chat

| Thuộc tính | Nội dung |
| --- | --- |
| Actor | Người dùng cuối hoặc người kiểm thử |
| Mục tiêu | Kiểm tra luồng chat chung và khả năng phản hồi của hệ thống |
| Tiền điều kiện | Backend và runtime AI/RAG hoạt động |
| Luồng chính | 1. Người dùng mở trang general chat. 2. Người dùng gửi câu hỏi. 3. Backend xử lý session general chat. 4. Runtime trả câu trả lời. 5. Giao diện hiển thị phản hồi. |
| Ngoại lệ | Session hết hạn, request không đúng định dạng, runtime trả lỗi |
| Kết quả | Phiên chat chung được xử lý và lưu theo convention của hệ thống |

## UC-04: Tenant admin quản lý nguồn tri thức

| Thuộc tính | Nội dung |
| --- | --- |
| Actor | Tenant admin |
| Mục tiêu | Cấu hình nguồn dữ liệu sản phẩm và tạo knowledge base cho chatbot |
| Tiền điều kiện | Tenant admin đăng nhập và có quyền quản trị tenant |
| Luồng chính | 1. Tenant admin mở trang quản trị tenant. 2. Admin nhập hoặc cập nhật URL nguồn tri thức. 3. Admin kích hoạt rebuild KB. 4. Backend gọi tiến trình xử lý dữ liệu. 5. Hệ thống tạo tài liệu chuẩn hóa, chunks và chỉ mục truy xuất. 6. Admin xem trạng thái rebuild và kiểm tra chatbot. |
| Ngoại lệ | URL không hợp lệ, nguồn không truy cập được, dữ liệu rỗng, tiến trình xử lý lỗi |
| Kết quả | Knowledge base sẵn sàng cho truy xuất tri thức và trả lời chatbot |

## UC-05: Platform admin quản lý tenant và chatbot

| Thuộc tính | Nội dung |
| --- | --- |
| Actor | Platform admin |
| Mục tiêu | Quản lý tenant, tài khoản tenant và cấu hình chatbot ở cấp nền tảng |
| Tiền điều kiện | Platform admin đăng nhập thành công |
| Luồng chính | 1. Platform admin mở trang admin. 2. Admin tạo hoặc cập nhật tenant. 3. Admin quản lý tenant member. 4. Admin kiểm tra cấu hình chatbot, trạng thái runtime và thống kê. 5. Hệ thống lưu thay đổi vào database. |
| Ngoại lệ | Trùng mã tenant, dữ liệu form không hợp lệ, tài khoản thiếu thông tin bắt buộc |
| Kết quả | Tenant và tài khoản được cấu hình đúng phạm vi vận hành |

## UC-06: Ghi nhận yêu cầu mua hàng

| Thuộc tính | Nội dung |
| --- | --- |
| Actor | Người dùng cuối, tenant admin, tenant member |
| Mục tiêu | Chuyển nhu cầu tư vấn thành yêu cầu mua hàng có thể theo dõi |
| Tiền điều kiện | Người dùng có phiên hội thoại hoặc cung cấp thông tin liên hệ |
| Luồng chính | 1. Người dùng nêu nhu cầu mua hàng trong chat. 2. Hệ thống ghi nhận thông tin sản phẩm/nhu cầu/liên hệ. 3. Backend tạo yêu cầu mua hàng. 4. Tenant admin hoặc member xem danh sách yêu cầu. 5. Nhân sự phụ trách cập nhật trạng thái và phản hồi. |
| Ngoại lệ | Thiếu thông tin liên hệ, dữ liệu yêu cầu không hợp lệ, người xử lý không có quyền |
| Kết quả | Yêu cầu mua hàng được lưu và có trạng thái xử lý rõ ràng |

## UC-07: Chat qua Messenger hoặc Telegram

| Thuộc tính | Nội dung |
| --- | --- |
| Actor | Người dùng cuối, tenant admin |
| Mục tiêu | Cho phép người dùng chat với hệ thống qua kênh nhắn tin bên ngoài |
| Tiền điều kiện | Tenant admin cấu hình binding kênh và webhook public URL hợp lệ |
| Luồng chính | 1. Người dùng gửi tin nhắn qua Messenger hoặc Telegram. 2. Nền tảng gọi webhook backend. 3. Backend ánh xạ kênh với tenant/chatbot. 4. Runtime AI/RAG xử lý câu hỏi. 5. Backend gửi phản hồi về kênh tương ứng. |
| Ngoại lệ | Webhook xác minh lỗi, binding không tồn tại, secret path không hợp lệ, nền tảng ngoài trả lỗi |
| Kết quả | Người dùng nhận phản hồi chatbot ngay trong kênh nhắn tin |

## UC-08: Vận hành runtime và kiểm tra hệ thống

| Thuộc tính | Nội dung |
| --- | --- |
| Actor | Platform admin, người vận hành |
| Mục tiêu | Kiểm tra trạng thái service, runtime AI/RAG, database và luồng API |
| Tiền điều kiện | Có quyền truy cập server hoặc trang quản trị |
| Luồng chính | 1. Người vận hành kiểm tra service bằng Docker Compose hoặc health endpoint. 2. Kiểm tra backend, database và runtime chatbot. 3. Gọi API chat thử nghiệm. 4. Xem log khi cần đối chiếu lỗi. 5. Ghi nhận kết quả kiểm tra theo tài liệu C.3. |
| Ngoại lệ | Service dừng, port bị chiếm, biến môi trường sai, database không kết nối |
| Kết quả | Trạng thái hệ thống được xác nhận và lỗi được khoanh vùng theo service |

