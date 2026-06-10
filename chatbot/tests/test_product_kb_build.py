import json
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.retrievers import BaselineRetriever
from tools.build_product_kb import build_product_kb


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class ProductKbBuildTests(unittest.TestCase):
    def test_build_product_kb_creates_baseline_retriever_index(self):
        tmp_path = TEST_TMP_ROOT / f"product-kb-{uuid4().hex}"
        input_path = tmp_path / "product_chunks.jsonl"
        kb_dir = tmp_path / "kb"

        _write_jsonl(
            input_path,
            [
                {
                    "doc_id": "product-rem",
                    "chunk_id": "product-rem#chunk-0",
                    "shop": "demo-tenant",
                    "tenant_id": "demo-tenant",
                    "title": "Rèm cửa giá rẻ dưới 1 triệu",
                    "text": "Sản phẩm rèm cửa phòng khách giá 700.000 VND, phù hợp ngân sách dưới 1 triệu.",
                    "source": "https://example.test/rem-cua-gia-re",
                    "metadata": {
                        "tenant_id": "demo-tenant",
                        "doc_type": "product",
                        "category": "Rèm",
                        "price": 700000,
                    },
                },
                {
                    "doc_id": "product-den",
                    "chunk_id": "product-den#chunk-0",
                    "shop": "demo-tenant",
                    "tenant_id": "demo-tenant",
                    "title": "Đèn trang trí phòng khách",
                    "content": "Sản phẩm đèn trang trí phòng khách giá 1.500.000 VND.",
                    "url": "https://example.test/den-trang-tri",
                    "metadata": {
                        "tenant_id": "demo-tenant",
                        "doc_type": "product",
                        "category": "Đèn trang trí",
                        "price": 1500000,
                    },
                },
            ],
        )

        total = build_product_kb(str(input_path), str(kb_dir))

        chunks_path = kb_dir / "chunks.jsonl"
        index_path = kb_dir / "index.json"
        self.assertEqual(total, 2)
        self.assertTrue(chunks_path.exists())
        self.assertTrue(index_path.exists())

        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["N"], 2)
        self.assertIn("idf", index)
        self.assertIn("rem", index["idf"])

        chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(chunks[0]["content"], chunks[0]["text"])
        self.assertEqual(chunks[0]["url"], chunks[0]["source"])
        self.assertEqual(chunks[0]["metadata"]["tenant_id"], "demo-tenant")
        self.assertEqual(chunks[0]["metadata"]["doc_type"], "product")

        retriever = BaselineRetriever(str(chunks_path), str(index_path))
        hits = retriever.search("rèm dưới 1 triệu", k=2)

        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0].doc_id, "product-rem")
        self.assertEqual(hits[0].metadata["doc_type"], "product")
        self.assertEqual(hits[0].tenant_id, "demo-tenant")


if __name__ == "__main__":
    unittest.main()
