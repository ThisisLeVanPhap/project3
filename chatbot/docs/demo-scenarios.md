# Demo Scenarios

## 1. Tenant Sales - Full Purchase Flow

**Mode:** `tenant_sales`

**User Message:**
```
I'm looking for a sofa for my living room. My budget is around $2000.
```

**Expected Reply (illustrative):**
```
Great! A $2000 budget gives you good options for a living room sofa. I'd recommend looking at fabric or leather sofas in the 2-3 seater range. They typically offer good comfort and durability.

Would you prefer a modern minimalist style or something more classic?
```

**Demonstrates:**
- Budget slot extraction
- Stage progression (discover → propose)
- Preference elicitation (style, size)
- Sales flow state management

---

## 2. General Consumer - General Advice

**Mode:** `general_consumer`

**User Message:**
```
How do I choose the right sofa size for my small living room?
```

**Expected Reply (illustrative):**
```
For a small living room, measure your space first and leave at least 30 inches for walkways. A 2-seater sofa (60-72 inches wide) or a compact apartment-sized sofa (under 72 inches) works well. Consider sofas with raised legs to create a sense of openness, and lighter colors to make the room feel larger.

Do you have specific dimensions you're working with?
```

**Demonstrates:**
- No sales stages or slots
- Direct grounded response from KB
- Consultative tone without purchase pressure
- Different prompt template than tenant_sales

---

## 3. Price Range Query

**Mode:** Any (`tenant_sales` or `general_consumer`)

**User Message:**
```
What is the typical price range for dining tables?
```

**Expected Reply:**
```
The typical price range for dining tables is USD 400-4000 per piece, with an average of around USD 2000. This falls in the normal range for this category.
```

**Vietnamese:**
```
Phạm vi giá điển hình cho bàn ăn là 400-4000 USD mỗi cái. Trung bình khoảng 2000 USD. Đây là mức giá bình thường cho danh mục này.
```

**Demonstrates:**
- Price reference guardrail early exit
- Category detection from message
- Bilingual response
- `model: "price_ref"` (no LLM latency)

---

## 4. Price Comparison - Below Average (Low)

**Mode:** Any

**User Message:**
```
Is $800 a good price for a sofa?
```

**Expected Reply:**
```
The typical price range for sofas is USD 500-5000 per piece, with an average of USD 2500. A price of USD 800 is below the typical market average, which is below average for this category. However, smaller or basic fabric sofas can be found at this price point if you're working with a tight budget.
```

**Demonstrates:**
- Price extraction from message
- Ratio calculation (800 / 2500 = 0.32 < 0.7 → low)
- Classification: "below average"
- Comparison with market average

---

## 5. Price Comparison - Above Average (High)

**Mode:** Any

**User Message:**
```
Is 4 triệu VND reasonable for a bed? (4 million VND)
```

**Expected Reply:**
```
The typical price range for beds is USD 600-6000 per piece, with an average of USD 3000. A price of USD 160 is below the typical market average, which is below average for this category.
```

**Note:** 4 triệu VND = 4,000,000 VND ÷ 25,000 = 160 USD

**Demonstrates:**
- Vietnamese unit handling (`triệu` → ×1,000,000 → ÷25,000)
- VND to USD conversion
- Correct classification based on converted amount
