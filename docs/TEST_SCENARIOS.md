# Test Scenarios - Chatbot Đa Tenant

## Hướng dẫn sử dụng

- Mỗi scenario có thể chuyển thành JSON/CSV để evaluator tự động hóa
- Fields: `id`, `user_message`, `expected_mode`, `expected_behavior`, `pass_criteria`, `should_create_purchase_request`
- Negative tests được phân nhóm riêng để đánh giá robustness

---

## Group A: Tenant Sales (tenant_sales mode)

### A001 - Khởi tạo yêu cầu mua hàng cơ bản
- **user_message**: "Tôi muốn mua một chiếc sofa cho phòng khách."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot chuyển sang stage discover, hỏi thêm thông tin về loại sản phẩm, kích thước, phong cách
- **pass_criteria**: Bot hỏi至少 1 câu về nhu cầu cụ thể, không yêu cầu purchase ngay
- **should_create_purchase_request**: false

### A002 - Cung cấp đầy đủ thông tin sản phẩm
- **user_message**: "Tôi cần sofa chữ L, phong cách hiện đại, màu be, chất liệu vải, ngân sách 15-20 triệu, cho phòng khách 40m2."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot ghi nhận preferences, chuyển sang stage specify hoặc review, tóm tắt lại thông tin
- **pass_criteria**: Bot xác nhận lại các tiêu chí đã cung cấp, không yêu cầu thông tin lặp lại
- **should_create_purchase_request**: false

### A003 - Hỏi về sản phẩm cụ thể
- **user_message**: "Sản phẩm SFG041 còn hàng không? Tôi muốn mua."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot kiểm tra thông tin sản phẩm, hỏi thêm về số lượng, thông tin liên hệ
- **pass_criteria**: Bot phản hồi về tình trạng sản phẩm (còn/không còn/không tìm thấy), yêu cầu phone/name để tạo lead
- **should_create_purchase_request**: false

### A004 - Thu thập thông tin liên hệ
- **user_message**: "Số điện thoại của tôi là 0901234567, tên tôi là Nguyễn Văn A."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot ghi nhận phone và name, xác nhận lại thông tin, hỏi có muốn tạo đơn hàng không
- **pass_criteria**: Bot lưu được phone và name, chuyển sang stage review hoặc close
- **should_create_purchase_request**: false

### A005 - Xác nhận tạo đơn hàng
- **user_message**: "Tôi confirm đặt sản phẩm SFG041, giao hàng trong tuần tới."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot tạo purchase request/lead, xác nhận thông tin đơn hàng, thông báo staff sẽ liên hệ
- **pass_criteria**: Bot tạo purchase request, hiển thị confirm message với thông tin đơn hàng
- **should_create_purchase_request**: true

### A006 - Hỏi về màu sắc và chất liệu
- **user_message**: "Tôi thích sofa màu nâu, chất liệu da thật. Có sản phẩm nào không?"
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot tìm kiếm sản phẩm phù hợp, liệt kê nếu có, hỏi thêm về kích thước và ngân sách
- **pass_criteria**: Bot phản hồi về khả năng đáp ứng màu sắc/chất liệu, tiếp tục thu thập thông tin
- **should_create_purchase_request**: false

### A007 - Thay đổi yêu cầu sau khi đã cung cấp thông tin
- **user_message**: "Thực ra tôi muốn đổi sang phong cách Scandinavian thay vì hiện đại."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot cập nhật preference, xác nhận lại các tiêu chí mới, không reset toàn bộ
- **pass_criteria**: Bot ghi nhận thay đổi, không yêu cầu cung cấp lại toàn bộ thông tin
- **should_create_purchase_request**: false

### A008 - Hỏi về kích thước và không gian
- **user_message**: "Phòng khách nhà tôi chỉ 30m2, sofa cỡ nào hợp?"
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot đề xuất kích thước phù hợp, hỏi thêm về phong cách và ngân sách
- **pass_criteria**: Bot đưa ra recommendation về kích thước, tiếp tục stage discover
- **should_create_purchase_request**: false

### A009 - Hỏi về ngân sách và khuyến mãi
- **user_message**: "Ngân sách của tôi 10 triệu. Có sản phẩm nào phù hợp không? Có khuyến mãi gì không?"
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot tìm sản phẩm trong ngân sách, nếu có khuyến mãi thì thông tin, nếu không có thì nói rõ
- **pass_criteria**: Bot phản hồi về khả năng đáp ứng ngân sách, không bịa khuyến mãi
- **should_create_purchase_request**: false

### A010 - Cancel yêu cầu mua hàng
- **user_message**: "Cancel, tôi không mua nữa."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot xác nhận hủy, reset conversation hoặc hỏi lý do
- **pass_criteria**: Bot không tạo purchase request, tôn trọng quyết định user
- **should_create_purchase_request**: false

### A011 - Hỏi về thời gian giao hàng
- **user_message**: "Tôi cần giao hàng trong 2 ngày. Có thể không?"
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot trả lời về khả năng giao hàng, không khẳng định tuyệt đối, transfer cho staff nếu cần
- **pass_criteria**: Bot không khẳng định chắc chắn delivery timing, đề nghị staff liên hệ
- **should_create_purchase_request**: false

### A012 - Hoàn tất purchase với đầy đủ thông tin
- **user_message**: "Tôi Nguyễn Văn A, số 0901234567, muốn mua sofa SFG041, giao tại địa chỉ 123 đường ABC. Confirm đơn hàng."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot tạo purchase request đầy đủ thông tin: name, phone, product, address
- **pass_criteria**: Bot tạo purchase request với tất cả fields, xác nhận đơn hàng thành công
- **should_create_purchase_request**: true

---

## Group B: General Compare (general_compare mode)

### B001 - So sánh 3 sản phẩm cơ bản
- **user_message**: "So sánh 3 sofa SFG041, SFG040, SFG039 theo giá, chất liệu, kích thước."
- **expected_mode**: general_compare
- **expected_behavior**: Bot liệt kê 3 sản phẩm, so sánh theo từng tiêu chí, ghi rõ missing data
- **pass_criteria**: Bot so sánh ít nhất 3 sản phẩm, không bịa thông tin, có bảng/list rõ ràng
- **should_create_purchase_request**: false

### B002 - So sánh theo phong cách
- **user_message**: "Sự khác biệt giữa sofa phong cách Scandinavian, Industrial và Modern là gì?"
- **expected_mode**: general_compare
- **expected_behavior**: Bot giải thích đặc điểm từng phong cách, so sánh ưu nhược điểm
- **pass_criteria**: Bot cung cấp thông tin so sánh, không bịa đặc điểm không có trong data
- **should_create_purchase_request**: false

### B003 - So sánh vật liệu
- **user_message**: "So sánh sofa gỗ sồi, gỗ công nghiệp và gỗ tự nhiên về độ bền và giá cả."
- **expected_mode**: general_compare
- **expected_behavior**: Bot so sánh từng loại vật liệu, nếu thiếu data thì nói rõ
- **pass_criteria**: Bot so sánh đúng theo data có sẵn, không khẳng định tuyệt đối về độ bền/giá
- **should_create_purchase_request**: false

### B004 - So sánh cho mục đích sử dụng cụ thể
- **user_message**: "Sofa chữ L và sofa đơn, loại nào hợp cho căn hộ 50m2?"
- **expected_mode**: general_compare
- **expected_behavior**: Bot phân tích ưu nhược điểm cho từng loại trong ngữ cảnh căn hộ nhỏ
- **pass_criteria**: Bot đưa ra recommendation dựa trên data/logic, không bịa số liệu
- **should_create_purchase_request**: false

### B005 - So sánh giá cả
- **user_message**: "Sofa da thật và sofa giả da cùng kích thước, chênh lệch giá bao nhiêu?"
- **expected_mode**: general_compare
- **expected_behavior**: Bot so sánh khoảng giá, nếu không có data thì nói chưa có thông tin
- **pass_criteria**: Bot trả về khoảng giá nếu có data, hoặc nói "chưa có dữ liệu" nếu không có
- **should_create_purchase_request**: false

### B006 - So sánh khi thiếu sản phẩm trong data
- **user_message**: "So sánh sofa SFG999 và SFG998, cả 2 đều là sản phẩm mới."
- **expected_mode**: general_compare
- **expected_behavior**: Bot thông báo không tìm thấy sản phẩm trong data, không bịa thông tin
- **pass_criteria**: Bot nói rõ không tìm thấy sản phẩm, không tạo thông tin giả
- **should_create_purchase_request**: false

### B007 - So sánh nhiều tiêu chí phức tạp
- **user_message**: "So sánh 5 sofa theo giá, kích thước, chất liệu, phong cách và phù hợp không gian nào."
- **expected_mode**: general_compare
- **expected_behavior**: Bot tạo bảng so sánh đa tiêu chí, ghi rõ missing fields
- **pass_criteria**: Bot so sánh ít nhất 3 sản phẩm (nếu data hạn chế), bảng có cấu trúc rõ ràng
- **should_create_purchase_request**: false

### B008 - So sánh cho không gian đặc biệt
- **user_message**: "Sofa nào hợp cho văn phòng làm việc, không gian hẹp, cần dễ di chuyển?"
- **expected_mode**: general_compare
- **expected_behavior**: Bot đề xuất sản phẩm phù hợp dựa trên tiêu chí, so sánh ít nhất 2-3 lựa chọn
- **pass_criteria**: Bot đưa ra recommendation có lý do, so sánh các lựa chọn
- **should_create_purchase_request**: false

### B009 - So sánh khi user chỉ cung cấp 1 sản phẩm
- **user_message**: "So sánh sofa SFG041 với các sản phẩm khác cùng phân khúc."
- **expected_mode**: general_compare
- **expected_behavior**: Bot tìm sản phẩm cùng phân khúc để so sánh, nếu không có thì nói rõ
- **pass_criteria**: Bot tìm được至少 2 sản phẩm để so sánh, hoặc nói không có sản phẩm tương đương
- **should_create_purchase_request**: false

### B010 - So sánh với budget constraint
- **user_message**: "So sánh các sofa dưới 15 triệu, ưu tiên chất liệu tốt."
- **expected_mode**: general_compare
- **expected_behavior**: Bot lọc sản phẩm theo budget, so sánh theo chất liệu
- **pass_criteria**: Bot liệt kê sản phẩm trong budget, so sánh có trọng tâm
- **should_create_purchase_request**: false

### B011 - So sánh khi data không đủ cho tất cả tiêu chí
- **user_message**: "So sánh sofa theo giá, màu sắc, kích thước, warranty và shipping time."
- **expected_mode**: general_compare
- **expected_behavior**: Bot so sánh theo data có sẵn, ghi rõ các field missing (warranty, shipping time)
- **pass_criteria**: Bot không bịa warranty/shipping time, nói rõ thiếu data
- **should_create_purchase_request**: false

### B012 - Yêu cầu so sánh không hợp lệ
- **user_message**: "So sánh sofa với giường ngủ."
- **expected_mode**: general_compare
- **expected_behavior**: Bot giải thích không thể so sánh 2 loại sản phẩm khác category, đề xuất so sánh trong cùng category
- **pass_criteria**: Bot không cố so sánh không hợp lý, đưa ra explanation
- **should_create_purchase_request**: false

---

## Group C: Market Price (market_price mode)

### C001 - Khảo giá sản phẩm cụ thể
- **user_message**: "Sofa SFG041 giá 14 triệu có cao bất thường không?"
- **expected_mode**: market_price
- **expected_behavior**: Bot tra cứu khoảng giá thị trường, nhận xét cao/thấp/bình thường
- **pass_criteria**: Bot trả về khoảng giá (nếu có data) hoặc nói chưa đủ dữ liệu, không khẳng định tuyệt đối
- **should_create_purchase_request**: false

### C002 - Hỏi khoảng giá hợp lý
- **user_message**: "Giá sofa gỗ sồi cỡ 2m4 khoảng bao nhiêu là hợp lý?"
- **expected_mode**: market_price
- **expected_behavior**: Bot trả về khoảng giá tham khảo, nêu rõ nguồn dữ liệu
- **pass_criteria**: Bot cung cấp khoảng giá (nếu có data) hoặc nói chưa có thông tin, có cảnh báo nếu là mock data
- **should_create_purchase_request**: false

### C003 - So sánh giá 2 nơi bán
- **user_message**: "Tôi thấy quảng cáo sofa 5 triệu ở bên A, 8 triệu ở bên B. Bên nào đáng tin?"
- **expected_mode**: market_price
- **expected_behavior**: Bot phân tích khoảng giá thị trường, không khẳng định bên nào đúng/sai
- **pass_criteria**: Bot không xác nhận bên nào đúng, chỉ cung cấp khoảng giá tham khảo
- **should_create_purchase_request**: false

### C004 - Hỏi giá cho phân khúc cụ thể
- **user_message**: "Sofa phân khúc trung bình, giá bao nhiêu là bình thường?"
- **expected_mode**: market_price
- **expected_behavior**: Bot trả về khoảng giá cho phân khúc trung bình
- **pass_criteria**: Bot cung cấp khoảng giá (nếu có data) hoặc nói chưa có thông tin cho phân khúc này
- **should_create_purchase_request**: false

### C005 - Hỏi giá khi không đủ nguồn dữ liệu
- **user_message**: "Sofa customization giá thị trường hiện nay là bao nhiêu?"
- **expected_mode**: market_price
- **expected_behavior**: Bot thông báo không có đủ structured price references, không bịa số liệu
- **pass_criteria**: Bot nói rõ "không có đủ dữ liệu", không đưa ra con số giả định
- **should_create_purchase_request**: false

### C006 - Xác nhận giá deal tốt
- **user_message**: "Mức giá 20 triệu cho sofa chữ L có phải deal tốt không?"
- **expected_mode**: market_price
- **expected_behavior**: Bot so sánh với khoảng giá thị trường, nhận xét nếu có data
- **pass_criteria**: Bot nhận xét dựa trên data (cao/thấp/bình thường) hoặc nói chưa có dữ liệu
- **should_create_purchase_request**: false

### C007 - Hỏi giá theo chất liệu
- **user_message**: "Sofa da thật và sofa vải, chênh lệch giá khoảng bao nhiêu?"
- **expected_mode**: market_price
- **expected_behavior**: Bot so sánh khoảng giá 2 loại chất liệu
- **pass_criteria**: Bot cung cấp chênh lệch giá (nếu có data) hoặc nói chưa có thông tin
- **should_create_purchase_request**: false

### C008 - Hỏi giá theo kích thước
- **user_message**: "Sofa 2 chỗ ngồi và 3 chỗ ngồi, chênh lệch giá bao nhiêu?"
- **expected_mode**: market_price
- **expected_behavior**: Bot so sánh khoảng giá theo kích thước
- **pass_criteria**: Bot cung cấp chênh lệch giá (nếu có data) hoặc nói chưa có thông tin
- **should_create_purchase_request**: false

### C009 - Cảnh báo mock/demo data
- **user_message**: "Sofa SFG040 giá 12 triệu có hợp lý không?"
- **expected_mode**: market_price
- **expected_behavior**: Bot trả về khoảng giá, có cảnh báo nếu dùng mock/demo data
- **pass_criteria**: Bot có cảnh báo "mock/demo data" nếu không phải data thật
- **should_create_purchase_request**: false

### C010 - Hỏi giá ngoài phạm vi data
- **user_message**: "Sofa cao cấp 50-100 triệu có đáng đầu tư không?"
- **expected_mode**: market_price
- **expected_behavior**: Bot thông báo phạm vi giá ngoài data hiện có, không khẳng định
- **pass_criteria**: Bot nói rõ không có data cho phân khúc này, không đưa ra recommendation
- **should_create_purchase_request**: false

### C011 - Hỏi giá khi có nhiều nguồn mâu thuẫn
- **user_message**: "Tôi thấy giá sofa SFG041 có chỗ 10 triệu, chỗ 15 triệu, chỗ 20 triệu. Tại sao chênh lệch lớn thế?"
- **expected_mode**: market_price
- **expected_behavior**: Bot giải thích các yếu tố gây chênh lệch giá (chất liệu, size, thương hiệu, v.v.)
- **pass_criteria**: Bot giải thích hợp lý, không khẳng định giá nào đúng
- **should_create_purchase_request**: false

### C012 - Hỏi giá cho sản phẩm không có trong catalog
- **user_message**: "Sofa model XYZ123 giá thị trường khoảng bao nhiêu?"
- **expected_mode**: market_price
- **expected_behavior**: Bot thông báo không tìm thấy sản phẩm trong data, không bịa giá
- **pass_criteria**: Bot nói rõ không tìm thấy sản phẩm, không đưa ra con số giả định
- **should_create_purchase_request**: false

---

## Group D: Negative Tests

### D001 - Thiếu thông tin sản phẩm (tenant_sales)
- **user_message**: "Tôi muốn mua sofa."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot hỏi thêm thông tin cụ thể (loại, size, style, budget), không tạo purchase request ngay
- **pass_criteria**: Bot hỏi至少 2 câu về nhu cầu, không yêu cầu confirm purchase
- **should_create_purchase_request**: false

### D002 - Hỏi ngoài dữ liệu catalog (general_compare)
- **user_message**: "So sánh sofa với tủ lạnh Samsung."
- **expected_mode**: general_compare
- **expected_behavior**: Bot giải thích không thể so sánh sản phẩm khác category
- **pass_criteria**: Bot không cố so sánh, đưa ra explanation hợp lý
- **should_create_purchase_request**: false

### D003 - Hỏi giá thị trường khi không đủ nguồn (market_price)
- **user_message**: "Giá thị trường cho sofa customization handmade là bao nhiêu?"
- **expected_mode**: market_price
- **expected_behavior**: Bot nói rõ không có đủ structured price references
- **pass_criteria**: Bot không bịa con số, nói "không có đủ dữ liệu"
- **should_create_purchase_request**: false

### D004 - Yêu cầu so sánh nhưng chỉ có 1 sản phẩm trong data
- **user_message**: "So sánh sofa SFG999 với các sản phẩm tương tự."
- **expected_mode**: general_compare
- **expected_behavior**: Bot thông báo không tìm thấy sản phẩm SFG999 hoặc không có sản phẩm tương đương
- **pass_criteria**: Bot không bịa sản phẩm giả để so sánh
- **should_create_purchase_request**: false

### D005 - Yêu cầu purchase request khi chưa đủ thông tin (tenant_sales)
- **user_message**: "Tạo đơn hàng cho tôi ngay."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot yêu cầu cung cấp thông tin cần thiết trước (product, contact info, v.v.)
- **pass_criteria**: Bot không tạo purchase request, yêu cầu đủ info trước
- **should_create_purchase_request**: false

### D006 - Hỏi thông tin bảo hành khi không có data
- **user_message**: "Warranty của sofa SFG041 là bao lâu?"
- **expected_mode**: tenant_sales (hoặc general_compare tùy routing)
- **expected_behavior**: Bot thông báo không có thông tin warranty trong data
- **pass_criteria**: Bot không bịa warranty period, đề nghị liên hệ staff
- **should_create_purchase_request**: false

### D007 - Yêu cầu khẳng định delivery timing tuyệt đối
- **user_message**: "Giao hàng trong 3 ngày có chắc không? Confirm đi."
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot không khẳng định chắc chắn delivery timing, đề nghị staff xác nhận
- **pass_criteria**: Bot không nói "chắc chắn" về delivery, transfer cho staff
- **should_create_purchase_request**: false

### D008 - Hỏi refund policy chi tiết
- **user_message**: "Tôi mua rồi không thích được refund không? Bao nhiêu ngày?"
- **expected_mode**: tenant_sales
- **expected_behavior**: Bot thông báo không thể confirm refund policy trong chat, transfer cho staff
- **pass_criteria**: Bot không bịa refund policy, đề nghị staff liên hệ
- **should_create_purchase_request**: false

### D009 - Claude API timeout giả định
- **user_message**: "So sánh sofa SFG041 và SFG040." (khi Claude API timeout)
- **expected_mode**: general_compare
- **expected_behavior**: Bot trả về error message thân thiện, đề nghị retry
- **pass_criteria**: Bot không crash, có fallback/error handling
- **should_create_purchase_request**: false

### D010 - Qwen local fallback timeout giả định (nếu fallback enabled)
- **user_message**: "Tôi muốn mua sofa." (khi Qwen local timeout)
- **expected_mode**: tenant_sales (hoặc fallback error)
- **expected_behavior**: Bot trả về error message hoặc timeout message
- **pass_criteria**: Bot không crash, có timeout handling
- **should_create_purchase_request**: false

### D011 - Nhập lệnh reset
- **user_message**: "/reset" hoặc "new scenario"
- **expected_mode**: system (hoặc current mode)
- **expected_behavior**: Bot reset conversation state, bắt đầu mới
- **pass_criteria**: Bot confirm reset, slots/state được clear
- **should_create_purchase_request**: false

### D012 - Nhập thông tin không liên quan
- **user_message**: "Hôm nay thời tiết thế nào?"
- **expected_mode**: general_compare (hoặc tenant_sales tùy routing)
- **expected_behavior**: Bot thông báo không thể trả lời ngoài phạm vi product consultation
- **pass_criteria**: Bot không cố trả lời, đề nghị hỏi về sản phẩm
- **should_create_purchase_request**: false

---

## Summary

| Group | Số lượng scenario |
|-------|-------------------|
| A - Tenant Sales | 12 |
| B - General Compare | 12 |
| C - Market Price | 12 |
| D - Negative Tests | 12 |
| **Total** | **48** |

---

## Fields cho JSON/CSV Evaluator

```json
{
  "id": "A001",
  "group": "tenant_sales",
  "user_message": "Tôi muốn mua một chiếc sofa cho phòng khách.",
  "expected_mode": "tenant_sales",
  "expected_behavior": "Bot chuyển sang stage discover, hỏi thêm thông tin về loại sản phẩm, kích thước, phong cách",
  "pass_criteria": "Bot hỏi至少 1 câu về nhu cầu cụ thể, không yêu cầu purchase ngay",
  "should_create_purchase_request": false,
  "input_channel": "messenger",
  "expected_response_contains": ["hỏi", "thêm thông tin"],
  "expected_response_not_contains": ["purchase", "confirm đơn hàng"],
  "expected_stage": "discover"
}
```

---

**Created**: 2026-05-20
**Total scenarios**: 48