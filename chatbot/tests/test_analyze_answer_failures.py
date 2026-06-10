import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.analyze_answer_failures import analyze_failures, classify_failed_answer  # noqa: E402


CONTEXT = (
    "[P1]\n"
    "Tên sản phẩm: Sofa A\n"
    "Giá: 10.000.000 VND\n"
    "Link nguồn: https://example.test/sofa-a\n"
)


def _answer_row(answer: str, query_type: str = "product_listing"):
    return {
        "id": "q1",
        "query": "Có sofa không?",
        "type": query_type,
        "context": CONTEXT,
        "answer": answer,
    }


def _eval_row(metrics):
    base = {
        "has_required_citation": True,
        "citation_validity": True,
        "source_link_presence": True,
        "price_consistency": True,
        "product_name_grounded": True,
        "missing_field_handling": True,
        "no_forbidden_hallucination": True,
        "answer_usefulness": True,
        "pass": False,
        "source_link_missing": False,
        "price_details": {
            "detected_prices": [],
            "context_prices": [10000000],
            "mismatched_prices": [],
        },
    }
    base.update(metrics)
    return {"id": "q1", "query": "Có sofa không?", "pass": False, "metrics": base}


class AnalyzeAnswerFailuresTests(unittest.TestCase):
    def test_classifies_real_hallucination_shipping(self):
        row = classify_failed_answer(
            _answer_row("Sofa A [P1] được miễn phí vận chuyển."),
            _eval_row({"no_forbidden_hallucination": False}),
        )

        self.assertIn("real_hallucination", row["failure_types"])
        self.assertIn("shipping", row["hallucinated_fields"])

    def test_classifies_source_link_missing(self):
        row = classify_failed_answer(
            _answer_row("Sofa A [P1] giá 10.000.000 VND."),
            _eval_row({"source_link_presence": False, "source_link_missing": True}),
        )

        self.assertIn("source_link_missing", row["failure_types"])

    def test_classifies_price_evaluator_false_positive(self):
        row = classify_failed_answer(
            _answer_row("Có nhiều sofa dưới 12 triệu. Sofa A [P1] giá 10.000.000 VND."),
            _eval_row({
                "price_consistency": False,
                "price_details": {
                    "detected_prices": [10000000, 12000000],
                    "context_prices": [10000000],
                    "mismatched_prices": [12000000],
                },
            }),
        )

        self.assertIn("price_evaluator_false_positive", row["failure_types"])
        self.assertEqual(row["recommended_fix"], "evaluator")

    def test_classifies_query_constraint_price_ignored(self):
        row = classify_failed_answer(
            _answer_row("Có nhiều sofa dưới 12 triệu. Sofa A [P1] giá 10.000.000 VND."),
            _eval_row({
                "price_consistency": False,
                "price_details": {
                    "detected_prices": [10000000],
                    "query_constraint_prices": [12000000],
                    "context_prices": [10000000],
                    "mismatched_prices": [12000000],
                },
            }),
        )

        self.assertIn("query_constraint_price_ignored", row["failure_types"])

    def test_report_counts_ignored_price_categories_for_passed_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            answers = tmp / "answers.json"
            eval_report = tmp / "eval.json"
            answers.write_text(json.dumps([_answer_row("Sofa A [P1] giá 10.000.000 VND.")], ensure_ascii=False), encoding="utf-8")
            passed_row = _eval_row({
                "pass": True,
                "price_details": {
                    "detected_prices": [10000000],
                    "query_constraint_prices": [12000000],
                    "approximate_or_range_prices": [11000000],
                    "aggregate_prices": [],
                    "context_prices": [10000000],
                    "mismatched_prices": [],
                },
            })
            passed_row["pass"] = True
            eval_report.write_text(
                json.dumps({
                    "summary": {},
                    "answers": [passed_row],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            report = analyze_failures(str(answers), str(eval_report))

            self.assertEqual(report["summary"]["total_failed"], 0)
            self.assertEqual(report["summary"]["ignored_price_counts"]["query_constraint_price_ignored"], 1)
            self.assertEqual(report["summary"]["ignored_price_counts"]["approximate_range_price_ignored"], 1)

    def test_classifies_answer_template_needed_for_bad_product_format(self):
        row = classify_failed_answer(
            _answer_row("Sofa A [P1] là lựa chọn phù hợp."),
            _eval_row({"source_link_presence": False, "source_link_missing": True}),
        )

        self.assertIn("answer_template_needed", row["failure_types"])
        self.assertEqual(row["recommended_fix"], "answer_template")

    def test_analysis_report_json_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            answers = tmp / "answers.json"
            eval_report = tmp / "eval.json"
            answers.write_text(json.dumps([_answer_row("Sofa A [P1] được miễn phí vận chuyển.")], ensure_ascii=False), encoding="utf-8")
            eval_report.write_text(
                json.dumps({
                    "summary": {},
                    "answers": [_eval_row({"no_forbidden_hallucination": False})],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            report = analyze_failures(str(answers), str(eval_report))

            self.assertIn("summary", report)
            self.assertIn("failed_answers", report)
            self.assertEqual(report["summary"]["total_failed"], 1)
            self.assertIn("failure_type_counts", report["summary"])


if __name__ == "__main__":
    unittest.main()
