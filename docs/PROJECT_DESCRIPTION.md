# Project Description

## 1. Tên đề tài

Tên đề tài: Hệ thống chatbot tư vấn và gợi ý sản phẩm nội thất sử dụng truy xuất tri thức và mô hình ngôn ngữ lớn.

## 2. Bối cảnh và vấn đề

Người dùng khi mua sản phẩm nội thất thường cần nhiều thông tin trước khi ra quyết định, ví dụ kích thước, chất liệu, màu sắc, phong cách, mức giá, không gian sử dụng và chính sách liên quan. Việc tìm kiếm thủ công trên website hoặc tài liệu sản phẩm tốn thời gian, đặc biệt khi số lượng sản phẩm lớn và thông tin nằm rải rác ở nhiều trang.

Trong lĩnh vực nội thất, nhu cầu tư vấn thường mang tính hội thoại. Người dùng có thể bắt đầu bằng một yêu cầu chung như chọn sofa cho phòng khách nhỏ, sau đó bổ sung ngân sách, phong cách, chất liệu, kích thước hoặc thay đổi lựa chọn trong quá trình trao đổi. Hệ thống tìm kiếm truyền thống khó xử lý tốt các tình huống đa lượt như vậy vì chỉ trả về danh sách kết quả, không duy trì ngữ cảnh tư vấn.

Chatbot tư vấn sản phẩm giúp tự động hóa quá trình hỏi đáp, gợi ý và tham chiếu thông tin sản phẩm. Khi kết hợp truy xuất tri thức với mô hình ngôn ngữ lớn, hệ thống có thể khai thác dữ liệu sản phẩm của cửa hàng để tạo câu trả lời tự nhiên, đúng ngữ cảnh và phù hợp với nhu cầu người dùng.

## 3. Mục tiêu hệ thống

Mục tiêu của hệ thống:

- Quản lý dữ liệu sản phẩm nội thất và thông tin liên quan theo từng cửa hàng/tenant.
- Xử lý dữ liệu sản phẩm thành knowledge base phục vụ truy xuất tri thức.
- Hỗ trợ hỏi đáp thông tin sản phẩm, chính sách và nội dung tư vấn liên quan đến nội thất.
- Hỗ trợ gợi ý/tư vấn sản phẩm theo nhu cầu người dùng như loại sản phẩm, không gian sử dụng, ngân sách, phong cách, màu sắc và chất liệu.
- Tích hợp mô hình ngôn ngữ lớn thông qua API hoặc runtime cục bộ có cấu hình provider.
- Cung cấp backend API, giao diện demo/người dùng/quản trị và bộ kiểm thử phục vụ sử dụng, kiểm tra và trình bày sản phẩm.

## 4. Phạm vi chức năng

Các nhóm chức năng chính của hệ thống:

- Quản lý sản phẩm và nguồn dữ liệu sản phẩm: lưu cấu hình tenant, đường dẫn knowledge base, danh sách URL nguồn và dữ liệu sản phẩm sau xử lý.
- Xử lý dữ liệu sản phẩm: crawl nội dung từ URL nguồn, chuẩn hóa dữ liệu, chia tài liệu thành chunk và tạo chỉ mục truy xuất.
- Truy xuất tri thức/RAG: tìm các đoạn tri thức liên quan từ knowledge base theo câu hỏi người dùng, đưa context vào prompt để sinh câu trả lời.
- Chatbot hỏi đáp sản phẩm: tiếp nhận câu hỏi từ web chat hoặc kênh tích hợp, trả lời dựa trên dữ liệu sản phẩm và lịch sử hội thoại.
- Gợi ý sản phẩm: tư vấn lựa chọn theo nhu cầu người dùng, bao gồm loại sản phẩm, không gian, ngân sách, phong cách, chất liệu và màu sắc.
- So sánh hoặc tham chiếu thông tin sản phẩm: hỗ trợ tham chiếu khoảng giá, tìm sản phẩm tương tự và so sánh hiệu quả các phương thức truy xuất bằng chỉ số thử nghiệm.
- Quản lý hội thoại: tạo conversation, lưu message, xem lại lịch sử, đổi tên và xóa hội thoại.
- Quản lý yêu cầu mua hàng: tạo purchase request từ hội thoại khi người dùng xác nhận nhu cầu, hỗ trợ cập nhật trạng thái, nhận xử lý và phân công.
- Giao diện người dùng/quản trị: cung cấp trang login, admin UI, tenant UI, web chat, general chat và màn hình quản lý purchase request.
- API backend: cung cấp API cho chat, tenant, chatbot, knowledge base, purchase request, kênh Messenger/Telegram, runtime và thống kê vận hành.
- Kiểm thử và đánh giá hệ thống: cung cấp test backend, test Python chatbot, test hội thoại và đánh giá retrieval bằng Recall@k, MRR.

## 5. Kiến trúc tổng quan

Hệ thống gồm các thành phần chính:

- Frontend: giao diện HTML/CSS/JavaScript tĩnh được phục vụ bởi Spring Boot, gồm login, admin UI, tenant UI, web chat, general chat và màn hình quản lý yêu cầu mua hàng.
- Backend service: ứng dụng Spring Boot trong thư mục `multitenant/`, chịu trách nhiệm xử lý API nghiệp vụ, xác định tenant, quản lý hội thoại, quản lý chatbot, lưu dữ liệu vào PostgreSQL và gọi AI/RAG service.
- AI/RAG service: dịch vụ FastAPI trong thư mục `chatbot/`, chịu trách nhiệm nạp knowledge base, truy xuất tri thức, xây prompt, quản lý state hội thoại và sinh câu trả lời.
- Cơ sở dữ liệu: PostgreSQL lưu tenant, thành viên, chatbot instance, conversation, message, lead, feedback, purchase request, binding Messenger/Telegram và thông tin vận hành.
- Thành phần lưu trữ/truy xuất tri thức: các thư mục knowledge base trong `chatbot/kb/`, gồm `raw_urls.txt`, `docs.jsonl`, `chunks.jsonl`, `index.json` cho từng nguồn dữ liệu.
- API gọi mô hình ngôn ngữ lớn: Python service nhận cấu hình `provider`, `api_model`, `api_key`, `api_base_url` hoặc cấu hình runtime local để gọi mô hình sinh câu trả lời.

Luồng xử lý chat:

1. Người dùng gửi câu hỏi qua web chat, Messenger hoặc Telegram.
2. Backend xác định tenant, chatbot và conversation tương ứng.
3. Backend lấy cấu hình chatbot và gửi request đến Python chatbot service.
4. AI/RAG service truy xuất context liên quan từ knowledge base của tenant.
5. Prompt được xây từ câu hỏi, lịch sử hội thoại, context truy xuất và system prompt.
6. Mô hình ngôn ngữ lớn sinh câu trả lời.
7. Backend lưu message, trả response cho người dùng và tạo purchase request khi hội thoại có xác nhận nhu cầu mua hàng.

## 6. Công nghệ sử dụng

Backend:

- Java 21: ngôn ngữ triển khai backend.
- Spring Boot 3.5.7: framework chính cho REST API và ứng dụng web.
- Spring Web và Spring WebFlux: xây dựng controller HTTP và client gọi Python service.
- Spring Security: xử lý xác thực/session và bảo vệ API.
- Spring Data JPA: truy cập dữ liệu qua repository/entity.
- Flyway: quản lý migration database.
- PostgreSQL Driver: kết nối PostgreSQL.
- Lombok: giảm mã lặp trong entity/service.

AI/RAG service:

- Python 3.11: ngôn ngữ triển khai chatbot service.
- FastAPI: xây dựng API `/chat`, `/healthz`, `/feedback`, `/state`.
- Uvicorn: chạy ASGI server cho FastAPI.
- Transformers, PEFT, Accelerate, PyTorch: phục vụ runtime sinh câu trả lời khi dùng provider local.
- Requests: gọi provider API và thu thập dữ liệu.
- BeautifulSoup4 và lxml: hỗ trợ crawl và xử lý nội dung HTML.

Dữ liệu và triển khai:

- Docker và Docker Compose: đóng gói và chạy PostgreSQL/backend/chatbot runtime.
- Maven: build và chạy backend Spring Boot.
- JSONL/JSON: định dạng lưu dữ liệu sản phẩm, chunk, chỉ mục và kết quả thử nghiệm.
- Mermaid: biểu diễn sơ đồ kỹ thuật trong tài liệu Markdown.

Kiểm thử và đánh giá:

- JUnit/Spring Boot Test: kiểm thử backend.
- Python unittest: kiểm thử chatbot service và retrieval.
- Script đánh giá retrieval: tính Recall@k và MRR cho các mode truy xuất.

## 7. Dữ liệu sử dụng

Dữ liệu sản phẩm và tri thức:

- Danh sách URL nguồn trong `raw_urls.txt`.
- Nội dung sản phẩm/chính sách sau thu thập trong `docs.jsonl`.
- Các đoạn tri thức phục vụ truy xuất trong `chunks.jsonl`.
- Chỉ mục truy xuất trong `index.json`.
- Dữ liệu tham chiếu giá trong `chatbot/kb/price_reference.json`.

Dữ liệu đầu vào:

- Câu hỏi/tin nhắn người dùng từ web chat, Messenger hoặc Telegram.
- Cấu hình tenant, chatbot, provider, model, prompt và knowledge base.
- Nguồn dữ liệu sản phẩm từ website hoặc tài liệu nội bộ được đưa vào pipeline xử lý.

Dữ liệu đầu ra:

- Câu trả lời tư vấn sản phẩm từ chatbot.
- Lịch sử conversation và message.
- Lead và purchase request từ hội thoại.
- Feedback đánh giá câu trả lời.
- Log chat, log feedback và thông tin timing.
- Kết quả đánh giá retrieval.

Test cases và kết quả thử nghiệm:

- Test backend trong `multitenant/src/test/java`.
- Test Python chatbot trong `chatbot/tests`.
- Test hội thoại tiếng Việt trong `chatbot/tools/datasets/vietnamese_buyer_script.json`.
- Bộ dữ liệu đánh giá retrieval trong `chatbot/eval/dataset.jsonl`.
- Kết quả thử nghiệm retrieval trong `chatbot/eval/results-summary.md` với các chỉ số Recall@k và MRR.

## 8. Kết quả đầu ra của project

Các sản phẩm đầu ra:

- Mã nguồn chương trình cho backend Spring Boot, Python chatbot service, giao diện static và công cụ xử lý dữ liệu.
- README và mô tả project.
- API documentation cho backend API và Python chatbot API.
- Dữ liệu đầu vào/đầu ra, knowledge base mẫu, test cases và kết quả thử nghiệm.
- Tài liệu kỹ thuật mô tả kiến trúc, module, dữ liệu, RAG/retrieval, luồng xử lý và tích hợp mô hình.
- Tài liệu triển khai và hướng dẫn sử dụng hệ thống.
- Video demo trình bày luồng sử dụng chính của chatbot và giao diện quản trị.
- Slide báo cáo trình bày bài toán, kiến trúc, chức năng, kết quả thử nghiệm và hướng triển khai sản phẩm.
