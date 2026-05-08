# Vietnamese Buyer Progress Summary

## 1. Retrieval Improvements

### Before

- Policy queries were already usable, but product and design-style retrieval were too broad.
- Compact-apartment queries could drift toward generic company/about content.
- Repeated footer, support, popup, and menu boilerplate reduced snippet quality.

### After

- KB cleaning now removes obvious repeated footer/support/menu noise earlier in the pipeline.
- The curated KB now includes stronger pages for:
  - compact sofa / small-room guidance
  - apartment-friendly sofa content
  - interior-design service content for chung cu queries
- The baseline retriever now applies simple Vietnamese intent boosts for:
  - can ho nho / chung cu / gon / hien dai / thiet ke
  - thanh toan / giao hang / doi tra

### Current Result Snapshot

- `toi can sofa gon cho can ho nho`
  - top result now comes from the dedicated `mau-sofa-phong-khach-nho` guide
- `thiet ke noi that chung cu hien dai`
  - top result now comes from the dedicated `thiet-ke-noi-that-chung-cu` service page
- `chinh sach thanh toan`, `giao hang`, and `doi tra`
  - top results consistently land on the correct policy pages

Source artifact:
- [retrieval-regression.json](/F:/20251/prj3/chatbot/kb/noithatcaco/retrieval-regression.json)

## 2. Product / Demo Improvements

- The Vietnamese buyer flow now supports a realistic path from chat advice to purchase-request confirmation.
- `CONFIRM` now returns clearer Vietnamese confirmation messaging instead of a generic handoff.
- Purchase-request creation is guarded so incomplete or fallback-chat conversations do not create low-quality rows.
- `GET /api/purchase-requests`
  - remains tenant-scoped
  - supports optional `status` filtering
  - returns newest records first
- Demo/testing docs now include:
  - a short product demo checklist
  - shared sample payloads
  - a minimal Postman collection for the real Spring Boot contract

Supporting docs:
- [testing.md](/F:/20251/prj3/multitenant/docs/testing.md)
- [api-contract.md](/F:/20251/prj3/multitenant/docs/api-contract.md)

## 3. Buyer Run Snapshot

Sample run summary from the 30-turn Vietnamese buyer script:

- total turns: 30
- successful turns: 29
- timeout count: 1
- average response time: 91.12s
- median response time: 44.06s
- highest latency: 1393.31s

Source artifact:
- [vietnamese_buyer_20260327_142139.summary.json](/F:/20251/prj3/chatbot/out/conversation_runs/vietnamese_buyer_20260327_142139.summary.json)

## Reuse Notes

- Use section 1 as a short before/after retrieval slide.
- Use section 2 as a product demo progress summary.
- Use section 3 as a concrete run snapshot in the report appendix or demo backup notes.
