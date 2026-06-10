import json
import tempfile
import unittest
from pathlib import Path

from data_pipeline.crawling.rag_export import (
    build_product_rag_document,
    convert_product_jsonl_to_rag_jsonl,
)


class ProductRagExportTests(unittest.TestCase):
    def test_build_product_rag_document_full_product(self):
        product = {
            "tenant_id": "tenant-a",
            "source_url": "https://shop.example/p/sofa",
            "canonical_url": "https://shop.example/p/sofa",
            "product_name": "Sofa SFG041",
            "price": 2500000,
            "original_price": 3000000,
            "currency": "VND",
            "category": "Sofa",
            "brand": "CaCo",
            "material": "Gỗ sồi",
            "color": "Nâu",
            "dimensions": "120 x 60 x 45 cm",
            "description": "Sofa phòng khách nhỏ.",
            "image_urls": ["https://shop.example/sofa.jpg"],
            "availability": "InStock",
            "sku": "SFG041",
            "observed_at": "2026-05-30T00:00:00+00:00",
            "content_hash": "abc123",
            "confidence": 1.0,
            "metadata": {"data_quality": "high", "extractor": "json_ld"},
        }

        doc = build_product_rag_document(product)

        self.assertEqual(doc["tenant_id"], "tenant-a")
        self.assertEqual(doc["shop"], "tenant-a")
        self.assertEqual(doc["url"], "https://shop.example/p/sofa")
        self.assertIn("Sofa SFG041", doc["content"])
        self.assertIn("Giá tham khảo: 2.500.000 VND.", doc["content"])
        self.assertIn("Danh mục: Sofa.", doc["content"])
        self.assertIn("Chất liệu: Gỗ sồi.", doc["content"])
        self.assertIn("Kích thước: 120 x 60 x 45 cm.", doc["content"])
        self.assertEqual(doc["metadata"]["doc_type"], "product")
        self.assertEqual(doc["metadata"]["sku"], "SFG041")
        self.assertEqual(doc["metadata"]["price"], 2500000)
        self.assertEqual(doc["metadata"]["data_quality"], "high")

    def test_missing_optional_fields_do_not_render_none(self):
        doc = build_product_rag_document({
            "tenant_id": "tenant-a",
            "source_url": "https://shop.example/p/rem",
            "product_name": "Rèm cửa",
            "currency": "VND",
            "metadata": {},
        })

        self.assertNotIn("None", doc["content"])
        self.assertNotIn("Giá tham khảo", doc["content"])
        self.assertIn("Rèm cửa", doc["content"])

    def test_convert_product_jsonl_to_rag_jsonl(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="rag-export-"))
        input_path = temp_dir / "products.jsonl"
        output_path = temp_dir / "product_chunks.jsonl"
        products = [
            {"tenant_id": "tenant-a", "source_url": "https://shop.example/p/1", "product_name": "Sofa", "price": 1},
            {"tenant_id": "tenant-a", "source_url": "https://shop.example/p/2", "product_name": "Bàn trà", "price": 2},
        ]
        input_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in products) + "\n",
            encoding="utf-8",
        )

        stats = convert_product_jsonl_to_rag_jsonl(input_path, output_path)

        self.assertEqual(stats["count"], 2)
        rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["metadata"]["doc_type"], "product")
        self.assertEqual(rows[1]["title"], "Bàn trà")


if __name__ == "__main__":
    unittest.main()
