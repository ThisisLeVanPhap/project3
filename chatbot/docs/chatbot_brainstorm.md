1.1. Lớp “sản phẩm”: Chatbot cho người bán cần làm được gì?
Gợi ý câu hỏi để tự brainstorm (bạn có thể mở 1 file docs/chatbot_brainstorm.md rồi ghi):

1. Chatbot phải làm được những loại task nào?
- Trả lời câu hỏi về sản phẩm (chất liệu, bảo hành, size,…)
- Gợi ý sản phẩm phù hợp (recommendation)
- Xử lý phản đối: “đắt quá”, “chất lượng có tốt không?”
- Hướng dẫn quy trình mua hàng, ship, thanh toán
- Thu thập thông tin khách (tên, sdt, nhu cầu)
- Chuyển tiếp cho người thật khi cần

2. Ở mỗi kênh (Facebook/Zalo/Web) có gì khác nhau?
- Giới hạn độ dài message
- Format (emoji, xuống dòng, button,…)
- Tốc độ trả lời
- Có cần lưu session dài ngày không?

3. Cần log lại những gì để sau này học phong cách?
- Câu hỏi khách
- Câu trả lời của seller
- Kết quả: có chốt đơn không, khách có hài lòng không
- Tag conversation: “thành công / fail / khách spam / hỏi linh tinh”

Mục tiêu brainstorm phần này: ra 1 file kiểu docs/use_cases.md liệt kê 5–10 use case rõ ràng, mỗi use case có: “input từ khách” – “output mong muốn” – “mô tả flow”.

1.2. Lớp “tùy biến phong cách”: mỗi tenant khác nhau ở đâu?
brainstorm 1 “style profile” cho mỗi người bán, gồm các tham số:
- Ngôn ngữ: vi, en, vi+en
- Tone: vui vẻ / lịch sự / nghiêm túc / “chốt đơn mạnh”
- Mức độ “đẩy hàng”:
+ thấp: chỉ trả lời thông tin
+ trung bình: có gợi ý thêm 1–2 sản phẩm
+ cao: luôn cố upsell/cross-sell

- Độ dài câu trả lời: ngắn gọn / trung bình / giải thích chi tiết
- Cách xưng hô: em – anh/chị; shop – khách; tôi – bạn…
- Emoji: nhiều / ít / không
- Chính sách không được vi phạm:
+ Không hứa hẹn quá mức
+ Không nói sai về bảo hành, đổi trả,…

Khi brainstorm xong, bạn có thể định nghĩa 1 JSON config, ví dụ:
``` json
{
  "name": "Phong cách chốt đơn mạnh",
  "language": "vi",
  "tone": "friendly_aggressive",
  "formality": "medium",
  "emoji_level": "high",
  "max_reply_tokens": 200,
  "sales_push_level": 3
}

```
Sau đó:
+ Prompt/system message sẽ đọc các tham số này.
+ Về sau, LoRA riêng cho từng tenant có thể được fine-tune từ chat log của họ để “học style sâu hơn”.

1.3. Lớp “kỹ thuật AI”: cái gì do prompt, cái gì do fine-tune, cái gì do RAG?
Khi brainstorm, nên tách:

1. Prompt / System message:
- Dùng để áp phong cách: tone, xưng hô, cách trả lời.
- Dùng cho logic “step-by-step sale flow” (hỏi nhu cầu, giới thiệu, xử lý phản đối, chốt…).

2. Fine-tune (LoRA):

- Dùng để:
    + Hiểu sâu domain (ví dụ đồ gỗ: loại gỗ, đặc tính, quy trình bảo quản).
    + Học cách đối thoại bán hàng nói chung (chung cho nhiều tenant).
- Về sau: fine-tune nhỏ per-tenant để học style riêng từ chat log (nếu có).

3. RAG / Vector search (giai đoạn sau):
- Lấy đúng thông tin sản phẩm của từng tenant (tên sản phẩm, mô tả, tồn kho,…).
- AI không cần nhớ “data sản phẩm” trong weights, mà chỉ học cách dùng thông tin đã retrieve.

Bạn có thể tạo 1 bảng trong docs:
“Feature -> Prompt | Fine-tune | RAG | App logic” để phân rạch ròi.