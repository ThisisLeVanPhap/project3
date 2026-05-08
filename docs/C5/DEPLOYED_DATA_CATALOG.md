# C.5 Danh mục dữ liệu triển khai

## 1. Mục đích

Tài liệu này mô tả danh mục dữ liệu sử dụng khi triển khai demo hệ thống, bao gồm tenant, knowledge base, dữ liệu đầu vào, dữ liệu đầu ra, test cases và các bảng database nghiệp vụ.

## 2. Tenant demo

| Tenant | Mã tenant | API key placeholder | Phạm vi dữ liệu |
| --- | --- | --- | --- |
| Nội thất demo | `<TENANT_DEMO_CODE>` | `<TENANT_DEMO_API_KEY>` | Dữ liệu sản phẩm và bài viết tư vấn nội thất |
| Bài viết demo | `<TENANT_ARTICLE_CODE>` | `<TENANT_ARTICLE_API_KEY>` | Dữ liệu dạng bài viết/tham khảo phục vụ kiểm thử retrieval |

## 3. Knowledge base folders

| Thư mục | Nội dung | Vai trò |
| --- | --- | --- |
| `chatbot/kb/noithatcaco` | Dữ liệu sản phẩm, metadata, chunks và chỉ mục truy xuất cho tenant nội thất demo | Nguồn tri thức chính cho hỏi đáp và gợi ý sản phẩm |
| `chatbot/kb/article` | Dữ liệu tri thức dạng bài viết | Kiểm thử truy xuất theo nội dung văn bản |
| `chatbot/kb/castlery` | Dữ liệu tham khảo sản phẩm nội thất | Kiểm thử truy vấn sản phẩm theo nguồn khác |
| `chatbot/kb/price_reference.json` | Dữ liệu tham chiếu giá | Hỗ trợ đối chiếu mức giá trong câu trả lời |

## 4. Dữ liệu đầu vào

| Loại dữ liệu | File/Bảng | Mô tả |
| --- | --- | --- |
| URL nguồn sản phẩm | `raw_urls.txt`, bảng nguồn KB theo tenant | Danh sách URL hoặc nguồn dữ liệu dùng để thu thập nội dung sản phẩm |
| Tài liệu chuẩn hóa | `docs.jsonl` | Nội dung sản phẩm/bài viết sau bước chuẩn hóa |
| Đoạn tri thức | `chunks.jsonl` | Các đoạn văn bản ngắn phục vụ retrieval |
| Chỉ mục truy xuất | `index.json` và file chỉ mục đi kèm | Dữ liệu phục vụ tìm kiếm keyword, vector hoặc hybrid |
| Câu hỏi người dùng | Request chat, request general chat | Nội dung hỏi đáp, nhu cầu tư vấn, tiêu chí chọn sản phẩm |
| Tiêu chí gợi ý | Request API hoặc dữ liệu nhập từ giao diện | Loại sản phẩm, không gian sử dụng, ngân sách, chất liệu, phong cách |
| Cấu hình chatbot | Bảng `chatbot_instances` | Tenant, tên chatbot, thư mục KB, runtime và API key |

## 5. Dữ liệu đầu ra

| Loại dữ liệu | Nơi lưu/Response | Mô tả |
| --- | --- | --- |
| Kết quả truy xuất tri thức | Response AI/RAG service | Danh sách đoạn tri thức liên quan đến câu hỏi |
| Câu trả lời chatbot | Response `/api/chat/*`, `/api/general/chat/*`, `/chat` | Nội dung trả lời người dùng dựa trên dữ liệu sản phẩm |
| Danh sách sản phẩm gợi ý | Response chat/API | Gợi ý sản phẩm theo nhu cầu và tiêu chí đầu vào |
| Tham chiếu sản phẩm/giá | Response chat/API | Thông tin đối chiếu tên sản phẩm, giá, thuộc tính và nguồn tham khảo |
| Lịch sử hội thoại | Bảng hội thoại và message | Phiên chat, tin nhắn người dùng, phản hồi hệ thống |
| Lead/yêu cầu mua hàng | Bảng lead và purchase request | Thông tin khách hàng, nhu cầu tư vấn và trạng thái xử lý |
| Feedback | Bảng feedback hoặc file output AI/RAG | Đánh giá câu trả lời, dữ liệu dùng cho kiểm thử chất lượng |
| Kết quả thử nghiệm | `chatbot/eval/results-summary.md`, tài liệu C.3 | Chỉ số retrieval và kết quả test cases |

## 6. Bộ câu hỏi kiểm thử và kết quả thử nghiệm

| Hạng mục | Vị trí | Mô tả |
| --- | --- | --- |
| Bộ câu hỏi kiểm thử retrieval | `chatbot/eval/dataset.jsonl` | Câu hỏi tiếng Việt dùng để đánh giá truy xuất tri thức |
| Tổng hợp kết quả retrieval | `chatbot/eval/results-summary.md` | Recall@5 và MRR của các chiến lược keyword, vector, hybrid, hybrid_rerank |
| Test backend | `multitenant/src/test` | Kiểm thử controller, service, login, chatbot, purchase request, runtime và rebuild KB |
| Test Python chatbot | `chatbot/tests` | Kiểm thử dữ liệu, retrieval và API AI/RAG |
| Postman collection | `multitenant/postman` | Request mẫu phục vụ kiểm thử API |
| Tài liệu test cases | `docs/C3_TEST_CASES_AND_RESULTS.md` | Danh sách test cases và kết quả thử nghiệm theo nhóm chức năng |

## 7. Bảng database nghiệp vụ

| Nhóm dữ liệu | Bảng/Thực thể | Vai trò |
| --- | --- | --- |
| Tenant | `tenants` | Lưu thông tin tenant, trạng thái và cấu hình truy cập |
| Người dùng tenant | `tenant_members` | Lưu tài khoản tenant admin/member và vai trò |
| Chatbot | `chatbot_instances` | Lưu cấu hình chatbot, API key, thư mục KB và runtime |
| Knowledge base | Bảng nguồn KB, bảng trạng thái rebuild | Lưu URL nguồn, trạng thái xử lý và kết quả rebuild |
| Hội thoại | `conversations`, `messages` | Lưu session hội thoại và tin nhắn |
| Lead | `leads` | Lưu thông tin khách hàng tiềm năng từ chat hoặc kênh tích hợp |
| Yêu cầu mua hàng | `purchase_requests` và bảng liên quan | Lưu nhu cầu mua hàng, trạng thái, phân công và phản hồi |
| Feedback | `feedback` hoặc thực thể tương ứng | Lưu đánh giá phản hồi chatbot |
| Tích hợp kênh | Bảng Messenger/Telegram binding | Lưu cấu hình kết nối kênh hội thoại |
| Vận hành | Bảng trạng thái runtime/tác vụ nếu có | Theo dõi tiến trình rebuild và vận hành AI/RAG |

## 8. Quy ước cập nhật catalog

| Nội dung cần cập nhật | Quy ước |
| --- | --- |
| Link server/ngrok | Ghi trong `docs/C5/SERVER_ACCESS.md` bằng placeholder hoặc URL triển khai nội bộ |
| Tài khoản demo | Chỉ ghi tài khoản demo được phép chia sẻ, không ghi secret thật |
| API key | Ghi placeholder hoặc giá trị demo reset cho môi trường nộp bài |
| Snapshot dữ liệu | Ghi ngày snapshot và số lượng bản ghi nếu cần đối chiếu |
