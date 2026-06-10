import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.retrievers import RetrievalResult
from tools.evaluate_product_retrieval import (
    build_report,
    category_coverage,
    build_diagnostic_report,
    diagnose_failure,
    duplicate_rate,
    evaluate_query,
    evaluate_query_depths,
    price_satisfaction,
    scan_oracle_products,
    write_report,
)


def _hit(doc_id: str, category: str, price: float, url: str) -> RetrievalResult:
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=doc_id,
        text=f"{doc_id} {category}",
        source=url,
        score=10.0,
        metadata={
            "doc_type": "product",
            "category": category,
            "price": price,
            "canonical_url": url,
        },
    )


class ProductRetrievalEvaluatorTests(unittest.TestCase):
    def test_category_coverage_counts_represented_expected_categories(self):
        hits = [
            _hit("rem-1", "Rèm", 700_000, "https://example.test/rem-1"),
            _hit("den-1", "Đèn", 900_000, "https://example.test/den-1"),
            _hit("rem-2", "Rèm", 800_000, "https://example.test/rem-2"),
        ]

        count, ratio, represented = category_coverage(hits, ["Rèm", "Đèn", "Thảm"])

        self.assertEqual(count, 2)
        self.assertAlmostEqual(ratio, 2 / 3)
        self.assertEqual(represented, ["Rèm", "Đèn"])

    def test_price_satisfaction_uses_product_hits_as_denominator(self):
        hits = [
            _hit("cheap", "Rèm", 700_000, "https://example.test/cheap"),
            _hit("boundary", "Rèm", 1_000_000, "https://example.test/boundary"),
            _hit("expensive", "Rèm", 1_200_000, "https://example.test/expensive"),
        ]

        ratio = price_satisfaction(hits, {"max": 1_000_000})

        self.assertAlmostEqual(ratio, 2 / 3)

    def test_duplicate_rate_counts_repeated_urls_in_top_k(self):
        hits = [
            _hit("first", "Sofa", 5_000_000, "https://example.test/sofa"),
            _hit("second", "Sofa", 6_000_000, "https://example.test/sofa"),
            _hit("third", "Sofa", 7_000_000, "https://example.test/other"),
        ]

        self.assertAlmostEqual(duplicate_rate(hits), 1 / 3)

    def test_report_json_has_expected_shape(self):
        query_spec = {
            "id": "multi_category_001",
            "query": "Tôi muốn rèm hoặc đèn trang trí dưới 1 triệu",
            "type": "multi_category",
            "expected_categories": ["Rèm", "Đèn"],
            "required_terms_any": ["rèm", "đèn"],
            "price": {"max": 1_000_000},
            "notes": "fixture",
        }
        hits = [
            _hit("rem-1", "Rèm", 700_000, "https://example.test/rem-1"),
            _hit("den-1", "Đèn", 900_000, "https://example.test/den-1"),
        ]

        query_report = evaluate_query(query_spec, hits, latency_ms=12.34)
        report = build_report([query_report], k=5, kb_dir="kb/demo")

        self.assertEqual(report["total_queries"], 1)
        self.assertEqual(report["overall_pass_rate"], 1.0)
        self.assertIn("multi_category", report["metrics_by_type"])
        self.assertEqual(report["queries"][0]["result_count"], 2)
        self.assertEqual(report["queries"][0]["category_coverage_count"], 2)
        self.assertTrue(report["queries"][0]["weak_success"])

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.json"
            write_report(report, str(output))
            self.assertTrue(output.exists())
            self.assertIn('"total_queries": 1', output.read_text(encoding="utf-8"))

    def test_out_of_scope_prefixed_type_is_report_only(self):
        query_spec = {
            "id": "policy",
            "query": "Có bảo hành không?",
            "type": "out_of_scope_or_policy",
            "expected_categories": [],
            "required_terms_any": ["bảo hành"],
            "price": {},
        }

        query_report = evaluate_query(query_spec, [], latency_ms=1.0)
        diagnostic = build_diagnostic_report([{
            "id": "policy",
            "query": "Có bảo hành không?",
            "type": "out_of_scope_or_policy",
            "pass_by_depth": {"5": None, "10": None, "20": None, "50": None, "100": None},
            "diagnosis": None,
        }], kb_dir="kb/demo")

        self.assertIsNone(query_report["weak_success"])
        self.assertEqual(diagnostic["summary"]["evaluated_product_queries"], 0)

    def test_depth_metrics_report_pass_by_depth(self):
        query_spec = {
            "id": "depth",
            "query": "sofa chair",
            "type": "multi_category",
            "expected_categories": ["Sofa", "Chair"],
            "required_terms_any": ["sofa", "chair"],
            "price": {},
        }
        hits_by_depth = {
            5: [_hit("sofa-1", "Sofa", 5_000_000, "https://example.test/sofa-1")],
            10: [_hit("sofa-1", "Sofa", 5_000_000, "https://example.test/sofa-1")],
            20: [
                _hit("sofa-1", "Sofa", 5_000_000, "https://example.test/sofa-1"),
                _hit("chair-1", "Chair", 2_000_000, "https://example.test/chair-1"),
            ],
            50: [
                _hit("sofa-1", "Sofa", 5_000_000, "https://example.test/sofa-1"),
                _hit("chair-1", "Chair", 2_000_000, "https://example.test/chair-1"),
            ],
            100: [
                _hit("sofa-1", "Sofa", 5_000_000, "https://example.test/sofa-1"),
                _hit("chair-1", "Chair", 2_000_000, "https://example.test/chair-1"),
            ],
        }

        report = evaluate_query_depths(query_spec, hits_by_depth, {}, [])

        self.assertFalse(report["pass_by_depth"]["5"])
        self.assertTrue(report["pass_by_depth"]["20"])
        self.assertEqual(report["metrics_by_depth"]["20"]["category_coverage_count"], 2)

    def test_oracle_scan_finds_product_by_category_price_and_terms(self):
        query_spec = {
            "expected_categories": ["Rug"],
            "required_terms_any": ["wool"],
            "price": {"max": 2_000_000},
        }
        records = [
            {
                "title": "Wool rug",
                "text": "Soft wool rug",
                "url": "https://example.test/rug",
                "metadata": {"doc_type": "product", "category": "Rug", "price": 1_500_000},
            },
            {
                "title": "Expensive wool rug",
                "text": "wool",
                "url": "https://example.test/expensive",
                "metadata": {"doc_type": "product", "category": "Rug", "price": 3_000_000},
            },
        ]

        oracle = scan_oracle_products(query_spec, records)

        self.assertEqual(oracle["oracle_match_count"], 1)
        self.assertEqual(oracle["oracle_samples"][0]["url"], "https://example.test/rug")

    def test_diagnosis_candidate_generation_failure(self):
        query_spec = {
            "type": "single_category",
            "expected_categories": ["Rug"],
            "required_terms_any": ["rug"],
            "price": {},
        }
        depth_reports = {
            depth: evaluate_query(query_spec, [], latency_ms=1.0)
            for depth in (5, 10, 20, 50, 100)
        }

        diagnosis, _ = diagnose_failure(
            query_spec,
            depth_reports,
            {depth: [] for depth in (5, 10, 20, 50, 100)},
            {"oracle_match_count": 3},
        )

        self.assertEqual(diagnosis, "candidate_generation_failure")

    def test_diagnosis_reranking_failure(self):
        query_spec = {
            "type": "single_category",
            "expected_categories": ["Rug"],
            "required_terms_any": ["rug"],
            "price": {},
        }
        top5 = [_hit("sofa", "Sofa", 5_000_000, "https://example.test/sofa")]
        top20 = top5 + [_hit("rug", "Rug", 1_000_000, "https://example.test/rug")]
        hits_by_depth = {5: top5, 10: top5, 20: top20, 50: top20, 100: top20}
        depth_reports = {
            depth: evaluate_query(query_spec, hits_by_depth[depth], latency_ms=1.0)
            for depth in (5, 10, 20, 50, 100)
        }

        diagnosis, _ = diagnose_failure(
            query_spec,
            depth_reports,
            hits_by_depth,
            {"oracle_match_count": 1},
        )

        self.assertEqual(diagnosis, "reranking_failure")

    def test_diagnosis_data_missing(self):
        query_spec = {
            "type": "single_category",
            "expected_categories": ["Rug"],
            "required_terms_any": ["rug"],
            "price": {},
        }
        depth_reports = {
            depth: evaluate_query(query_spec, [], latency_ms=1.0)
            for depth in (5, 10, 20, 50, 100)
        }

        diagnosis, _ = diagnose_failure(
            query_spec,
            depth_reports,
            {depth: [] for depth in (5, 10, 20, 50, 100)},
            {"oracle_match_count": 0},
        )

        self.assertEqual(diagnosis, "data_missing")

    def test_diagnosis_multi_intent_coverage_failure(self):
        query_spec = {
            "type": "multi_category",
            "expected_categories": ["Table", "Shelf"],
            "required_terms_any": ["table", "shelf"],
            "price": {},
        }
        top5 = [_hit("table", "Table", 2_000_000, "https://example.test/table")]
        top100 = top5 + [_hit("shelf", "Shelf", 3_000_000, "https://example.test/shelf")]
        hits_by_depth = {5: top5, 10: top5, 20: top100, 50: top100, 100: top100}
        depth_reports = {
            depth: evaluate_query(query_spec, hits_by_depth[depth], latency_ms=1.0)
            for depth in (5, 10, 20, 50, 100)
        }

        diagnosis, _ = diagnose_failure(
            query_spec,
            depth_reports,
            hits_by_depth,
            {"oracle_match_count": 2},
        )

        self.assertEqual(diagnosis, "multi_intent_coverage_failure")

    def test_diagnostic_report_json_has_expected_shape(self):
        query_report = {
            "id": "q1",
            "query": "sofa",
            "type": "single_category",
            "pass_by_depth": {"5": False, "10": True, "20": True, "50": True, "100": True},
            "diagnosis": "reranking_failure",
        }

        report = build_diagnostic_report([query_report], kb_dir="kb/demo")

        self.assertEqual(report["summary"]["total_queries"], 1)
        self.assertEqual(report["summary"]["pass_at_5"], 0.0)
        self.assertEqual(report["summary"]["pass_at_20"], 1.0)
        self.assertEqual(report["summary"]["diagnosis_counts"]["reranking_failure"], 1)


if __name__ == "__main__":
    unittest.main()
