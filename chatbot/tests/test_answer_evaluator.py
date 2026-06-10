import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.answer_evaluator import (  # noqa: E402
    evaluate_answer_grounding,
    extract_answer_citations,
    extract_context_facts,
)
from app.retrievers import RetrievalResult  # noqa: E402
from tools.evaluate_answer_grounding import (  # noqa: E402
    evaluate_context_readiness,
    run_answers_mode,
    write_report,
)


CONTEXT = (
    "[P1]\n"
    "Tên sản phẩm: Rèm cuốn tranh cao cấp GHO-607\n"
    "Danh mục: Rèm\n"
    "Giá: 700.000 VND\n"
    "Chất liệu: Vải\n"
    "SKU: GHO-607\n"
    "Link nguồn: https://example.test/rem-cuon\n"
    "Mô tả ngắn: Rèm cuốn tranh cho phòng khách."
)


QUERY_SPEC = {
    "id": "price_001",
    "query": "Có rèm nào dưới 1 triệu không?",
    "type": "price_constraint",
    "expected_behavior": {
        "must_have_citation": True,
        "must_mention_price": True,
        "should_include_source_link": True,
        "must_not_fabricate_missing_fields": True,
    },
}


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query: str, k: int = 4):
        return self.hits[:k]


class AnswerEvaluatorTests(unittest.TestCase):
    def test_extract_context_facts_parses_product_block(self):
        facts = extract_context_facts(CONTEXT)

        self.assertIn("P1", facts["products"])
        product = facts["products"]["P1"]
        self.assertEqual(product["product_name"], "Rèm cuốn tranh cao cấp GHO-607")
        self.assertEqual(product["price_value"], 700000)
        self.assertEqual(product["source_url"], "https://example.test/rem-cuon")

    def test_valid_citation_passes(self):
        answer = "Rèm cuốn tranh cao cấp GHO-607 [P1] giá 700.000 VND. Nguồn: https://example.test/rem-cuon"

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertTrue(result["citation_validity"])
        self.assertTrue(result["pass"])

    def test_invalid_citation_fails(self):
        answer = "Rèm cuốn tranh cao cấp GHO-607 [P99] giá 700.000 VND."

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertFalse(result["citation_validity"])
        self.assertFalse(result["pass"])

    def test_ungrounded_product_name_fails(self):
        answer = "Sofa Phantom là lựa chọn tốt, giá 700.000 VND."

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertFalse(result["product_name_grounded"])
        self.assertFalse(result["pass"])

    def test_fabricated_price_fails(self):
        answer = "Rèm cuốn tranh cao cấp GHO-607 [P1] giá 900.000 VND. Nguồn: https://example.test/rem-cuon"

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertFalse(result["price_consistency"])
        self.assertFalse(result["pass"])

    def test_price_consistency_ignores_sku_and_url_numbers(self):
        answer = (
            "Rèm cuốn tranh cao cấp GHO-607 [P1] giá 700.000 VND. "
            "Nguồn: https://example.test/rem-607"
        )

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertTrue(result["price_consistency"])

    def test_price_consistency_ignores_dimensions(self):
        answer = (
            "Rèm cuốn tranh cao cấp GHO-607 [P1] giá 700.000 VND, "
            "kích thước tham khảo 1800x360x535mm và 114x55x42cm. "
            "Nguồn: https://example.test/rem-cuon"
        )

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertTrue(result["price_consistency"])
        self.assertIn("dimension", {item["reason"] for item in result["price_details"]["ignored_numbers"]})

    def test_range_price_passes_when_endpoints_are_in_context(self):
        context = (
            "[P1]\n"
            "Tên sản phẩm: Bàn trà A\n"
            "Giá: 1.500.000 VND\n"
            "Link nguồn: https://example.test/a\n\n"
            "[P2]\n"
            "Tên sản phẩm: Bàn trà B\n"
            "Giá: 1.700.000 VND\n"
            "Link nguồn: https://example.test/b"
        )
        answer = (
            "Khoảng giá có trong context là 1.500.000 - 1.700.000 VND cho "
            "Bàn trà A [P1] và Bàn trà B [P2]. Nguồn: https://example.test/a"
        )

        result = evaluate_answer_grounding(QUERY_SPEC, context, answer)

        self.assertTrue(result["price_consistency"])
        self.assertEqual(result["price_details"]["approximate_or_range_prices"], [1500000, 1700000])

    def test_aggregate_total_does_not_fail_product_price_consistency(self):
        answer = (
            "Rèm cuốn tranh cao cấp GHO-607 [P1] giá 700.000 VND. "
            "Tổng tham khảo khoảng 1.400.000 VND, ước tính từ các sản phẩm đang liệt kê. "
            "Nguồn: https://example.test/rem-cuon"
        )

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertTrue(result["price_consistency"])
        self.assertEqual(result["price_details"]["aggregate_prices"], [1400000])
        self.assertEqual(result["price_details"]["mismatched_prices"], [])

    def test_query_constraint_price_is_not_product_price_mismatch(self):
        answer = (
            "Dưới 2 triệu thì có các mẫu sau: "
            "Rèm cuốn tranh cao cấp GHO-607 [P1] - Giá: 700.000 VND. "
            "Nguồn: https://example.test/rem-cuon"
        )

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertTrue(result["price_consistency"])
        self.assertEqual(result["price_details"]["query_constraint_prices"], [2000000])
        self.assertEqual(result["price_details"]["detected_prices"], [700000])

    def test_product_specific_wrong_price_still_fails(self):
        answer = (
            "Rèm cuốn tranh cao cấp GHO-607 [P1] - Giá: 3.000.000 VND. "
            "Nguồn: https://example.test/rem-cuon"
        )

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertFalse(result["price_consistency"])
        self.assertEqual(result["price_details"]["mismatched_prices"], [3000000])

    def test_general_approximate_range_price_does_not_fail(self):
        answer = (
            "Nhóm sản phẩm này thường ở khoảng 4-5 triệu tùy mẫu. "
            "Rèm cuốn tranh cao cấp GHO-607 [P1] - Giá: 700.000 VND. "
            "Nguồn: https://example.test/rem-cuon"
        )

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertTrue(result["price_consistency"])
        self.assertIn(5000000, result["price_details"]["approximate_or_range_prices"])

    def test_product_name_without_source_id_fails(self):
        answer = "Rèm cuốn tranh cao cấp GHO-607 giá 700.000 VND. Nguồn: https://example.test/rem-cuon"

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertFalse(result["has_required_citation"])
        self.assertFalse(result["product_name_grounded"])
        self.assertFalse(result["pass"])

    def test_product_citation_without_link_is_source_link_failure_not_hallucination(self):
        answer = "Rèm cuốn tranh cao cấp GHO-607 [P1] giá 700.000 VND."

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertTrue(result["has_required_citation"])
        self.assertFalse(result["source_link_presence"])
        self.assertTrue(result["no_forbidden_hallucination"])
        self.assertTrue(result["source_link_missing"])

    def test_out_of_scope_missing_info_does_not_need_citation(self):
        query_spec = {
            "query": "Tôi muốn mua điện thoại",
            "type": "out_of_scope_or_policy",
            "expected_behavior": {"must_have_citation": False, "should_include_source_link": False},
        }
        answer = "Mình chưa thấy thông tin này trong dữ liệu hiện có. Bạn nên liên hệ cửa hàng để xác nhận."

        result = evaluate_answer_grounding(query_spec, CONTEXT, answer)

        self.assertTrue(result["has_required_citation"])
        self.assertTrue(result["pass"])

    def test_policy_missing_info_does_not_need_citation(self):
        query_spec = {
            "query": "Chính sách đổi trả thế nào?",
            "type": "out_of_scope_or_policy",
            "expected_behavior": {"must_have_citation": False, "should_include_source_link": False},
        }
        answer = "Mình chưa thấy thông tin này trong dữ liệu hiện có. Bạn nên liên hệ cửa hàng để xác nhận."

        result = evaluate_answer_grounding(query_spec, CONTEXT, answer)

        self.assertTrue(result["has_required_citation"])
        self.assertTrue(result["pass"])

    def test_out_of_scope_fallback_with_product_words_passes(self):
        query_spec = {
            "query": "Tôi muốn mua điện thoại",
            "type": "out_of_scope_or_policy",
            "expected_behavior": {"must_have_citation": False, "should_include_source_link": False},
        }
        answer = "Mình chưa thấy thông tin về quạt mini trong dữ liệu hiện có."

        result = evaluate_answer_grounding(query_spec, CONTEXT, answer)

        self.assertTrue(result["out_of_scope_fallback_valid"])
        self.assertTrue(result["product_name_grounded"])
        self.assertTrue(result["pass"])

    def test_out_of_scope_fabricated_product_price_fails(self):
        query_spec = {
            "query": "Tôi muốn mua điện thoại",
            "type": "out_of_scope_or_policy",
            "expected_behavior": {"must_have_citation": False, "should_include_source_link": False},
        }
        answer = "Có quạt mini giá 500k khá phù hợp."

        result = evaluate_answer_grounding(query_spec, CONTEXT, answer)

        self.assertFalse(result["price_consistency"])
        self.assertFalse(result["pass"])

    def test_missing_warranty_fabrication_fails(self):
        query_spec = {
            "query": "Sản phẩm này bảo hành bao lâu?",
            "expected_behavior": {"must_not_fabricate_missing_fields": True},
        }
        answer = "Sản phẩm này bảo hành 12 tháng và miễn phí vận chuyển."

        result = evaluate_answer_grounding(query_spec, CONTEXT, answer)

        self.assertFalse(result["missing_field_handling"])
        self.assertFalse(result["no_forbidden_hallucination"])
        self.assertFalse(result["pass"])

    def test_missing_warranty_fallback_passes(self):
        query_spec = {
            "query": "Sản phẩm này bảo hành bao lâu?",
            "expected_behavior": {"must_not_fabricate_missing_fields": True},
        }
        answer = "Mình chưa thấy thông tin này trong dữ liệu hiện có. Bạn nên hỏi cửa hàng để xác nhận."

        result = evaluate_answer_grounding(query_spec, CONTEXT, answer)

        self.assertTrue(result["missing_field_handling"])
        self.assertTrue(result["no_forbidden_hallucination"])
        self.assertTrue(result["pass"])

    def test_extract_answer_citations(self):
        self.assertEqual(extract_answer_citations("Xem [P1] và [P2]."), {"P1", "P2"})

    def test_context_readiness_detects_source_link(self):
        hit = RetrievalResult(
            doc_id="p1",
            chunk_id="p1#0",
            title="Rèm cuốn tranh cao cấp GHO-607",
            text="Rèm cuốn tranh cho phòng khách.",
            source="kb://p1",
            metadata={
                "doc_type": "product",
                "product_name": "Rèm cuốn tranh cao cấp GHO-607",
                "category": "Rèm",
                "price": 700000,
                "currency": "VND",
                "source_url": "https://example.test/rem-cuon",
            },
        )

        row = evaluate_context_readiness(FakeRetriever([hit]), QUERY_SPEC)

        self.assertTrue(row["context_ready"])
        self.assertTrue(row["context_has_source_links"])
        self.assertEqual(row["context_product_count"], 1)

    def test_answers_report_json_has_expected_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            queries = tmp / "queries.json"
            answers = tmp / "answers.json"
            output = tmp / "report.json"
            queries.write_text(json.dumps([QUERY_SPEC], ensure_ascii=False), encoding="utf-8")
            answers.write_text(
                json.dumps([
                    {
                        "id": "price_001",
                        "query": QUERY_SPEC["query"],
                        "context": CONTEXT,
                        "answer": "Rèm cuốn tranh cao cấp GHO-607 [P1] giá 700.000 VND. Nguồn: https://example.test/rem-cuon",
                    }
                ], ensure_ascii=False),
                encoding="utf-8",
            )

            report = run_answers_mode(str(queries), str(answers))
            write_report(report, str(output))

            self.assertEqual(report["summary"]["total_answers"], 1)
            self.assertEqual(report["summary"]["pass_rate"], 1.0)
            self.assertTrue(output.exists())
            self.assertIn("answers", json.loads(output.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
