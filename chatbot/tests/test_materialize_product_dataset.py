import json
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.materialize_product_dataset import materialize_product_dataset


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


class MaterializeProductDatasetTests(unittest.TestCase):
    def test_materialize_dataset_from_pipeline_output_and_report(self):
        tmp_path = TEST_TMP_ROOT / f"materialize-dataset-{uuid4().hex}"
        input_path = tmp_path / "batch_gotrangtri_products.jsonl"
        report_path = tmp_path / "batch_gotrangtri_products.jsonl.report.json"
        dataset_dir = tmp_path / "dataset"
        tmp_path.mkdir(parents=True, exist_ok=True)

        rows = [
            {
                "tenant_id": "demo-tenant",
                "product_name": "Bàn trà gỗ",
                "category": "Bàn trà",
                "price": 5900000,
                "currency": "VND",
                "brand": "Go Trang Tri",
                "material": "Gỗ sồi",
                "dimensions": "1200x600x435mm",
                "availability": "Còn hàng",
                "description": "Bàn trà phòng khách nhỏ gọn.",
                "source_url": "https://gotrangtri.vn/shop/ban-tra-go",
                "canonical_url": "https://gotrangtri.vn/shop/ban-tra-go",
                "image_urls": ["https://gotrangtri.vn/img/ban-tra-go.jpg"],
                "metadata": {"extractor": "json_ld", "data_quality": "high"},
                "content_hash": "abc123",
            },
            {
                "tenant_id": "demo-tenant",
                "product_name": "Sofa gỗ sồi",
                "category": "Sofa",
                "price": 12500000,
                "currency": "VND",
                "brand": "Go Trang Tri",
                "material": "Gỗ sồi tự nhiên",
                "availability": "Còn hàng",
                "description": "Sofa cho phòng khách.",
                "source_url": "https://gotrangtri.vn/shop/sofa-go-soi",
                "canonical_url": "https://gotrangtri.vn/shop/sofa-go-soi",
                "image_urls": ["https://gotrangtri.vn/img/sofa.jpg"],
                "metadata": {"extractor": "json_ld", "data_quality": "high"},
                "content_hash": "def456",
            },
        ]
        input_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        report_path.write_text(json.dumps({
            "source_name": "gotrangtri",
            "generated_at": "2026-05-29T18:38:41.757738+00:00",
            "counts": {"extracted_count": 2}
        }, ensure_ascii=False), encoding="utf-8")

        result = materialize_product_dataset(
            input_path=input_path,
            output_dir=dataset_dir,
            dataset_id="gotrangtri-20260529",
            source=None,
            source_url=None,
            version="20260529",
            overwrite=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["product_count"], 2)
        self.assertEqual(result["rag_chunk_count"], 2)
        self.assertTrue((dataset_dir / "manifest.json").exists())
        self.assertTrue((dataset_dir / "rag_products.jsonl").exists())

        manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["dataset_id"], "gotrangtri-20260529")
        self.assertEqual(manifest["source"], "gotrangtri")
        self.assertEqual(manifest["source_url"], "https://gotrangtri.vn")
        self.assertEqual(manifest["product_count"], 2)
        self.assertEqual(manifest["rag_chunk_count"], 2)
        self.assertEqual(manifest["files"]["rag_products"], "rag_products.jsonl")

        rag_rows = [json.loads(line) for line in (dataset_dir / "rag_products.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rag_rows), 2)
        self.assertIn("doc_id", rag_rows[0])
        self.assertIn("chunk_id", rag_rows[0])
        self.assertIn("content", rag_rows[0])
        self.assertEqual(rag_rows[0]["metadata"]["doc_type"], "product")


if __name__ == "__main__":
    unittest.main()
