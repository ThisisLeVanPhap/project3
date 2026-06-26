# Hướng dẫn kiểm tra thủ công hệ thống Multi-tenant AI Shopping Assistant

## 1. Mục tiêu kiểm tra

Tài liệu này hướng dẫn kiểm tra 3 năng lực chính của hệ thống:

1. **Tenant Sales Assistant** — chatbot bán hàng riêng từng tenant, dùng active KB version.
2. **General Consumer Assistant** — so sánh/gợi ý sản phẩm từ nhiều nguồn public (general_products).
3. **Market Price Insight Assistant** — tham khảo giá thị trường, median/range/confidence.

Và các phần quản trị:
- Source Registry, Crawl/Rebuild Job, Product Dataset, Artifact, Bind Tenant, Import General, Quality Dashboard.

## 2. Chuẩn bị

```bash
# 1. Start services
docker compose up -d

# 2. Kiểm tra services
docker compose ps
# Expected: 3 containers running (app, chatbot-api, postgres)

# 3. Đợi app start
sleep 30

# 4. Kiểm tra health
curl http://localhost:8080/api/login           # Expected: 405 (reachable)
curl http://localhost:8000/healthz             # Expected: ready=true

# 5. Login admin
# Mở browser: http://localhost:8080/admin
# Hoặc dùng API:
curl -s -c /tmp/cookies.txt -X POST http://localhost:8080/api/login \
  -H "Content-Type: application/json" \
  -d '{"name":"admin","code":"admin123"}'
# Expected: ok:true, role:PLATFORM_ADMIN

# 6. Không cần torch/local model
INSTALL_LOCAL_AI=false (mặc định)
```

## 3. Kiểm tra Admin Login

**Bước:**
1. Mở `http://localhost:8080/admin` trên browser.
2. Nhập username `admin`, password `admin123`.

**Expected:**
- Vào được dashboard admin.
- Sidebar hiển thị "Platform Admin".
- Các tab: Dashboard, Tenant Management, Chatbot & Channels, Knowledge Base, Business Data, Operations.

**Lỗi thường gặp:**
- 401 Unauthorized → session hết hạn, login lại.
- 403 Forbidden → tài khoản không phải PLATFORM_ADMIN.

## 4. Kiểm tra Source Registry

**Bước:**
1. Vào **Knowledge Base → Product Datasets**.
2. Mở mục **"Source Registry"**.
3. Click **"Load sources"**.
4. Nếu chưa có source, thêm mới:
   - Source code: `test-source`
   - Root URL: `https://example.com`
   - Sitemap URL: `https://example.com/sitemap.xml`
   - Visibility: chọn **GLOBAL_PUBLIC** (TENANT_BOUND yêu cầu ownerTenantId)
   - Click **Save**.
5. Click **"Use in crawl job"** trên source vừa tạo.

**Expected:**
- Source xuất hiện trong table.
- Click "Use in crawl job" → form Crawl & Materialize Job được fill tự động (sourceCode, sourceName, rootUrl, sitemapUrl, visibility).

**Lưu ý:**
- Không crawl lớn (maxUrls mặc định 100, tối đa 1000).
- TENANT_BOUND yêu cầu ownerTenantId.

## 5. Kiểm tra Crawl & Materialize Job

**Bước:**
1. Trong tab **Product Datasets**, mở mục **"Crawl & Materialize Job"**.
2. Nhập:
   - Source code: `gotrangtri`
   - Sitemap URL: `https://gotrangtri.vn/sitemap.xml`
   - Max URLs: `2`
   - Visibility: `TENANT_BOUND`
   - Build artifact: bỏ chọn
   - Import general: bỏ chọn
3. Click **"Start Job"**.
4. Không chờ — job chạy nền.
5. Click **"Load jobs"** để refresh.

**Expected:**
- Job được tạo với status QUEUED.
- Sau vài giây reload: RUNNING → CRAWL → MATERIALIZE → REGISTER → SUCCESS.
- datasetId hiển thị.
- productCount = 2 (maxUrls=2).

**Nếu FAILED:**
- Xem cột Detail → stage + errorMessage.
- Xem app logs: `docker compose logs app --tail 50`.

## 6. Kiểm tra Product Dataset Registry

**Bước:**
1. Click **"Load datasets"**.
2. Tìm dataset mới tạo hoặc `gotrangtri-20260610` (6070 products).

**Expected:**
- Dataset ID, Source, Status, Products, Chunks, Quality badge.
- Actions: View, Artifacts, Build Artifact, Copy ID, Delete.

**Quality badge:**
- `pass` → xanh
- `warn` → vàng
- `fail` → đỏ

## 7. Kiểm tra Artifact

**Bước:**
1. Chọn dataset có data → click **"Artifacts"**.
2. Xem artifact list.

**Expected:**
- Build tag + short ID.
- Status: READY.
- Chunks count.
- Quality badge.
- Actions: **Bind**, **Import General**, **Copy ID**.

**Ghi chú:**
- Import General chỉ enable khi artifact READY.
- Chi public (GLOBAL_PUBLIC) mới được import general.

## 8. Kiểm tra Bind Tenant / Active KB

**Bước:**
1. Chọn tenant ở Tenant Management (tab Tenants → Select).
2. Quay lại Product Datasets → Artifacts.
3. Click **"Bind"** trên artifact READY.
4. Confirm dialog.
5. Sau bind, reload runtime/KB status nếu cần.

**Expected:**
- tenant.activeKbVersionId được set.
- tenant.kbDir không thay đổi (chỉ legacy fallback).
- Runtime log có evict tenant (load lại KB mới).

**Lưu ý:**
- Chỉ bind được artifact READY.
- Bind sẽ tạo TenantKbVersion mới.
- **tenant.kbDir là legacy fallback; source-of-truth là activeKbVersionId → TenantKbVersion.kbDir.**

## 9. Kiểm tra Import General

**Bước:**
1. Chọn artifact READY.
2. Click **"Import General"**.
3. Confirm dialog.
4. Refresh Quality Dashboard hoặc General Sources.

**Expected:**
- general_sources có source mới.
- general_products tăng (hoặc giữ nguyên — idempotent).
- general_import_runs có import_run mới.
- Nếu import lại artifact đã import → 0 products imported (idempotent).

**Ghi chú:**
- Chỉ import artifact GLOBAL_PUBLIC.
- Import không ảnh hưởng tenant active KB.

## 10. Kiểm tra Data Quality Dashboard

**Bước:**
1. Trong Product Datasets, mở **"Data Quality Dashboard"**.
2. Click **"Refresh"**.

**Expected với gotrangtri:**
- Total products: ~6070
- Sources: 1
- Price coverage: ~99%
- Category coverage: ~85%
- Material coverage: ~65%
- Dimensions coverage: ~76%
- Quality: pass hoặc warn
- Warnings: material/category/dimensions < 80% (nếu có)

**Nếu API lỗi:**
- Kiểm tra trực tiếp: `curl -s -b /tmp/cookies.txt http://localhost:8080/api/admin/general/quality-summary`

## 11. Kiểm tra General Compare

**Bước:**
Gọi FastAPI chat endpoint với mode `general_compare`:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"gợi ý sofa","gen":{"mode":"general_compare","provider":"stub"},"channel":"web"}' \
  | python -X utf8 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reply','')[:400])"
```

**Expected:**
- Trả 3–5 sản phẩm từ general_products.
- Có tên, giá, nguồn, lý do phù hợp.
- **KHÔNG** hỏi số điện thoại.
- **KHÔNG** tạo đơn mua.
- **KHÔNG** dùng tenant KB.

**Thử thêm query:**
- "So sánh vài mẫu tủ quần áo"
- "Bàn làm việc nhỏ giá tốt"
- "Kệ tivi dưới 5 triệu"

## 12. Kiểm tra Market Price

**Bước:**
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"sofa giá 8 triệu có hợp lý không?","gen":{"mode":"market_price","provider":"stub"},"channel":"web"}' \
  | python -X utf8 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reply','')[:500])"
```

**Expected:**
- Có khoảng giá: min/p25/median/p75/max.
- Có sampleCount/sourceCount/confidence.
- Có đánh giá giá 8 triệu.
- **KHÔNG** hỏi số điện thoại.
- **KHÔNG** tạo đơn mua.

**Thử thêm query:**
- "Tủ quần áo gỗ công nghiệp 5 triệu có đắt không?"
- "Bàn làm việc nhỏ tầm bao nhiêu?"

## 13. Kiểm tra Tenant Sales

**Bước:**
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Tôi muốn mua tủ quần áo","tenant_id":"TENANT_UUID","gen":{"mode":"tenant_sales","provider":"stub"},"channel":"web"}' \
  | python -X utf8 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reply','')[:400])"
```

(Thay `TENANT_UUID` bằng UUID tenant có activeKbVersionId — ví dụ tenant `moho`)

**Expected:**
- Trả sản phẩm từ KB tenant.
- Có thể hỏi thêm nhu cầu (kích thước, chất liệu, ngân sách).
- Chỉ tenant_sales mới tạo lead/purchase request.
- `/reset` làm mới context.

**Nếu không có tenant active KB:**
- Kiểm tra trong DB:
  ```sql
  SELECT code, active_kb_version_id FROM tenants WHERE active_kb_version_id IS NOT NULL;
  ```
- Nếu không có tenant active KB → cần bind artifact trước.

## 14. Kiểm tra Eval Scripts

**Bước:**
```bash
cd repo_root
python scripts/eval/run_all_eval_scenarios.py
```

**Expected:**
- General compare: pass (14 test)
- Market price: pass (10 test)
- Tenant sales: pass (5 test)
- Overall: PASS
- Evidence: `tmp/eval/eval_summary.json`

**Nếu FAIL:**
- Kiểm tra file evidence JSON chi tiết.
- Thường do backend/FastAPI không available hoặc INTERNAL_API_SECRET mismatch.

## 15. Kiểm tra Lightweight Deployment

**Bước:**
```bash
# Kiểm tra torch không được cài mặc định
docker compose exec chatbot-api python3 -c "import torch"
# Expected: ModuleNotFoundError: No module named 'torch'

# Kiểm tra memory
docker stats --no-stream
# Expected: tổng ~600MB (app ~400, chatbot-api ~50, postgres ~80)
```

## 16. Kiểm tra bảo mật

**Local dev:**
- INTERNAL_API_SECRET có thể bỏ trống.
- Backend log warning khi start: "INTERNAL_API_SECRET is not configured..."
- Internal endpoints (/api/internal/) vẫn hoạt động.

**VPS/production:**
- **Bắt buộc** set INTERNAL_API_SECRET cho cả backend và chatbot-api.
- Nếu secret configured mà gọi thiếu header → 403 Forbidden.
- FastAPI gửi header `X-Internal-Api-Key` nếu env set.

## 17. Bảng lỗi thường gặp

| Lỗi | Nguyên nhân | Cách xử lý |
|---|---|---|
| 401 API | Chưa login / session hết hạn | Login lại admin |
| Missing tenant header | Endpoint chưa exclude interceptor | Thêm `/api/internal/**` vào WebConfig exclude |
| Internal API 403 | INTERNAL_API_SECRET mismatch | Đồng bộ secret giữa backend và chatbot-api |
| general_compare không ra item | Thiếu general_products hoặc search query | Kiểm tra quality dashboard data |
| market_price no data | Thiếu price/category/material | Kiểm tra coverage trong quality dashboard |
| tenant_sales không load KB | activeKbVersionId null | Bind artifact vào tenant trước |
| Job FAILED | Lỗi crawl/materialize/register | Xem stage + errorMessage → docker compose logs app |
| Import General duplicate | Idempotent OK, không lỗi | Import lại không tăng product count |
| Clipboard không hoạt động | HTTP không hỗ trợ navigator.clipboard | Copy thủ công |

## 18. Checklist nhanh

- [ ] Admin login OK
- [ ] Source Registry tạo được source
- [ ] Crawl job start + SUCCESS
- [ ] Dataset hiển thị count/quality
- [ ] Artifact READY + có nút Bind + Import General
- [ ] Bind tenant thành công
- [ ] Import general thành công
- [ ] Quality dashboard hiển thị coverage đúng
- [ ] General compare trả sản phẩm
- [ ] Market price trả range/confidence
- [ ] Tenant sales trả sản phẩm từ KB
- [ ] Eval scripts 29/29 PASS
- [ ] Docker memory < 1GB
- [ ] INTERNAL_API_SECRET (VPS) đã set
