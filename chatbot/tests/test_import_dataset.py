import json
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.build_dataset_kb_artifact import build_dataset_kb_artifact
from tools.import_dataset import import_dataset


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


class ImportDatasetTests(unittest.TestCase):
    def test_import_dataset_accepts_utf8_bom_manifest(self):
        tmp_path = TEST_TMP_ROOT / f"import-dataset-{uuid4().hex}"
        dataset_dir = tmp_path / "dataset"
        kb_base = tmp_path / "kb"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        self.write_dataset(dataset_dir)
        manifest = {
            "dataset_id": "demo-dataset",
            "product_count": 1,
            "rag_chunk_count": 1,
            "files": {"catalog": "catalog.jsonl", "rag_products": "rag_products.jsonl"},
        }
        (dataset_dir / "manifest.json").write_text(
            "\ufeff" + json.dumps(manifest),
            encoding="utf-8",
        )

        result = import_dataset(dataset_dir, "demo_tenant", kb_base, None)

        self.assertTrue(result["success"])
        self.assertEqual(result["dataset_id"], "demo-dataset")
        self.assertEqual(result["chunk_count"], 1)
        self.assertEqual(result["quality_status"], "pass")
        self.assertTrue((dataset_dir / "quality_audit.json").exists())
        self.assertTrue((kb_base / "demo_tenant" / "products.jsonl").exists())
        self.assertTrue((kb_base / "demo_tenant" / "chunks.jsonl").exists())
        self.assertTrue((kb_base / "demo_tenant" / "index.json").exists())

    def test_import_dataset_blocks_quality_fail(self):
        tmp_path = TEST_TMP_ROOT / f"import-dataset-{uuid4().hex}"
        dataset_dir = tmp_path / "dataset"
        kb_base = tmp_path / "kb"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        self.write_dataset(dataset_dir, title="RÃ¨m lỗi")
        (dataset_dir / "manifest.json").write_text(
            json.dumps({
                "dataset_id": "bad-dataset",
                "product_count": 1,
                "rag_chunk_count": 1,
                "files": {"catalog": "catalog.jsonl", "rag_products": "rag_products.jsonl"},
            }),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            import_dataset(dataset_dir, "demo_tenant", kb_base, None)
        self.assertFalse((kb_base / "demo_tenant" / "chunks.jsonl").exists())

    def test_build_dataset_kb_artifact_does_not_require_tenant(self):
        tmp_path = TEST_TMP_ROOT / f"build-artifact-{uuid4().hex}"
        dataset_dir = tmp_path / "dataset"
        artifact_dir = tmp_path / "kb" / "datasets" / "demo-dataset" / "build-1"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        self.write_dataset(dataset_dir)
        (dataset_dir / "manifest.json").write_text(
            json.dumps({
                "dataset_id": "demo-dataset",
                "product_count": 1,
                "rag_chunk_count": 1,
                "files": {"catalog": "catalog.jsonl", "rag_products": "rag_products.jsonl"},
            }),
            encoding="utf-8",
        )

        result = build_dataset_kb_artifact(dataset_dir, artifact_dir)

        self.assertTrue(result["success"])
        self.assertEqual(result["dataset_id"], "demo-dataset")
        self.assertEqual(result["artifact_count"], 1)
        self.assertEqual(result["quality_status"], "pass")
        self.assertTrue((artifact_dir / "products.jsonl").exists())
        self.assertTrue((artifact_dir / "chunks.jsonl").exists())
        self.assertTrue((artifact_dir / "index.json").exists())

    def write_dataset(self, dataset_dir: Path, title: str = "Sample chair"):
        catalog_row = {
            "tenant_id": "demo",
            "product_name": title,
            "price": 1000000,
            "category": "Ghế",
            "material": "Gỗ",
            "dimensions": "100x50cm",
            "source_url": "https://example.test/chair",
        }
        rag_row = {
            "shop": "demo",
            "tenant_id": "demo",
            "title": title,
            "content": "A compact chair for a small room.",
            "text": "A compact chair for a small room.",
            "url": "https://example.test/chair",
            "metadata": {
                "doc_type": "product",
                "product_name": title,
                "price": 1000000,
                "category": "Ghế",
                "material": "Gỗ",
                "dimensions": "100x50cm",
                "source_url": "https://example.test/chair",
            },
        }
        (dataset_dir / "catalog.jsonl").write_text(json.dumps(catalog_row, ensure_ascii=False) + "\n", encoding="utf-8")
        (dataset_dir / "rag_products.jsonl").write_text(json.dumps(rag_row, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
