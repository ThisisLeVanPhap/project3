# Scope tổng thể — Multi-tenant AI Shopping Assistant Platform

Đây là scope nâng cấp cuối cùng, điều chỉnh theo chiến thuật **tận dụng tối đa data_pipeline** kết hợp với **kiến trúc Spring Boot (system-of-record) + FastAPI (AI/RAG/chat behavior)**.

---

## Kiến trúc tổng thể

```
[data_pipeline]                    [Spring Boot]                     [FastAPI]
                                                                   
crawl/sitemap ──> enrichment ──>  product_dataset_registry ──>     general_products DB
     │                │                   │                              │
     │           taxonomy_normalize   build_artifact                 scope_resolver
     │                │                   │                              │
     │           quality_audit       bind_tenant                   GeneralCatalogProvider
     │                │                   │                              │
     └── rag_export ──┘            activeKbVersionId              MarketPriceInsightProvider
                                        │                              │
                                   tenant_chatbot                general_compare_chat
                                   (tenant_sales)                market_price_chat
```

---

## 3 năng lực chính

1. **Tenant Sales Assistant**  
   Trợ lý bán hàng riêng từng tenant, dùng active KB version của tenant đó.

2. **General Consumer Assistant**  
   Trợ lý so sánh sản phẩm nhiều nguồn public, xét toàn bộ allowed corpus.

3. **Market Price Insight Assistant**  
   Tham khảo giá thị trường với median/range/sample/confidence.

---

## Chiến thuật tận dụng data_pipeline

data_pipeline không chỉ là crawler; nó có 7 module quan trọng có thể dùng xuyên suốt:

| Module | Vai trò | Dùng ở đâu |
|---|---|---|
| `enrichment.py` | rule-based infer category, material, dimensions, price | Chatbot query understanding, GeneralCatalogProvider filter |
| `rag_export.py` | product → RAG chunk với structured metadata | Import general từ artifact mới |
| `quality_audit.py` | price/material/dimensions coverage, mojibake, duplicate | Data quality dashboard, quality gate |
| `taxonomy_normalize.py` + profiles | source-aware category normalization | Materialize dataset step |
| `normalize.py` | normalize price/URL/content_hash | Product import pipeline |
| `dedupe_output.py` | dedup by normalized URL, keep best record | Crawl output cleanup |
| `report.py` | crawl stats | Job logs |

**Nguyên tắc:** Không rewrite logic đã có. backend Java gọi Python script/module khi cần xử lý nặng (crawl, materialize, audit). Logic nhẹ (filter, sort, score) làm trong Java/DB.

---

## Phần 1: Những gì đã hoàn thành

### ✅ Data model
- `V36__create_general_products.sql` — general_products (core fields + visibility=GLOBAL_PUBLIC, raw JSONB)
- `V37__create_general_sources_chunks_import_runs.sql` — general_sources, general_product_chunks, general_import_runs
- `V38__create_crawl_materialize_jobs.sql` — crawl_materialize_jobs (async job status)

### ✅ General Data Layer importer
- `GeneralProductImportService` — import artifact READY → general_products + chunks + import_run
- Đã import artifact gotrangtri-20260610: 6070 products, 6070 chunks
- Phase 1E backfill: price 99%, category 85%, material 65%, dimensions 76%

### ✅ Crawl & Materialize async job
- `POST /api/admin/product-datasets/crawl-materialize-jobs` (trả QUEUED ngay)
- `GET /api/admin/product-datasets/crawl-materialize-jobs`
- `GET /api/admin/product-datasets/crawl-materialize-jobs/{jobId}`
- Worker async: crawl → materialize dataset folder → quality audit → auto-register ProductDataset

### ✅ Lightweight deployment
- Default build không cài torch/transformers/accelerate
- Lazy import model_loader.py
- Image size tiết kiệm ~900MB

### ✅ Structured fields backfill
- 6070 external_product_id (doc_id), 6070 image_url, 6018 price, 5176 category, 3939 material, 4636 dimensions

---

## Phần 2: Tích hợp data_pipeline vào các module sản phẩm

### 2.1. Crawl/Materialize pipeline (đã có, cần mở rộng)

**Hiện tại:** crawl → materialize dataset folder → register ProductDataset → dừng.

**Cần bổ sung (mở rộng crawl_materialize_jobs thành multi-stage):**
1. CRAWL — discovery + fetch + extract (dùng `SitemapProductUrlDiscoverer` + `ProductCrawlJob`)
2. ENRICH — `enrich_product_from_text()` → category/material/dimensions (dùng `enrichment.py`)
3. RAG_EXPORT — `convert_product_jsonl_to_rag_jsonl()` → structured metadata (dùng `rag_export.py`)
4. DEDUPE — `dedupe_product_jsonl()` → loại trùng (dùng `dedupe_output.py`)
5. MATERIALIZE — `materialize_product_dataset()` → dataset folder
6. QUALITY_AUDIT — `audit_product_dataset()` → quality gate (dùng `quality_audit.py`)
7. TAXONOMY_NORMALIZE — nếu có profile (dùng `taxonomy_normalize.py`)
8. REGISTER — ProductDataset (Java service)
9. BUILD_ARTIFACT — `build_dataset_kb_artifact()` (dùng script cũ)
10. BIND_TENANT — nếu có tenant_id → tạo TenantKbVersion + set activeKbVersionId
11. IMPORT_GENERAL — nếu visibility=GLOBAL_PUBLIC → import vào general layer

**Stage tracking:** Thêm field `stage` vào `crawl_materialize_jobs`, cập nhật dần khi worker chạy.

### 2.2. GeneralCatalogProvider (recommendation query)

**Chiến thuật:** Không chỉ dùng Java. Tận dụng `enrichment.py` ở FastAPI layer.

```
User query → FastAPI detect_signals()
          → extract category, material, price budget (rule-based, reuse enrichment.py logic)
          → POST đến backend API /api/internal/general-products/search
          → Backend query general_products theo scope (scope resolver)
          → filter theo constraints
          → score/rank
          → trả về FastAPI
          → LLM/template giải thích
```

**Cụ thể:** Giữ ranking trong Java/DB vì nhẹ (numeric + category match). Dùng Python `enrichment.py` nếu cần query understanding phức tạp (extract category từ text tiếng Việt).

### 2.3. MarketPriceInsightProvider

**Chiến thuật:** Dùng SQL aggregate trực tiếp trên `general_products`:
```sql
SELECT category, material,
       MIN(price), PERCENTILE_CONT(0.25)..., MEDIAN(price),
       PERCENTILE_CONT(0.75)..., MAX(price),
       COUNT(*) as sample_count,
       COUNT(DISTINCT source_code) as source_count
FROM general_products
WHERE status='ACTIVE' AND price IS NOT NULL
  AND visibility IN allowed_scope
  [AND category = ?]
  [AND material = ?]
GROUP BY category, material
```

Không cần Python cho insight tính toán. LLM chỉ giải thích kết quả.

### 2.4. Data quality dashboard

**Chiến thuật:** `quality_audit.py` đã tính sẵn mọi metric. Admin UI chỉ cần:
- Gọi `POST /api/admin/product-datasets/artifacts/{id}/audit` (chạy `audit_product_dataset()`)
- Hoặc query `general_products` coverage stats trong DB:
  ```sql
  SELECT COUNT(price)/COUNT(*) as price_coverage, ...
  ```

---

## Phần 3: Scope chi tiết theo phase

### Phase 1 — Ổn định nền ✅ (đã hoàn thành)

- Lightweight deployment (bỏ torch default) ✅
- General Data Layer schema (V36/V37/V38) ✅
- General importer + import artifact gotrangtri 6070 ✅
- Structured field backfill ✅
- Async crawl/materialize job (POST/GET) ✅
- Fix Messenger/Telegram test compile ✅

### Phase 2 — Multi-stage crawl job + scope resolver

#### 2A — Multi-stage orchestration (1 phase)

**Mở rộng `crawl_materialize_jobs`:**
- Thêm field `stage` (VARCHAR), `total_urls` (INT), `processed_urls` (INT), `tenant_id` (UUID), `build_artifact` (BOOLEAN), `bind_tenant` (BOOLEAN), `import_general` (BOOLEAN)
- Worker cập nhật stage qua từng bước
- Thêm stage: CRAWL, ENRICH, RAG_EXPORT, DEDUPE, MATERIALIZE, QUALITY_AUDIT, REGISTER, BUILD_ARTIFACT, BIND_TENANT, IMPORT_GENERAL
- Nếu fail ở stage nào → ghi stage name trong error message

**API:**
- `POST /api/admin/product-datasets/crawl-materialize-jobs` (mở rộng request: thêm `tenantId`, `buildArtifact`, `bindTenant`, `importGeneral`
- `GET .../jobs/{id}` trả stage hiện tại + processed/total

**Tận dụng data_pipeline:** Gọi `rag_export.py` → `dedupe_output.py` → `materialize_product_dataset.py` → `quality_audit.py` → `build_dataset_kb_artifact.py`

#### 2B — Scope resolver

- `GeneralScopeResolver` (Java service)
- Input: mode, tenant_id, role, source visibility
- Output: allowed WHERE clause

#### 2C — Internal search API

- `GET /api/internal/general-products/search`
- Controller mỏng → scope resolver → repository query → filter → score → rank
- Dùng `product_filters.py` logic (parse_price_constraint, parse_product_categories) ở Java

### Phase 3 — GeneralCompare

#### 3A — GeneralCatalogProvider

- Đọc từ `general_products` (không dùng file catalog.jsonl cũ)
- Fallback sang `InternalCatalogProvider` cũ nếu không có general data

#### 3B — FastAPI tích hợp

- Mode `general_compare`: gọi backend search API → context → LLM
- Ranking toàn bộ allowed corpus, không chia đều mỗi source

### Phase 4 — MarketPriceInsightProvider

- Provider mới đọc `general_products`, aggregate price stats
- Query category + material + optional dimensions range
- Tính min/p25/median/p75/max/sample_count/source_count
- Fallback sang `DatabaseMarketPriceProvider` cũ nếu không đủ data

### Phase 5 — Admin UX

- Crawl job list UI (reuse data từ GET jobs)
- Nút "Import to General" trên artifact detail
- Data quality dashboard (reuse quality_audit.py metrics)
- Source registry form (source_code, domain, sitemap, visibility)
- Job stage progress indicator

### Phase 6 — Isolation & Eval

- Test: tenant A không thấy general_products private của tenant B
- Test: general_compare không query TENANT_BOUND
- Test: crawler không crawl localhost/private IP
- Eval scripts: test_compare_scenarios.py, test_market_price.py

---

## Phần 4: Source visibility model

```
GLOBAL_PUBLIC  → general_compare / market_price thấy
TENANT_BOUND   → chỉ tenant sở hữu thấy (qua tenant_sales)
PRIVATE        → chỉ admin thấy
ADMIN_ONLY     → chỉ admin thấy
```

- Mặc định khi materialize từ tenant rebuild: TENANT_BOUND
- Mặc định khi admin crawl qua UI: GLOBAL_PUBLIC
- Import general chỉ khi GLOBAL_PUBLIC và admin approve

---

## Phần 5: Mối quan hệ giữa data_pipeline và General Data Layer

```
Crawl Output (products.jsonl)
    │
    ├── enrichment.py  → category, material, dimensions, price (rule-based)
    ├── dedupe_output.py  → loại trùng
    ├── rag_export.py  → structured metadata
    │
    ▼
Materialize → dataset folder
    │
    ├── quality_audit.py  → coverage, mojibake, duplicate
    ├── taxonomy_normalize.py  → source-aware category (nếu có profile)
    │
    ▼
Register ProductDataset (Java)
    │
    ▼
Build Artifact → products.jsonl + chunks.jsonl
    │
    ├── Build Tenant KB → activeKbVersionId (nếu bind)
    └── Import General → general_products (nếu GLOBAL_PUBLIC)
```

---

## Phần 6: source adapter strategy

Hiện chỉ gotrangtri có adapter + taxonomy profile đầy đủ.

**Chiến thuật mở rộng:**
1. MOHO, Caco, Nhà Xinh: tạo adapter kế thừa `SiteAdapter` (giống gotrangtri) — mỗi adapter chỉ cần selectors + allowed_domains + sitemap pattern
2. Generic fallback: dùng sitemap discovery với product_url_patterns infer từ domain
3. Taxonomy profile mới: mỗi source cần profile riêng nếu category tree khác gotrangtri
4. Nếu chưa có profile → skip taxonomy normalize, dùng raw category từ enrichment

---

## Phần 7: Demo mục tiêu

### Demo 1 — Tenant Sales
Tenant MOHO đã bind artifact → chatbot gợi ý sản phẩm MOHO → tạo purchase request

### Demo 2 — General Compare
"Gợi ý sofa vải dưới 7 triệu" → query general_products (gotrangtri + các source public) → top 5 phù hợp nhất

### Demo 3 — Market Price
"Sofa vải 2m giá 8tr có hợp lý không?" → aggregate price stats từ general_products → median 6.9tr, 37 samples

### Demo 4 — Admin Data Flow
Add source MOHO → crawl → materialize → register → build artifact → bind tenant → import general → general assistant thấy data mới

---

## Phần 8: Những thứ không làm

- Không rewrite crawler/materialize pipeline Python
- Không dùng LLM để chọn sản phẩm
- Không dùng LLM để quyết định visibility
- Không reset DB
- Không gắn cứng tenant.kbDir làm source-of-truth
- Không bỏ torch cho trường hợp cần local AI (giữ optional)
