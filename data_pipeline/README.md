# Data Pipeline Product Catalog

Khung nay tach rieng crawl va chuan hoa product catalog khoi chatbot runtime.
Buoc nay khong tich hop vao `server.py`, khong sua runtime chatbot, va khong goi Claude API.

## Multi-tenant isolation

Pipeline co the xu ly nhieu nguon du lieu, nhung output phai tach ro scope:

- `tenant_private`: du lieu rieng cua mot tenant/shop. Chi dung cho `tenant_sales` cua dung tenant do.
- `tenant_public`: du lieu cong khai cua mot tenant/shop, nhung van gan voi tenant. Runtime tenant van phai loc theo dung `tenant_id`.
- `public_reference`: public reference catalog / market reference catalog / du lieu tham chieu cong khai. Day la nguon cho `general_compare` va `market_price`.

Khong goi public reference catalog la aggregate tenant data. Khong tron du lieu rieng cua shop nay sang shop khac.

## Input schema

Quan ly URL bang:

```text
data_pipeline/input/source_urls.csv
```

Header bat buoc:

```csv
tenant_id,store,source_type,category,visibility,url,note
```

Quy tac:

- `visibility` chi duoc la `tenant_private`, `tenant_public`, hoac `public_reference`.
- Neu `visibility` la `tenant_private` hoac `tenant_public`, `tenant_id` bat buoc co gia tri.
- Neu `visibility` la `public_reference`, `tenant_id` de trong de tranh hieu nham day la du lieu rieng cua tenant.
- Moi record lay tu website cua hang van giu cac field `tenant_id`, `store`, `source_url`, `crawled_at` neu ap dung.
- Thieu du lieu crawl/parse thi de `null`, khong tu bia.

## Output layout

```text
data_pipeline/output/
  tenants/
    {tenant_id}/
      products.clean.jsonl
      catalog_report.md
  reference/
    products.clean.jsonl
    knowledge_docs.clean.jsonl
    catalog_report.md
```

`data_pipeline/output/reference/products.clean.jsonl` la public reference catalog cho `general_compare` va `market_price`.

`data_pipeline/output/tenants/{tenant_id}/products.clean.jsonl` la catalog rieng theo tenant, dung cho `tenant_sales` cua dung tenant.

`knowledge_docs.clean.jsonl` chi tao khi can chuan hoa tai lieu/knowledge tham chieu cong khai; khung hien tai chua sinh file nay.

## Runtime rules

- `tenant_sales` chi doc record co `tenant_id` dung voi `request.tenant_id`.
- `general_compare` chi doc `visibility=public_reference`, khong doc `tenant_private`.
- `market_price` chi doc `visibility=public_reference`, khong doc `tenant_private`.
- Policy/knowledge cua cua hang chi dung cho dung tenant.
- Chatbot runtime chua duoc tich hop trong buoc nay.

## Quy trinh du kien

### 1. Nhap URL

Them URL vao `data_pipeline/input/source_urls.csv`.

Vi du schema, khong phai du lieu mau:

```csv
tenant_id,store,source_type,category,visibility,url,note
```

### 2. Crawl raw

Mac dinh crawler chi dry-run de tranh crawl hang loat ngoai y muon:

```powershell
python data_pipeline\scripts\crawl_products.py
```

Khi can crawl that, truyen `--execute` va nen dung `--limit`:

```powershell
python data_pipeline\scripts\crawl_products.py --execute --limit 10
```

Raw HTML va metadata duoc luu trong `data_pipeline/raw/pages/`. Metadata giu `visibility` de buoc normalize route dung output scope.

### 3. Tach link san pham tu collection

Neu mot row trong `source_urls.csv` co `source_type=collection` va raw HTML da duoc crawl, co the tach link san pham:

```powershell
python data_pipeline\scripts\extract_product_links.py --link-pattern "/products/"
```

Script xuat `data_pipeline/output/source_urls.discovered.csv`. Can review thu cong truoc khi dua link vao `input/source_urls.csv`.

### 4. Normalize

Chuan hoa raw HTML thanh JSONL va tu route theo `visibility`:

```powershell
python data_pipeline\scripts\normalize_catalog.py
```

Ket qua:

- `public_reference` -> `data_pipeline/output/reference/products.clean.jsonl`
- `tenant_private` / `tenant_public` -> `data_pipeline/output/tenants/{tenant_id}/products.clean.jsonl`

### 5. Validate

Validate public reference catalog:

```powershell
python data_pipeline\scripts\validate_catalog.py --input data_pipeline\output\reference\products.clean.jsonl --report data_pipeline\output\reference\catalog_report.md
```

Validate catalog cua mot tenant:

```powershell
python data_pipeline\scripts\validate_catalog.py --input data_pipeline\output\tenants\TENANT_ID\products.clean.jsonl --report data_pipeline\output\tenants\TENANT_ID\catalog_report.md
```

Report kiem tra field bat buoc, `visibility`, duplicate URL, missing field quan trong, va thong ke theo visibility/store/category.

### 6. Chuyen du lieu sang chatbot sau nay

Buoc nay chua copy vao chatbot va chua tich hop runtime. Khi tich hop sau nay, runtime phai doc dung output theo rule multi-tenant o tren.
