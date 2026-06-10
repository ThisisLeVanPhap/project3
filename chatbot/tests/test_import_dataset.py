import json
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.import_dataset import import_dataset


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


class ImportDatasetTests(unittest.TestCase):
    def test_import_dataset_accepts_utf8_bom_manifest(self):
        tmp_path = TEST_TMP_ROOT / f"import-dataset-{uuid4().hex}"
        dataset_dir = tmp_path / "dataset"
        kb_base = tmp_path / "kb"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        (dataset_dir / "rag_products.jsonl").write_text(
            json.dumps(
                {
                    "shop": "demo",
                    "tenant_id": "demo",
                    "title": "Sample chair",
                    "content": "A compact chair for a small room.",
                    "url": "https://example.test/chair",
                    "metadata": {"doc_type": "product"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        manifest = {
            "dataset_id": "demo-dataset",
            "files": {"rag_products": "rag_products.jsonl"},
        }
        (dataset_dir / "manifest.json").write_text(
            "\ufeff" + json.dumps(manifest),
            encoding="utf-8",
        )

        result = import_dataset(dataset_dir, "demo_tenant", kb_base, None)

        self.assertTrue(result["success"])
        self.assertEqual(result["dataset_id"], "demo-dataset")
        self.assertEqual(result["chunk_count"], 1)
        self.assertTrue((kb_base / "demo_tenant" / "products.jsonl").exists())
        self.assertTrue((kb_base / "demo_tenant" / "chunks.jsonl").exists())
        self.assertTrue((kb_base / "demo_tenant" / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
