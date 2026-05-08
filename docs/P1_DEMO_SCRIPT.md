# P1 Demo Script - Video giữa kỳ

Thời lượng mục tiêu: khoảng 6 phút 30 giây.  
Trọng tâm: chatbot tư vấn/gợi ý sản phẩm nội thất dùng RAG, gọi model, lưu hội thoại và tạo yêu cầu mua hàng cho tenant xử lý.

## Chuẩn bị trước khi quay

- Backend đã chạy tại `http://localhost:8080`.
- Đã pre-warm general chat và tenant chat để tránh chờ model quá lâu khi quay.
- Đã có tenant, chatbot và KB đúng môi trường chạy.
- TODO: thay `TODO_TENANT_ID` và `TODO_CHATBOT_ID` bằng dữ liệu thật trước khi quay.
- TODO: đăng nhập tenant trong browser trước khi mở tenant chat, vì `/api/chat/**` hiện cần session.
- TODO: chuẩn bị sẵn một purchase request mẫu trong DB nếu luồng live không tạo request kịp trong thời gian quay.

## Bảng kịch bản

| Thời lượng | Màn hình/thao tác | Nội dung thuyết minh | Kết quả cần hiện ra |
|---|---|---|---|
| 0:00 - 0:25 | Mở `http://localhost:8080/` hoặc màn hình login. Có thể lướt nhanh `docker compose ps` nếu quay cả terminal. | “Đây là hệ thống chatbot tư vấn nội thất cho nhiều cửa hàng. Người mua có thể hỏi đáp sản phẩm, nhận gợi ý theo nhu cầu, và khi có ý định mua thì hệ thống tạo yêu cầu để nhân viên xử lý.” | Trang hệ thống mở được. Nếu show terminal, `postgres` và `app` đang running. |
| 0:25 - 0:55 | Mở nhanh màn hình hoặc slide kiến trúc ngắn. Nếu không có slide, mở `/admin` hoặc runbook và chỉ vào các thành phần. | “Kiến trúc gồm backend Spring Boot quản lý tenant, hội thoại và purchase request; Python AI service xử lý chat, truy xuất knowledge base theo tenant; PostgreSQL lưu tenant, chatbot, conversation và yêu cầu mua hàng; KB chứa dữ liệu sản phẩm/chính sách.” | Người xem thấy 4 thành phần: backend, AI/RAG service, database, knowledge base. |
| 0:55 - 1:20 | Vào `/login`, đăng nhập platform admin `admin` / `admin123`, chuyển tới `/admin`. | “Đầu tiên là vai trò platform admin. Admin dùng để kiểm tra tenant và dữ liệu cấu hình demo.” | Login thành công, UI `/admin` hiện ra. |
| 1:20 - 1:45 | Trong `/admin`, mở danh sách tenants. Nếu dùng API/terminal, show `GET /api/admin/tenants`. | “Mỗi cửa hàng là một tenant riêng, có API key và đường dẫn KB riêng. Demo này dùng tenant đã chuẩn bị với KB nội thất.” | Danh sách tenant hiện ra, có tenant demo. `kbDir` trỏ tới `chatbot/kb/noithatcaco` hoặc `/opt/app/chatbot/kb/noithatcaco`. |
| 1:45 - 2:15 | Logout admin, login tenant admin. Mở `/tenant`, bấm load chatbot hoặc load tenant ops, load KB Source URLs. | “Ở phía tenant, quản trị viên xem chatbot, nguồn dữ liệu KB và trạng thái vận hành. KB được build từ các URL nguồn và các file `chunks.jsonl`, `index.json`.” | Tenant UI hiện tenant admin. Khu vực KB Source URLs hoặc Tenant Ops có dữ liệu. Không có lỗi `kb_dir is not configured`. |
| 2:15 - 2:35 | Mở tenant chat: `http://localhost:8080/chat?tenantId=TODO_TENANT_ID&chatbotId=TODO_CHATBOT_ID`. | “Bây giờ chuyển sang trải nghiệm người dùng. Đây là cửa sổ chat gắn với tenant và chatbot cụ thể, nên câu trả lời sẽ dùng KB của tenant này.” | Chat UI mở được, có conversation mới hoặc danh sách hội thoại. |
| 2:35 - 3:10 | Nhập câu hỏi sản phẩm: `Tôi muốn tìm sofa cho phòng khách nhỏ. Có mẫu nào phù hợp, dễ vệ sinh và bền không?` | “Người mua hỏi bằng ngôn ngữ tự nhiên. Backend lưu hội thoại, gọi AI service, AI service truy xuất knowledge base rồi sinh câu trả lời.” | Assistant trả lời được, không báo lỗi model. Câu trả lời nên nhắc sản phẩm/tiêu chí phù hợp, ví dụ sofa gọn, dễ vệ sinh, bền, phù hợp phòng khách nhỏ. |
| 3:10 - 3:55 | Nhập nhu cầu chi tiết: `Phòng khách khoảng 18m2, nhà có trẻ nhỏ, tôi thích màu trung tính, phong cách hiện đại, ngân sách khoảng 10 triệu. Bạn gợi ý 2 lựa chọn phù hợp nhất.` | “Không chỉ hỏi đáp, chatbot còn tư vấn theo ràng buộc: diện tích, ngân sách, phong cách và bối cảnh sử dụng. Đây là phần gợi ý sản phẩm theo nhu cầu.” | Assistant trả lời theo dạng tư vấn/gợi ý. Kết quả mong đợi có 2 lựa chọn hoặc nhóm lựa chọn, giải thích vì sao phù hợp với phòng nhỏ, trẻ nhỏ, màu trung tính và ngân sách. |
| 3:55 - 4:25 | Nhập câu hỏi follow-up: `Chính sách giao hàng hoặc bảo hành của cửa hàng như thế nào?` | “Người mua có thể hỏi thêm thông tin chính sách. Với RAG, hệ thống ưu tiên thông tin trong KB thay vì trả lời hoàn toàn chung chung.” | Assistant trả lời về giao hàng/bảo hành/chính sách nếu KB có dữ liệu. Nếu KB không đủ, câu trả lời nên nói chưa đủ thông tin thay vì bịa. |
| 4:25 - 5:10 | Tiếp tục chat để tạo yêu cầu mua hàng. Nhập lần lượt: `Tôi chọn phương án bạn gợi ý. Tên tôi là Nguyễn Văn A, số điện thoại 0912345678, địa chỉ 123 Nguyễn Trãi, Quận 1, TP.HCM.` Sau khi assistant hỏi/chốt, nhập: `Tôi xác nhận mua, bạn tạo yêu cầu giúp tôi.` | “Khi người mua có ý định mua, chatbot thu thập tên, số điện thoại và địa chỉ. Sau bước xác nhận, backend chuyển thông tin hội thoại thành purchase request cho nhân viên.” | Mong đợi assistant trả lời đã ghi nhận yêu cầu mua hàng. Nếu luồng live chưa tới bước chốt, chuyển sang request mẫu đã chuẩn bị để tiếp tục demo. |
| 5:10 - 5:45 | Mở `/tenant/purchase-requests`. Bấm refresh nếu cần. | “Đây là màn hình vận hành của tenant. Yêu cầu mua hàng từ hội thoại được đưa vào danh sách để nhân viên tiếp nhận.” | Bảng purchase request hiện request mới hoặc request mẫu, trạng thái `NEW`, có tên khách, số điện thoại, địa chỉ. |
| 5:45 - 6:15 | Tenant member hoặc tenant admin thao tác `Claim`. Nếu là tenant admin, có thể chọn member và `Reassign`. Sau đó đổi trạng thái sang `CONTACTED` hoặc `COMPLETED` bằng API/UI nếu đã có control. | “Nhân viên có thể nhận xử lý, quản trị viên có thể phân công lại, và trạng thái request được cập nhật theo tiến độ chăm sóc khách hàng.” | Request có assignee hoặc trạng thái được cập nhật. Không hiện lỗi phân quyền. |
| 6:15 - 6:35 | Quay lại `/tenant` bấm load Tenant Ops, hoặc platform admin mở `/api/ops/benchmark-summary` nếu đã chuẩn bị. | “Ngoài luồng chat, hệ thống còn có thông tin vận hành như runtime AI, trạng thái KB và số lượng yêu cầu mua hàng.” | Tenant Ops/benchmark/runtime trả dữ liệu. Có thể thấy trạng thái KB, runtime hoặc số lượng request. |
| 6:35 - 6:55 | Kết thúc tại màn hình chat và purchase request. | “Tóm lại, demo đã thể hiện: quản trị tenant và KB, chatbot hỏi đáp sản phẩm, gợi ý theo nhu cầu, tạo purchase request từ hội thoại và tenant xử lý yêu cầu mua hàng. Đây là luồng chính của hệ thống tư vấn nội thất dùng RAG và gọi model.” | Video kết thúc với hai bằng chứng chính: câu trả lời chat và purchase request trong tenant UI. |

## Dữ liệu mẫu nên copy sẵn

Tenant chat URL:

```text
http://localhost:8080/chat?tenantId=TODO_TENANT_ID&chatbotId=TODO_CHATBOT_ID
```

Câu hỏi sản phẩm:

```text
Tôi muốn tìm sofa cho phòng khách nhỏ. Có mẫu nào phù hợp, dễ vệ sinh và bền không?
```

Câu gợi ý theo nhu cầu:

```text
Phòng khách khoảng 18m2, nhà có trẻ nhỏ, tôi thích màu trung tính, phong cách hiện đại, ngân sách khoảng 10 triệu. Bạn gợi ý 2 lựa chọn phù hợp nhất.
```

Câu hỏi chính sách:

```text
Chính sách giao hàng hoặc bảo hành của cửa hàng như thế nào?
```

Thông tin tạo yêu cầu mua hàng:

```text
Tôi chọn phương án bạn gợi ý. Tên tôi là Nguyễn Văn A, số điện thoại 0912345678, địa chỉ 123 Nguyễn Trãi, Quận 1, TP.HCM.
```

Xác nhận mua:

```text
Tôi xác nhận mua, bạn tạo yêu cầu giúp tôi.
```

## Ghi chú khi quay

- Không quay lúc model đang cold start; hãy gửi thử một câu trước khi bắt đầu ghi hình.
- Không dùng `/api/chat/**` bằng API key thuần trong video; dùng browser đã login tenant.
- Nếu chatbot chưa tạo request đúng lúc, nói ngắn: “Đây là request được tạo từ hội thoại đã chuẩn bị trước” rồi mở `/tenant/purchase-requests`.
- Không để lộ API key thật, token webhook hoặc thông tin nhạy cảm trên màn hình.

