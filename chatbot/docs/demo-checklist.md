# Demo Checklist

## Setup Prerequisites
- [ ] Chatbot server running on `localhost:8000`
- [ ] `KB_DIR` environment set to a tenant KB (e.g., `chatbot/kb/castlery`)
- [ ] `price_reference.json` exists in `chatbot/kb/`
- [ ] Two bots created: one with `mode=tenant_sales`, one with `mode=general_consumer`
- [ ] Use Swagger UI at `http://localhost:8000/docs` or curl commands

---

## 1. Tenant Sales - Full Purchase Flow

**Prerequisite:** Bot with `mode="tenant_sales"`

**Action:**
```bash
POST /chat
{
  "message": "I'm looking for a sofa for my living room. My budget is around $2000.",
  "conversation_id": "demo1",
  "tenant_id": "castlery",
  "mode": "tenant_sales"
}
```

**Expected Observable Results:**
- Response mentions the $2000 budget explicitly
- Response asks about style preference (modern vs classic)
- Response suggests 2-3 seater sofas
- Response time: < 3 seconds (LLM inference)

**Pass/Fail Check:**
- [ ] PASS: Response acknowledges budget AND asks clarifying question about style/features
- [ ] FAIL: No budget mention OR no follow-up question OR generic response

---

## 2. General Consumer - General Advice

**Prerequisite:** Bot with `mode="general_consumer"`

**Action:**
```bash
POST /chat
{
  "message": "How do I choose the right sofa size for my small living room?",
  "conversation_id": "demo2",
  "tenant_id": "castlery",
  "mode": "general_consumer"
}
```

**Expected Observable Results:**
- Response gives practical sizing advice
- Response mentions measurements (e.g., "60-72 inches", "walkway space")
- Response asks about dimensions OR suggests next steps
- NO sales pressure (no "buy now", "purchase", "order" urgency)
- Response time: < 2 seconds

**Pass/Fail Check:**
- [ ] PASS: Helpful advice, consultative tone, no hard sell
- [ ] FAIL: Aggressive sales language OR response about purchase flow stages

---

## 3. Price Range Query

**Prerequisite:** `price_reference.json` loaded

**Action:**
```bash
POST /chat
{
  "message": "What is the typical price range for dining tables?",
  "conversation_id": "demo3",
  "tenant_id": "castlery",
  "mode": "general_consumer"
}
```

**Expected Observable Results:**
- Response time: < 500ms (rule-based early exit)
- Response contains "USD 400-4000" and "average of around USD 2000"
- Response JSON has `"model": "price_ref"`
- No LLM processing in logs

**Pass/Fail Check:**
- [ ] PASS: Fast response (< 1s) AND contains exact range from price_reference.json AND model=price_ref
- [ ] FAIL: Slow response (LLM generated) OR range doesn't match data file

---

## 4. Price Comparison - Below Average (Low)

**Prerequisite:** `price_reference.json` loaded

**Action:**
```bash
POST /chat
{
  "message": "Is $800 a good price for a sofa?",
  "conversation_id": "demo4",
  "tenant_id": "castlery",
  "mode": "general_consumer"
}
```

**Expected Observable Results:**
- Response contains "$800" (user's price)
- Response contains "below the typical market average" OR "below average" OR "low"
- Response mentions sofa range "USD 500-5000" and average "USD 2500"
- Response time: < 500ms

**Pass/Fail Check:**
- [ ] PASS: Contains user price, classification "below average", and correct range/avg
- [ ] FAIL: No price comparison OR wrong classification (normal/high)

---

## 5. Price Comparison - Above Average (High with VND Conversion)

**Prerequisite:** `price_reference.json` loaded

**Action:**
```bash
POST /chat
{
  "message": "Is 4 triệu VND reasonable for a bed?",
  "conversation_id": "demo5",
  "tenant_id": "castlery",
  "mode": "general_consumer"
}
```

**Expected Observable Results:**
- Response converts 4 triệu VND to ~$160 USD (4,000,000 ÷ 25,000 = 160)
- Response contains "below the typical market average" OR "below average" OR "low"
- Response mentions bed range "USD 600-6000" and average "USD 3000"
- 160 USD is far below 3000 average → classification **below average** (160/3000 ≈ 0.05 < 0.7)

**Pass/Fail Check:**
- [ ] PASS: Shows converted USD value (~160) AND correct classification "below average"
- [ ] FAIL: Shows raw VND without conversion OR wrong classification

---

## Quick Verification Commands

```bash
# Check price reference loaded
curl http://localhost:8000/chat | grep -i price

# Test all scenarios sequentially
for s in 1 2 3 4 5; do
  echo "=== Scenario $s ==="
  curl -s -X POST http://localhost:8000/chat \
    -H "Content-Type: application/json" \
    -d "$(cat docs/demo-scenarios.md | grep -A5 \"$s.\" | tail -n +3 | head -3 | tr '\n' ' ')"
done
```

---

## Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| Price queries hit LLM | Verify `price_reference.json` in parent of `KB_DIR` | Move file to `chatbot/kb/` if `KB_DIR=chatbot/kb/castlery` |
| VND not converting | Check regex matches Vietnamese units | Ensure input contains "triệu", "nghìn", or "k" |
| No Vietnamese reply | Check `is_vietnamese_text()` detection | Include Vietnamese diacritics or common words |
| Slow responses | Check logs for `model=price_ref` | Price guardrail not triggering - verify category in message |
