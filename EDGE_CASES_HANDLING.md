# Edge Cases Handling

## 1. Off-topic Detection

### Logic Added
- Thêm intent `off_topic` trong `detect_intent()`
- Pattern matching cho các chủ đề không liên quan đến nội thất/mua sắm:
  - Politics, elections
  - Sports (football, etc.)
  - Weather
  - Personal questions (how are you, who are you)
  - Tourism, eating out, drinks
- Khi phát hiện off-topic, hệ thống giữ nguyên stage nhưng LLM được hướng dẫn redirect qua prompt.

### Prompt Instructions
```
OFF-TOPIC & DISENGAGEMENT:
- If user asks about unrelated topics (politics, sports, weather, personal questions), politely redirect: 
  'Mình là trợ lý mua sắm nội thất, mình có thể giúp gì cho bạn về ghế, bàn, tủ hay các sản phẩm khác?'
```

### Example Cases

**Case 1: Weather talk**
```
User: "Hôm nay trời nóng quá"
Bot: "Mình là trợ lý mua sắm nội thất, mình có thể giúp gì cho bạn về ghế, bàn, tủ hay các sản phẩm khác? Bạn đang tìm đồ cho phòng nào?"
```

**Case 2: Personal question**
```
User: "Bạn khỏe không?"
Bot: "Mình là trợ lý tư vấn nội thất, mình có thể giúp gì cho bạn về ghế, bàn, tủ hay các sản phẩm khác? Bạn cần mua gì cho nhà mình?"
```

**Case 3: Politics**
```
User: "Bạn nghĩ về bầu cử sắp tới?"
Bot: "Mình là trợ lý mua sắm nội thất, mình chỉ tập trung vào việc tư vấn sản phẩm nội thất thôi ạ. Bạn có ghế, bàn hay tủ nào cần tư vấn không?"
```

---

## 2. Topic Change Detection (Product Type Switch)

### Logic Added
- Thêm hàm `_handle_topic_change()` trong `server.py`
- Khi `product_type` mới khác với `product_type` cũ:
  - **Consultation mode**: reset `room_type` và `room_size_sqm` vì các slot này liên quan đến phòng cụ thể cho sản phẩm cũ
  - **Sales mode**: không reset thêm (chỉ product_type được update)
- Giữ lại các preferences tổng quát: style, color, material, budget, space

### Code
```python
def _handle_topic_change(existing_slots, new_slots, mode):
    if "product_type" not in new_slots:
        return
    old_product = existing_slots.get("product_type")
    new_product = new_slots["product_type"]
    if old_product and new_product and old_product != new_product:
        if mode == "general_consumer":
            existing_slots.pop("room_type", None)
            existing_slots.pop("room_size_sqm", None)
```

### Example Cases

**Case 1: From sofa to bed (consultation)**
```
Slots before: {product_type: "sofa", room_type: "living_room", room_size_sqm: 15, budget_range: {min:5, max:10}}
User: "Tôi muốn xem giường"
→ product_type becomes "bed"
→ room_type, room_size_sqm are cleared
→ Bot will ask: "Bạn cần giường cho phòng nào? Phòng ngủ hay phòng khách?"
```

**Case 2: From bed to dining table**
```
Slots before: {product_type: "giường", room_type: "phòng ngủ", style_preference: "modern"}
User: "Đổi sang bàn ăn đi"
→ product_type: "bàn ăn"
→ room_type cleared
→ Bot: "Bạn cần bàn ăn cho phòng ăn phải không? Phòng ăn của bạn rộng khoảng bao nhiêu m²?"
```

---

## 3. Disengagement Detection

### Logic Added
- Thêm intent `disengage` trong `detect_intent()`
- Pattern list: "thôi", "thoát", "dừng", "để sau", "khi khác", "bỏ đi", "hủy", "ok rồi", "được rồi", "vậy thôi", "vậy nhé", "tạm biệt", "bye", "goodbye"
- Chỉ kích hoạt nếu tin nhắn ngắn (≤ 4 từ) để tránh false positive
- Khi intent = "disengage", `next_stage()` chuyển trực tiếp sang "handoff"
- LLM được hướng dẫn phản hồi soft close

### Prompt Instructions
```
- If user indicates disengagement ('thôi', 'để sau', 'ok rồi'), respond with a soft close: 
  'Tạm biệt! Nếu sau này cần tư vấn, bạn cứ quay lại nhé.' and transition to handoff.
```

### Example Cases

**Case 1: "Thôi để sau"**
```
User: "Thôi để sau mình xem lại"
Bot: "Tạm biệt! Nếu sau này cần tư vấn, bạn cứ quay lại nhé. Chúc bạn một ngày tốt lành!"
→ Stage chuyển thành handoff
```

**Case 2: "Ok rồi"**
```
User: "Ok rồi"
Bot: "Tạm biệt! Cảm ơn bạn đã ghé thăm. Nếu cần tìm hiểu thêm về nội thất, mình luôn sẵn sàng hỗ trợ."
```

**Case 3: "Để sau đi"**
```
User: "Để sau đi, bận quá"
Bot: "Không sao ạ! Bạn cứ để lại thông tin nếu muốn, hoặc quay lại bất kỳ lúc nào. Tạm biệt!"
```

---

## Summary Table

| Edge Case | Detection Method | System Response | Example Trigger |
|-----------|------------------|----------------|-----------------|
| Off-topic | Regex patterns for unrelated topics | Redirect to furniture context | "Trời nóng quá" |
| Topic change | `product_type` differs from previous | Reset product-specific slots (room_type, room_size_sqm) | "Tôi muốn xem giường" (after sofa) |
| Disengagement | Phrase match + word_count ≤ 4 | Soft close + handoff | "Thôi để sau" |

All edge case handling is integrated into:
- `chatbot/app/sales_flow.py`: `detect_intent()`, `next_stage()`, `build_sales_prefix()`
- `chatbot/app/consultation.py`: `build_consultation_prefix()`
- `chatbot/app/server.py`: `_handle_topic_change()` helper
