# Demo Manual Checklist

## Chuẩn bị

- [ ] Docker services running: `docker compose ps` → 3 containers Up
- [ ] Backend reachable: `curl http://localhost:8080/api/login` → 405
- [ ] FastAPI ready: `curl http://localhost:8000/healthz` → ready=true
- [ ] Admin login: `admin/admin123` → role PLATFORM_ADMIN

## 10 bước kiểm tra chính

### 1. Source Registry
**Bước:** Product Datasets → Source Registry → Load sources
**Kỳ vọng:** Table hiển thị source, có nút "Use in crawl job"

### 2. Crawl Job
**Bước:** Crawl & Materialize Job → nhập gotrangtri, maxUrls=2 → Start Job → Load jobs
**Kỳ vọng:** Job QUEUED → SUCCESS, datasetId xuất hiện

### 3. Dataset
**Bước:** Load datasets → tìm dataset (gotrangtri-20260610 hoặc dataset mới)
**Kỳ vọng:** Product count + Chunks + Quality badge

### 4. Artifact
**Bước:** Chọn dataset → Artifacts
**Kỳ vọng:** Artifact READY, có nút Bind + Import General

### 5. Bind Tenant
**Bước:** Chọn tenant → Bind artifact → Confirm
**Kỳ vọng:** activeKbVersionId set, kbDir legacy fallback

### 6. Import General
**Bước:** Click Import General → Confirm → Refresh Quality Dashboard
**Kỳ vọng:** general_products tăng (hoặc idempotent), import_run tạo

### 7. Quality Dashboard
**Bước:** Product Datasets → Data Quality Dashboard → Refresh
**Kỳ vọng:** totalProducts=6070, price≈99%, category≈85%, material≈65%, dimensions≈76%

### 8. General Compare
**Bước:** Chat "gợi ý sofa vải" mode=general_compare
**Kỳ vọng:** 3-5 sản phẩm, có giá/nguồn/lý do, không phone/lead

### 9. Market Price
**Bước:** Chat "sofa giá 8tr có hợp lý không?" mode=market_price
**Kỳ vọng:** Có min/p25/median/p75/max, sampleCount, confidence

### 10. Tenant Sales
**Bước:** Chat "tôi muốn mua tủ quần áo" mode=tenant_sales (tenant có active KB)
**Kỳ vọng:** Sản phẩm từ KB tenant, hỏi thêm nhu cầu

## Eval Scripts
```bash
python scripts/eval/run_all_eval_scenarios.py
```
**Kỳ vọng:** 29 pass, 0 fail, overall PASS

## Lightweight Deploy
```bash
docker compose exec chatbot-api python3 -c "import torch"
# ModuleNotFoundError (expected — torch không cài mặc định)
```

## VPS checklist
- [ ] INTERNAL_API_SECRET set cho backend + chatbot-api
- [ ] INSTALL_LOCAL_AI=false (mặc định)
- [ ] docker compose up -d --build
- [ ] Eval scripts PASS
- [ ] Memory < 1GB
