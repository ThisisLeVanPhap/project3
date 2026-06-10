import json
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = ROOT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


BENCHMARK_FILES = [
    REPO_DIR / "chatbot" / "benchmarks" / "product_retrieval_queries.json",
    REPO_DIR / "chatbot" / "benchmarks" / "product_retrieval_stress_queries.json",
]


class ProductRetrievalBenchmarkTests(unittest.TestCase):
    def test_benchmark_files_follow_expected_schema(self):
        required_keys = {
            "id",
            "query",
            "type",
            "expected_categories",
            "required_terms_any",
            "price",
            "notes",
        }

        for path in BENCHMARK_FILES:
            with self.subTest(path=str(path)):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(data, list)
                self.assertGreater(len(data), 0)
                seen_ids = set()
                for row in data:
                    self.assertTrue(required_keys.issubset(row.keys()))
                    self.assertNotIn(row["id"], seen_ids)
                    seen_ids.add(row["id"])
                    self.assertIsInstance(row["query"], str)
                    self.assertIsInstance(row["type"], str)
                    self.assertIsInstance(row["expected_categories"], list)
                    self.assertIsInstance(row["required_terms_any"], list)
                    self.assertIsInstance(row["price"], dict)

    def test_stress_benchmark_does_not_map_work_desk_to_dining_table(self):
        path = REPO_DIR / "chatbot" / "benchmarks" / "product_retrieval_stress_queries.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        row = next(item for item in data if item["id"] == "multi_category_matching_006")

        self.assertNotIn("Bàn ăn", row["expected_categories"])
        self.assertIn("Kệ", row["expected_categories"])
        self.assertTrue(any(term in row["required_terms_any"] for term in ("bàn làm việc", "ban lam viec")))

    def test_stress_benchmark_accepts_ambiguous_decor_coffee_table_query(self):
        path = REPO_DIR / "chatbot" / "benchmarks" / "product_retrieval_stress_queries.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        row = next(item for item in data if item["id"] == "natural_language_need_009")

        self.assertIn("Bàn trà", row["expected_categories"])
        self.assertNotIn("Đồ trang trí", row["expected_categories"])
        self.assertIn("decor", row["required_terms_any"])


if __name__ == "__main__":
    unittest.main()
