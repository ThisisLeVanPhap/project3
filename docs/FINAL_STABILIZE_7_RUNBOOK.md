# FINAL-STABILIZE-7 Demo Runbook

Short checklist for the Product Dataset -> Tenant KB -> Runtime -> Chat demo.

## Local DB Notes

- Spring datasource: `jdbc:postgresql://localhost:5432/global_admin`
- Flyway current schema version verified in local run: `31`
- Demo tenant: `datn_demo_moho`
- Product dataset: `gotrangtri-20260610`
- Dataset path: `data_pipeline/output/datasets/gotrangtri-20260610`
- Expected dataset counts: `product_count=6070`, `rag_chunk_count=6070`

## Manual Demo Checklist

1. Start PostgreSQL and confirm database `global_admin` is available.
2. Start backend:

```powershell
cd F:\20251\prj3\multitenant
.\mvnw.cmd spring-boot:run
```

3. Open `http://localhost:8080/admin`.
4. Login as platform admin.
5. Go to `Tenant Management -> Tenants`.
6. Select tenant `datn_demo_moho`.
7. Go to `Knowledge Base -> Product Datasets`.
8. Load datasets and open `gotrangtri-20260610`.
9. Verify `product_count=6070`, `rag_chunk_count=6070`, path, and content hash.
10. Assign dataset to the selected tenant only if the tenant has no active gotrangtri KB yet.
11. Go to `Knowledge Base -> KB Versions` and verify the gotrangtri version is `READY` and active.
12. Go to `Knowledge Base -> KB Directories` and verify source is `ACTIVE_VERSION`.
13. Go to `Knowledge Base -> Runtime` and verify desired/running KB dir match the active KB version.
14. Open tenant chat and ask a product question, for example:

```text
Sản phẩm nào bằng gỗ công nghiệp?
```

15. Verify the reply contains product names, prices, SKUs, or gotrangtri links from the KB.

## Evidence Checklist

Capture these screenshots for the final demo package:

- Product Datasets list with `gotrangtri-20260610`
- Product Dataset detail showing counts, path, and content hash
- Assign result showing tenant, KB dir, and chunk/artifact count
- KB Versions showing gotrangtri version `READY` and active
- Active KB Directory showing source `ACTIVE_VERSION`
- Runtime Status showing desired/running KB dir in sync
- Chat response showing product data from gotrangtri KB

## Suggested Verification Commands

```powershell
cd F:\20251\prj3\multitenant
.\mvnw.cmd -Dtest=*ProductDataset* test
.\mvnw.cmd -Dtest=*Kb* test
.\mvnw.cmd test

cd F:\20251\prj3
python -m unittest chatbot.tests.test_import_dataset
python .\chatbot\tools\import_dataset.py --help
```

