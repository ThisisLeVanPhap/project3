import json
import tempfile
import unittest
from pathlib import Path

from data_pipeline.crawling.quality_audit import audit_product_dataset, has_mojibake


class ProductDatasetQualityAuditTests(unittest.TestCase):
    def test_valid_dataset_passes(self):
        dataset = self.make_dataset()

        report = audit_product_dataset(dataset)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["product_count_actual"], 2)
        self.assertEqual(report["rag_chunk_count_actual"], 2)
        self.assertEqual(report["duplicate_url_count"], 0)

    def test_manifest_product_count_mismatch_fails(self):
        dataset = self.make_dataset(product_count=3)

        report = audit_product_dataset(dataset)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("product_count" in reason for reason in report["fail_reasons"]))

    def test_manifest_rag_count_mismatch_fails(self):
        dataset = self.make_dataset(rag_count=3)

        report = audit_product_dataset(dataset)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("rag_chunk_count" in reason for reason in report["fail_reasons"]))

    def test_title_mojibake_fails(self):
        dataset = self.make_dataset(title="RÃ¨m sáo gỗ")

        report = audit_product_dataset(dataset)

        self.assertTrue(has_mojibake("RÃ¨m"))
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["title_mojibake_count"], 1)

    def test_rag_text_mojibake_warns_when_titles_clean(self):
        dataset = self.make_dataset(rag_text="Sản phẩm: Rèm. Mô tả: RÃ¨m lỗi.")

        report = audit_product_dataset(dataset)

        self.assertEqual(report["status"], "warn")
        self.assertEqual(report["rag_text_mojibake_count"], 1)

    def test_stale_crawl_report_warns(self):
        dataset = self.make_dataset(crawl_report={"row_count": 1})

        report = audit_product_dataset(dataset)

        self.assertEqual(report["status"], "warn")
        self.assertTrue(report["stale_report"])

    def test_duplicate_url_detected(self):
        dataset = self.make_dataset(duplicate_url=True)

        report = audit_product_dataset(dataset)

        self.assertEqual(report["duplicate_url_count"], 1)
        self.assertEqual(report["status"], "fail")

    def test_suspicious_category_detected(self):
        dataset = self.make_dataset(title="Tủ quần áo gỗ", category="Kệ", url="https://gotrangtri.vn/shop/tu-quan-ao-go")

        report = audit_product_dataset(dataset)

        self.assertEqual(report["suspicious_category_count"], 1)
        self.assertEqual(report["status"], "warn")

    def make_dataset(
        self,
        product_count=2,
        rag_count=2,
        title="Rèm sáo gỗ",
        category="Rèm",
        url="https://gotrangtri.vn/shop/rem-sao-go",
        rag_text="Sản phẩm: Rèm sáo gỗ.",
        crawl_report=None,
        duplicate_url=False,
    ) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dataset = Path(tmp.name)
        second_url = url if duplicate_url else "https://gotrangtri.vn/shop/sofa-go"
        catalog_rows = [
            {
                "tenant_id": "demo",
                "product_name": title,
                "price": 1000000,
                "category": category,
                "material": "Gỗ",
                "dimensions": "100x50cm",
                "source_url": url,
            },
            {
                "tenant_id": "demo",
                "product_name": "Sofa gỗ",
                "price": 2000000,
                "category": "Sofa",
                "material": "Gỗ",
                "dimensions": "120x80cm",
                "source_url": second_url,
            },
        ]
        rag_rows = [
            {
                "title": title,
                "text": rag_text,
                "content": rag_text,
                "url": url,
                "metadata": {
                    "product_name": title,
                    "price": 1000000,
                    "category": category,
                    "material": "Gỗ",
                    "dimensions": "100x50cm",
                    "source_url": url,
                },
            },
            {
                "title": "Sofa gỗ",
                "text": "Sản phẩm: Sofa gỗ.",
                "content": "Sản phẩm: Sofa gỗ.",
                "url": second_url,
                "metadata": {
                    "product_name": "Sofa gỗ",
                    "price": 2000000,
                    "category": "Sofa",
                    "material": "Gỗ",
                    "dimensions": "120x80cm",
                    "source_url": second_url,
                },
            },
        ]
        self.write_jsonl(dataset / "catalog.jsonl", catalog_rows)
        self.write_jsonl(dataset / "rag_products.jsonl", rag_rows)
        (dataset / "manifest.json").write_text(json.dumps({
            "dataset_id": "demo-dataset",
            "product_count": product_count,
            "rag_chunk_count": rag_count,
            "files": {"catalog": "catalog.jsonl", "rag_products": "rag_products.jsonl"},
        }), encoding="utf-8")
        if crawl_report is not None:
            (dataset / "crawl_report.json").write_text(json.dumps(crawl_report), encoding="utf-8")
        return dataset

    def write_jsonl(self, path: Path, rows):
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    unittest.main()
