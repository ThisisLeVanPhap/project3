# R.4 Hướng dẫn người dùng cuối

## 1. Mục đích

Tài liệu này hướng dẫn người dùng cuối sử dụng web chat và general chat để hỏi đáp, tra cứu và nhận gợi ý sản phẩm nội thất.

## 2. Truy cập hệ thống

| Giao diện | URL mẫu | Mục đích |
| --- | --- | --- |
| Web chat theo tenant | `<SERVER_PUBLIC_URL>/chat` | Hỏi đáp và tư vấn sản phẩm nội thất |
| General chat | `<SERVER_PUBLIC_URL>/chat/general` | Chat thử nghiệm và kiểm tra phản hồi chung |

## 3. Hỏi đáp thông tin sản phẩm

1. Mở trang web chat.
2. Nhập câu hỏi về sản phẩm nội thất.
3. Nhấn gửi hoặc dùng phím Enter theo giao diện.
4. Đọc câu trả lời và các thông tin sản phẩm được hệ thống tham chiếu.
5. Tiếp tục đặt câu hỏi theo ngữ cảnh nếu cần làm rõ.

Ví dụ câu hỏi:

- `Có mẫu bàn ăn nào phù hợp căn hộ nhỏ không?`
- `Ghế sofa nào có chất liệu dễ vệ sinh?`
- `Tủ giày kích thước nhỏ có những lựa chọn nào?`
- `Sản phẩm nào phù hợp phòng khách phong cách tối giản?`

## 4. Nhận gợi ý sản phẩm

Người dùng nên mô tả rõ nhu cầu để chatbot đưa ra gợi ý phù hợp:

| Tiêu chí | Ví dụ |
| --- | --- |
| Loại sản phẩm | Bàn ăn, sofa, giường, tủ quần áo, tủ giày |
| Không gian sử dụng | Phòng khách, phòng ngủ, căn hộ nhỏ, văn phòng |
| Ngân sách | Dưới 5 triệu, khoảng 10 triệu, phân khúc cao cấp |
| Chất liệu | Gỗ, nỉ, da, kim loại, vật liệu dễ vệ sinh |
| Phong cách | Tối giản, hiện đại, Bắc Âu, sang trọng |

Ví dụ:

`Tôi cần một bộ bàn ăn cho căn hộ 60m2, phong cách hiện đại, ngân sách khoảng 8 triệu.`

## 5. Tham chiếu và so sánh thông tin sản phẩm

Người dùng có thể yêu cầu chatbot so sánh hoặc tham chiếu thông tin khi dữ liệu sản phẩm có thuộc tính phù hợp.

Ví dụ:

- `So sánh hai mẫu sofa có giá dưới 12 triệu.`
- `Mẫu bàn ăn nào phù hợp hơn cho gia đình 4 người?`
- `Sản phẩm nào có giá tốt hơn trong nhóm tủ giày?`

## 6. Gửi nhu cầu mua hàng

Khi muốn được tư vấn tiếp, người dùng cung cấp thông tin nhu cầu và liên hệ theo yêu cầu của giao diện hoặc theo hướng dẫn trong hội thoại.

Thông tin thường dùng:

- Tên hoặc cách xưng hô.
- Số điện thoại hoặc kênh liên hệ.
- Sản phẩm quan tâm.
- Nhu cầu, ngân sách, khu vực hoặc thời gian tư vấn.

## 7. Sử dụng general chat

General chat dùng cho tình huống kiểm tra phản hồi chung:

1. Mở `<SERVER_PUBLIC_URL>/chat/general`.
2. Nhập câu hỏi hoặc yêu cầu tư vấn.
3. Kiểm tra câu trả lời, độ phù hợp và khả năng duy trì ngữ cảnh.

## 8. Lưu ý khi đặt câu hỏi

| Tình huống | Cách nhập hiệu quả |
| --- | --- |
| Câu hỏi quá ngắn | Bổ sung loại sản phẩm hoặc nhu cầu cụ thể |
| Cần gợi ý theo ngân sách | Ghi rõ khoảng giá mong muốn |
| Cần chọn theo không gian | Ghi rõ phòng/kích thước/cách sử dụng |
| Cần tham chiếu giá | Nêu rõ nhóm sản phẩm hoặc tên sản phẩm |
| Câu trả lời không đúng ý | Hỏi tiếp với tiêu chí cụ thể hơn |

## 9. Lỗi thường gặp

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
| --- | --- | --- |
| Trang chat không mở được | URL server/ngrok không hợp lệ hoặc service backend không chạy | Kiểm tra lại URL truy cập trong tài liệu server access |
| Chatbot trả lỗi kết nối | Runtime AI/RAG không phản hồi hoặc quá tải | Gửi lại câu hỏi sau ít phút hoặc báo người vận hành |
| Câu trả lời thiếu thông tin | Dữ liệu sản phẩm không có thuộc tính được hỏi | Hỏi theo sản phẩm khác hoặc bổ sung tiêu chí |
| Không gửi được yêu cầu mua hàng | Thiếu thông tin liên hệ hoặc form không hợp lệ | Kiểm tra lại các trường thông tin bắt buộc |
