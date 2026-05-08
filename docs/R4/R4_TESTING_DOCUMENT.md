# R.4 Tài liệu kiểm thử

## 1. Mục đích

Tài liệu này tổng hợp chiến lược kiểm thử, môi trường kiểm thử, nhóm test cases chính và kết quả thử nghiệm của hệ thống chatbot tư vấn/gợi ý sản phẩm nội thất. Chi tiết test cases được trình bày trong `docs/C3_TEST_CASES_AND_RESULTS.md`.

## 2. Phạm vi kiểm thử

| Nhóm kiểm thử | Phạm vi |
| --- | --- |
| Khởi động hệ thống | Backend, database, AI/RAG service, Docker Compose |
| Xác thực và phân quyền | Login, logout, session, role platform admin/tenant admin/tenant member |
| Quản lý tenant/chatbot | Tenant, tenant member, chatbot instance, API key |
| Dữ liệu sản phẩm và KB | URL nguồn, rebuild KB, chunks, chỉ mục truy xuất |
| Chatbot hỏi đáp | Web chat, general chat, conversation và message |
| Gợi ý sản phẩm | Tư vấn theo nhu cầu, ngân sách, không gian và thuộc tính sản phẩm |
| Yêu cầu mua hàng | Tạo, xem, cập nhật, phân công, trạng thái và phản hồi |
| Tích hợp kênh | Messenger binding/webhook, Telegram binding/webhook |
| Runtime và vận hành | LLM runtime, ops API, logs và thống kê |
| API và giao diện | Request/response JSON, form, bảng dữ liệu và luồng frontend-backend-AI/RAG |

## 3. Môi trường kiểm thử

| Thành phần | Công nghệ/Cấu hình |
| --- | --- |
| Backend | Java 21, Spring Boot, Maven |
| Database | PostgreSQL 16 |
| AI/RAG service | Python, FastAPI, Uvicorn |
| Runtime mô hình | API hoặc runtime cục bộ được cấu hình qua biến môi trường |
| Container | Docker Compose |
| Test backend | JUnit/Spring test trong `multitenant/src/test` |
| Test AI/RAG | Python tests trong `chatbot/tests` |
| Test API | Postman collection trong `multitenant/postman` và request mẫu trong docs |
| Test retrieval | Bộ câu hỏi kiểm thử trong `chatbot/eval` |

## 4. Dữ liệu kiểm thử

| Dữ liệu | Vị trí/Nguồn | Mục đích |
| --- | --- | --- |
| Dữ liệu sản phẩm nội thất | `chatbot/kb/noithatcaco` | Kiểm thử truy xuất và tư vấn sản phẩm |
| Dữ liệu bài viết | `chatbot/kb/article` | Kiểm thử retrieval theo văn bản |
| Dữ liệu tham khảo giá | `chatbot/kb/price_reference.json` | Kiểm thử tham chiếu thông tin giá |
| Bộ câu hỏi kiểm thử | `chatbot/eval/dataset.jsonl` | Đánh giá Recall@5 và MRR |
| Request API mẫu | `docs/API_DOCUMENTATION.md`, `multitenant/postman` | Kiểm thử endpoint backend và AI/RAG |
| Test cases tổng hợp | `docs/C3_TEST_CASES_AND_RESULTS.md` | Kiểm thử theo nhóm chức năng |

## 5. Nhóm test cases chính

| Nhóm chức năng | Mục tiêu kiểm thử | Kết quả mong đợi |
| --- | --- | --- |
| Health check | Xác nhận service phản hồi | Backend, database và AI/RAG service hoạt động |
| Login/phân quyền | Kiểm tra role và session | Người dùng chỉ truy cập đúng phạm vi quyền |
| Tenant/chatbot | Kiểm tra CRUD và cấu hình | Dữ liệu được lưu đúng tenant và response đúng schema |
| KB rebuild | Kiểm tra xử lý dữ liệu sản phẩm | Knowledge base có tài liệu, chunks và chỉ mục |
| Retrieval | Kiểm tra truy xuất đoạn tri thức | Kết quả liên quan đến câu hỏi và dữ liệu sản phẩm |
| Chat hỏi đáp | Kiểm tra câu trả lời chatbot | Câu trả lời phù hợp, có căn cứ từ dữ liệu |
| Gợi ý sản phẩm | Kiểm tra tư vấn theo nhu cầu | Danh sách gợi ý phù hợp tiêu chí đầu vào |
| Yêu cầu mua hàng | Kiểm tra luồng nghiệp vụ | Yêu cầu được tạo, cập nhật và phân công đúng |
| Kênh tích hợp | Kiểm tra webhook và binding | Tin nhắn ngoài kênh được ánh xạ về tenant/chatbot |
| Lỗi đầu vào | Kiểm tra validation và lỗi quyền | API trả lỗi rõ ràng, không làm sai dữ liệu |

## 6. Kết quả thử nghiệm retrieval

Kết quả trong `chatbot/eval/results-summary.md` sử dụng 48 câu hỏi tiếng Việt trên knowledge base `chatbot/kb/noithatcaco`, top-k bằng 5.

| Chiến lược retrieval | Recall@5 | MRR |
| --- | ---: | ---: |
| Keyword | 0.7917 | 0.7333 |
| Vector | 0.6667 | 0.4639 |
| Hybrid | 0.7917 | 0.6708 |
| Hybrid rerank | 0.7708 | 0.6285 |

## 7. Kết quả thử nghiệm theo nhóm

| Nhóm chức năng | Số test cases | Số test đạt | Nhận xét |
| --- | ---: | ---: | --- |
| Khởi động hệ thống và health check | 2 | 2 | Service phản hồi đúng điểm kiểm tra |
| Quản lý dữ liệu sản phẩm | 3 | 3 | Dữ liệu được lưu theo tenant và convention API |
| Xử lý/import dữ liệu sản phẩm | 3 | 3 | KB tạo được tài liệu, chunks và chỉ mục |
| Truy xuất thông tin sản phẩm | 4 | 4 | Retrieval trả đoạn tri thức liên quan |
| Chatbot hỏi đáp sản phẩm | 4 | 4 | Câu trả lời phù hợp dữ liệu sản phẩm |
| Gợi ý/tư vấn sản phẩm | 4 | 4 | Gợi ý bám theo tiêu chí người dùng |
| Tham chiếu thông tin sản phẩm | 2 | 2 | Tham chiếu sản phẩm/giá đúng phạm vi dữ liệu |
| Kiểm tra lỗi đầu vào | 3 | 3 | API trả lỗi rõ ràng khi request không hợp lệ |
| Kiểm tra giao diện demo | 3 | 3 | Luồng web chat và quản trị thao tác được |
| Tích hợp frontend-backend-AI/RAG | 4 | 4 | Request đi qua đủ các lớp và trả response hợp lệ |

## 8. Script và lệnh chạy thử

| Mục tiêu | Lệnh/Vị trí |
| --- | --- |
| Chạy test backend | `mvn test` trong thư mục `multitenant` |
| Chạy test theo class | `mvn -q "-Dtest=ChatbotControllerTest,PurchaseRequestControllerTest" test` |
| Chạy service bằng Docker Compose | `docker compose up -d --build` |
| Xem trạng thái service | `docker compose ps` |
| Xem log backend | `docker compose logs --no-color --tail=200 app` |
| Chạy API AI/RAG độc lập | `uvicorn app.server:app --host 0.0.0.0 --port 8000` trong thư mục `chatbot` |
| Kiểm tra retrieval | Script và dữ liệu trong `chatbot/eval` |

## 9. Tiêu chí đánh giá

| Tiêu chí | Cách đánh giá |
| --- | --- |
| Tính đúng dữ liệu | Câu trả lời và API response khớp dữ liệu sản phẩm |
| Mức độ phù hợp | Gợi ý đáp ứng nhu cầu, ngân sách và tiêu chí người dùng |
| Khả năng retrieval | Recall@5, MRR và kiểm tra thủ công đoạn tri thức liên quan |
| Tính ổn định API | API trả response đúng status code và schema |
| Xử lý lỗi | Request sai được phản hồi bằng lỗi rõ ràng |
| Tích hợp hệ thống | Frontend, backend, database và AI/RAG service hoạt động xuyên suốt |

## 10. Tài liệu liên quan

- `docs/C3_TEST_CASES_AND_RESULTS.md`: danh sách test cases và kết quả thử nghiệm chi tiết.
- `docs/API_DOCUMENTATION.md`: endpoint, request và response.
- `docs/DEPLOYMENT_GUIDE.md`: triển khai và kiểm tra sau triển khai.
- `chatbot/eval/results-summary.md`: kết quả đánh giá retrieval.

