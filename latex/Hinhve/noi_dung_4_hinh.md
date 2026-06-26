# Nội dung văn bản cho 4 hình Chương 4

## Hình 4.1 — Kiến trúc tổng thể multi-tenant RAG chatbot

Hệ thống được tổ chức theo mô hình multi-tenant với ranh giới dữ liệu là `tenant_id`. Người dùng tiếp cận qua Web Chat, Messenger, Telegram hoặc Admin UI; các kênh ngoài đi qua webhook (sử dụng ngrok trong giai đoạn phát triển) trước khi đến backend. Spring Boot Backend đảm nhiệm xác thực, phân quyền theo vai trò, định tuyến hội thoại và quản lý nghiệp vụ; PostgreSQL lưu dữ liệu hệ thống, còn KB Artifact Storage trên file system lưu các artifact tri thức theo cửa hàng. FastAPI Chatbot Runtime nạp KB của từng cửa hàng theo yêu cầu và sinh phản hồi bằng cách gửi yêu cầu đến Claude API (Anthropic) hoặc rơi về luật rule fallback nếu cần. Cách phân tách này cho phép phần kiến trúc lõi do nhóm tự xây dựng được tách bạch rõ với dịch vụ ngôn ngữ bên ngoài.

## Hình 4.2 — Luồng dữ liệu sản phẩm và knowledge base

Dữ liệu sản phẩm không đi thẳng từ nguồn vào chatbot mà phải qua một chuỗi xử lý ngoại tuyến có kiểm soát. Từ nguồn (URL hoặc sitemap), pipeline thu thập, chuẩn hóa thành định dạng nội bộ rồi đi qua bước kiểm tra chất lượng — soát mojibake, đếm số sản phẩm, phát hiện URL trùng và độ phủ giá. Khi đạt ngưỡng, dữ liệu được đăng ký thành một bộ dữ liệu sản phẩm chính thức và đóng gói thành KB Artifact lưu trên file system. Artifact chỉ phát huy tác dụng sau khi được kích hoạt cho một cửa hàng cụ thể; chatbot luôn trả lời dựa trên artifact đang ở trạng thái active của cửa hàng đó. Cách tách rời giữa dataset, artifact và liên kết kích hoạt cho phép cập nhật tri thức mà không phải sửa luồng chatbot.

## Hình 4.3 — Luồng hội thoại và kiểm soát ba chế độ

Mọi tin nhắn đến đều đi qua cùng một bước xác định cửa hàng, kênh và phiên hội thoại trước khi rẽ nhánh theo chế độ. Ở chế độ tư vấn bán hàng theo cửa hàng (`tenant_sales`), chatbot truy xuất knowledge base đang active của cửa hàng, sinh phản hồi và có thể tạo lead hoặc yêu cầu mua hàng nếu hội thoại đáp ứng đủ điều kiện. Hai chế độ còn lại — so sánh sản phẩm chung (`general_compare`) và tham khảo giá (`market_price`) — chỉ truy xuất nguồn dữ liệu được phép tương ứng và không được phép tạo dữ liệu nghiệp vụ. Phản hồi cuối cùng được lưu lại và trả về đúng kênh khách hàng đã gửi tin. Việc tách quyền tạo dữ liệu nghiệp vụ ra khỏi tín hiệu sinh từ mô hình ngôn ngữ là điểm then chốt: mô hình chỉ đề xuất, backend mới quyết định ghi.

## Hình 4.4 — Nhận diện khách hàng liên kênh

Khách hàng đến từ Messenger có định danh theo cặp `pageId + senderId`, từ Telegram theo `chatId`/`userId`; hai cách định danh tự nhiên này không trùng nhau. Hệ thống ghi nhận từng định danh kênh thành một bản ghi riêng, sau đó nếu khách hàng cung cấp số điện thoại hoặc email trong hội thoại, các bản ghi cùng cửa hàng có cùng thông tin chuẩn hóa sẽ được liên kết về một hồ sơ khách hàng thống nhất. Mọi hội thoại, lead và yêu cầu mua hàng phát sinh đều gắn với hồ sơ này. Phạm vi liên kết luôn bị chặn trong một cửa hàng: cùng số điện thoại nhưng ở hai cửa hàng khác nhau vẫn là hai hồ sơ tách biệt. Hệ thống không gộp chỉ dựa vào tên hiển thị để tránh nhầm lẫn giữa những khách hàng trùng tên.
