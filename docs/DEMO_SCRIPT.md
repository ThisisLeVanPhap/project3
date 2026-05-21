# Demo Script - Đồ Án Chatbot Đa Tenant

## Thông tin chung

- **Model**: Claude Sonnet 4-6 (Claude API)
- **Provider**: Claude (system-level, env-only config)
- **Runtime**: VPS CPU-only, không load Qwen model
- **3 modes**: `tenant_sales`, `general_compare`, `market_price`

---

## A. Chat Tư Vấn Chung / So Sánh Sản Phẩm (general_compare)

### Mục tiêu demo
Thể hiện khả năng so sánh sản phẩm dựa trên dữ liệu có sẵn, trung lập, không bịa thông tin.

### URL/Kênh sử dụng
- **URL**: `http://SERVER_IP:8080/chat/` hoặc `http://SERVER_IP:8080/general-chat/`
- **Mode**: `general_compare`

### 3-5 câu người dùng nên nhập

1. "So sánh 3 sofa SFG041, SFG040, SFG039 theo giá, chất liệu, kích thước và phong cách."

2. "Giữa sofa chữ L và sofa đơn, loại nào hợp với căn hộ 50m2?"

3. "Sofa phong cách Scandinavian và Industrial khác nhau thế nào?"

4. "Sản phẩm nào trong cửa hàng có giá dưới 10 triệu?"

5. "Tôi muốn sofa cho văn phòng làm việc, có recommendations không?"

### Expected behavior

- Bot so sánh ít nhất 3 sản phẩm theo tiêu chí được hỏi
- Dữ liệu missing được ghi rõ là "chưa có dữ liệu" hoặc "không tìm thấy thông tin"
- **KHÔNG** bịa giá, chất liệu, kích thước
- Kết luận trung lập, không ép mua
- **KHÔNG** tạo purchase request/lead trong mode này

### Điều cần quan quan sát trong log/debug

```
mode=general_compare
stage=compare
data_provider=retrieval (hoặc internal_catalog)
trigger_purchase_request=false
model=claude-sonnet-4-6
```

### Lỗi thường gặp và cách xử lý

| Lỗi | Xử lý |
|-----|-------|
| Bot trả về "không tìm thấy sản phẩm" | Giải thích: đây là mode so sánh dựa trên dữ liệu hiện có, chưa sync full catalog |
| Bot bịa giá sản phẩm | Pause demo, chuyển sang mode khác, note là đang cải thiện data quality |
| Response timeout (>30s) | Check Claude API connectivity, retry |

---

## B. Khảo Giá (market_price)

### Mục tiêu demo
Thể hiện khả năng tham khảo giá thị trường, cảnh báo khi chưa đủ dữ liệu, không khẳng định tuyệt đối.

### URL/Kênh sử dụng
- **URL**: `http://SERVER_IP:8080/price-check/`
- **Mode**: `market_price`

### 3-5 câu người dùng nên nhập

1. "Sofa SFG041 giá 14 triệu có cao bất thường không?"

2. "Giá sofa gỗ sồi cỡ 2m4 khoảng bao nhiêu là hợp lý?"

3. "So sánh giá sofa da thật và sofa giả da cùng kích thước"

4. "Mức giá 20 triệu cho sofa chữ L có phải deal tốt không?"

5. "Tôi thấy quảng cáo sofa 5 triệu, có đáng tin không?"

### Expected behavior

- Bot tra cứu khoảng giá từ nguồn price provider (internal catalog hoặc external)
- Nếu **có đủ dữ liệu**: trả về khoảng giá + nhận xét (cao/thấp/bình thường)
- Nếu **chưa đủ dữ liệu**:
  - Bot nói rõ: "không có đủ structured price references"
  - Bot nói rõ: "không khẳng định giá thị trường tuyệt đối"
  - Bot không bịa số liệu
- **KHÔNG** tạo purchase request/lead trong mode này
- Có cảnh báo nếu dùng mock/demo data

### Điều cần quan sát trong log/debug

```
mode=market_price
stage=price_reference
external_price_refs=X (số lượng price references tìm thấy)
used_mock_price_data=true/false
trigger_purchase_request=false
```

### Lỗi thường gặp và cách xử lý

| Lỗi | Xử lý |
|-----|-------|
| Bot nói "giá thị trường là X triệu" mà không có dữ liệu | Pause demo, giải thích: đang trong quá trình tích hợp external price provider |
| Bot tạo purchase request khi khảo giá | Bug - note lại để fix, không dùng mode này cho demo |
| Response nói "chưa đủ dữ liệu" liên tục | Demo scenario đúng - đang dùng mock data, giải thích rõ với khán giả |

**Lưu ý quan trọng**: Nếu chưa có external price provider thật, bot PHẢI nói "chưa đủ dữ liệu" hoặc "không khẳng định được". Đây là behavior ĐÚNG, không phải bug.

---

## C. Chat Với Shop Qua Messenger/Telegram (tenant_sales)

### Mục tiêu demo
Thể hiện flow tư vấn bán hàng theo stage, thu thập lead, tạo purchase request khi đủ điều kiện.

### URL/Kênh sử dụng
- **Kênh**: Messenger hoặc Telegram
- **Mode**: `tenant_sales`
- **Webhook**: `http://SERVER_IP:8080/api/messenger/webhook` hoặc `/api/telegram/webhook`

### Kịch bản 3-5 câu người dùng

1. "Tôi muốn mua sofa cho phòng khách 40m2, phong cách hiện đại."

2. "Màu be hoặc nâu, chất liệu vải, ngân sách khoảng 15-20 triệu."

3. "Sản phẩm SFG041 còn hàng không? Tôi muốn đặt hàng."

4. (Khi bot hỏi thông tin) "Số điện thoại của tôi là 0901234567, tên là Nguyễn Văn A."

5. "Tôi confirm đặt sản phẩm SFG041, giao hàng trong tuần tới."

### Expected behavior

**Stage progression**:
- `discover` → `discover`: Bot hỏi nhu cầu (product type, size, style)
- `discover` → `specify`: Bot hỏi thêm material, color, budget
- `specify` → `review`: Bot summarize lại preferences
- `review` → `close`: Bot hỏi confirmation để tạo purchase request
- `close` → `close`: Bot confirm lead được tạo, CTA cho staff liên hệ

**Lead capture**:
- Bot thu thập: style, color, material, budget, product_type, space
- Bot yêu cầu phone + name ở stage `review` hoặc `close`
- Bot trigger purchase request khi:
  - Stage = `close`
  - User intent = `confirm`
  - Có đủ constraints (sufficient info)

**Output guardrails**:
- Bot KHÔNG khẳng định delivery timing ("within 3 days", "receive next week")
- Bot KHÔNG khẳng định refund policy
- Bot KHÔNG process payment trực tiếp

### Điều cần quan sát trong log/debug

```
mode=tenant_sales
stage=discover/specify/review/close
slots={style, color, material, budget, product_type, ...}
trigger_purchase_request=true/false (chỉ true khi confirm)
captured_phone=090... (nếu có)
```

### Lỗi thường gặp và cách xử lý

| Lỗi | Xử lý |
|-----|-------|
| Bot skip stages, nhảy thẳng sang ask payment | Demo từ đầu lại, nhấn mạnh flow là progressive |
| Bot yêu cầu payment trực tiếp | Correction: Bot chỉ create purchase request, staff mới xử lý payment |
| Bot không thu thập phone/name | Note lại: đang cải thiện lead capture flow |
| Purchase request không được tạo sau confirm | Bug - check server log, retry demo |

---

## Quick Reference - Command Line Testing

### Test general_compare
```bash
curl -X POST http://SERVER_IP:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"So sánh sofa SFG041 và SFG040","history":[],"gen":{"provider":"claude","mode":"general_compare"}}'
```

### Test market_price
```bash
curl -X POST http://SERVER_IP:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Sofa 14 triệu có cao không","history":[],"gen":{"provider":"claude","mode":"market_price"}}'
```

### Test tenant_sales (qua Messenger webhook)
```bash
curl -X POST http://SERVER_IP:8080/api/messenger/webhook \
  -H "Content-Type: application/json" \
  -d '{"entry":[{"messaging":{"sender":{"id":"USER_ID"},"message":{"text":"Tôi muốn mua sofa"}}}],"object":"page"}'
```

---

## Health Check Before Demo

```bash
# Check container status
docker compose ps

# Check Claude warmup (KHÔNG load Qwen)
docker compose logs chatbot-api --tail=50 | grep warmup
# Expected: [warmup] Claude API available, skipping local model warmup

# Check health
curl http://SERVER_IP:8000/healthz
# Expected: {"status":"ready","ready":true,"cached_pipelines":0,...}
```

---

## Backup Scenarios (nếu main flow fail)

| Main flow fail | Backup |
|----------------|--------|
| Claude API timeout | Retry 2-3 lần, nếu fail → demo stub mode (`CHATBOT_TEST_MODE=1`) |
| Price provider unavailable | Demo general_compare thay vì market_price |
| Messenger webhook không respond | Demo qua web UI general chat thay vì Messenger |
| Database connection error | Restart containers, check postgres health |

---

## Demo Flow Suggested (15 phút)

| Thời gian | Luồng | Mục tiêu |
|-----------|-------|----------|
| 0-2 phút | Giới thiệu hệ thống | Claude provider, 3 modes, VPS CPU-only |
| 2-6 phút | general_compare | So sánh sản phẩm, không bịa dữ liệu |
| 6-10 phút | market_price | Khảo giá, cảnh báo khi thiếu data |
| 10-14 phút | tenant_sales | Chat với shop, tạo lead/purchase request |
| 14-15 phút | Q&A | Ghi nhận câu hỏi |

---

## Notes cho Demo

1. **Luôn bắt đầu bằng health check** để chứng minh hệ thống đang chạy
2. **Giải thích Claude-only** trước khi demo: không load Qwen, startup nhanh
3. **Với market_price**: nhấn mạnh bot KHÔNG bịa giá, nói rõ khi thiếu data
4. **Với general_compare**: nhấn mạnh so sánh trung lập, dựa trên dữ liệu hiện có
5. **Với tenant_sales**: demonstrate progressive flow, lead capture, purchase request trigger
6. **Nếu fail**: retry hoặc chuyển backup scenario, không panick

---

**Created**: 2026-05-20
**Last updated**: 2026-05-20