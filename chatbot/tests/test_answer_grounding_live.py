import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.answer_evaluator import evaluate_answer_grounding  # noqa: E402
from app.retrievers import RetrievalResult  # noqa: E402
from tools import run_answer_grounding_live as harness  # noqa: E402
from tools.run_answer_grounding_live import (  # noqa: E402
    capture_query,
    detect_live_config,
    generate_fake_answer,
    generate_live_answer,
    summarize_hit,
    summarize_outputs,
    write_outputs,
)


CONTEXT = (
    "[P1]\n"
    "Tên sản phẩm: Rèm cuốn tranh cao cấp GHO-607\n"
    "Danh mục: Rèm\n"
    "Giá: 700.000 VND\n"
    "Link nguồn: https://example.test/rem-cuon\n"
    "Mô tả ngắn: Rèm cuốn tranh cho phòng khách."
)


QUERY_SPEC = {
    "id": "listing_001",
    "query": "Co rem nao duoi 1 trieu khong?",
    "type": "product_listing",
    "expected_behavior": {
        "must_have_citation": True,
        "must_mention_price": True,
        "should_include_source_link": True,
        "max_products_to_answer": 5,
    },
}


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query: str, k: int = 4):
        return self.hits[:k]


def _hit() -> RetrievalResult:
    return RetrievalResult(
        doc_id="rem-1",
        chunk_id="rem-1#0",
        title="Rèm cuốn tranh cao cấp GHO-607",
        text="Rèm cuốn tranh cho phòng khách.",
        source="kb://rem-1",
        score=12.5,
        metadata={
            "doc_type": "product",
            "product_name": "Rèm cuốn tranh cao cấp GHO-607",
            "category": "Rèm",
            "price": 700000,
            "currency": "VND",
            "source_url": "https://example.test/rem-cuon",
        },
    )


class AnswerGroundingLiveHarnessTests(unittest.TestCase):
    def test_fake_answer_uses_context_citation_price_and_link(self):
        answer = generate_fake_answer(QUERY_SPEC, CONTEXT)

        self.assertIn("[P1]", answer)
        self.assertIn("700.000 VND", answer)
        self.assertIn("https://example.test/rem-cuon", answer)
        self.assertTrue(evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)["pass"])

    def test_fake_answer_handles_missing_field_without_fabricating(self):
        query_spec = {
            "id": "missing_001",
            "query": "San pham nay bao hanh bao lau?",
            "type": "missing_field",
            "expected_behavior": {"must_not_fabricate_missing_fields": True},
        }

        answer = generate_fake_answer(query_spec, CONTEXT)

        self.assertIn("chưa thấy", answer)
        self.assertNotIn("12 tháng", answer)
        self.assertTrue(evaluate_answer_grounding(query_spec, CONTEXT, answer)["pass"])

    def test_summarize_hit_extracts_product_fields(self):
        summary = summarize_hit(_hit())

        self.assertEqual(summary["category"], "Rèm")
        self.assertEqual(summary["price"], 700000)
        self.assertEqual(summary["url"], "https://example.test/rem-cuon")
        self.assertAlmostEqual(summary["score"], 12.5)

    def test_capture_query_outputs_answer_file_compatible_schema(self):
        row = capture_query(
            FakeRetriever([_hit()]),
            QUERY_SPEC,
            kb_dir="fake-kb",
            mode="fake",
            k=5,
        )

        self.assertEqual(row["id"], "listing_001")
        self.assertIn("context", row)
        self.assertIn("answer", row)
        self.assertIn("retrieval_hits", row)
        self.assertIn("prompt", row)
        self.assertEqual(row["metadata"]["provider"], "fake")
        self.assertIsInstance(row["metadata"]["latency_ms"], int)
        self.assertTrue(row["metadata"]["prompt_has_grounding_contract"])
        self.assertTrue(evaluate_answer_grounding(QUERY_SPEC, row["context"], row["answer"])["pass"])

    def test_run_capture_and_write_outputs_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            output = tmp / "outputs.json"
            rows = [capture_query(FakeRetriever([_hit()]), QUERY_SPEC, kb_dir="fake-kb", mode="fake", k=5)]
            write_outputs(rows, str(output))

            self.assertTrue(output.exists())
            loaded = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(loaded[0]["id"], "listing_001")
            self.assertEqual(summarize_outputs(loaded)["total_outputs"], 1)

    def test_live_mode_reports_clear_unavailable_error_without_config(self):
        with self.assertRaisesRegex(RuntimeError, "Live mode is not configured"):
            generate_live_answer(QUERY_SPEC, CONTEXT, env={})

    def test_live_config_check_reports_missing_env_without_secret_values(self):
        report = detect_live_config(env={"ANTHROPIC_API_KEY": "secret-key"})
        rendered = json.dumps(report)

        self.assertEqual(report["provider_detected"], ["claude"])
        self.assertIn("internal_claude", report["live_strategy_available"])
        self.assertNotIn("secret-key", rendered)

    def test_endpoint_strategy_can_be_mocked_without_network(self):
        calls = []

        def fake_post(url, payload, timeout_seconds):
            calls.append((url, payload, timeout_seconds))
            return {"reply": "Câu trả lời live [P1]", "latency_ms": 42, "model": "mock-live"}

        result = generate_live_answer(
            QUERY_SPEC,
            CONTEXT,
            endpoint="http://localhost:8000/chat",
            timeout_seconds=3,
            answer_mode="template",
            http_post=fake_post,
            env={},
        )

        self.assertEqual(result["answer"], "Câu trả lời live [P1]")
        self.assertEqual(result["provider"], "mock-live")
        self.assertEqual(result["strategy"], "endpoint")
        self.assertEqual(calls[0][1]["message"], QUERY_SPEC["query"])
        self.assertEqual(calls[0][1]["gen"]["answer_mode"], "template")

    def test_live_capture_schema_includes_provider_strategy_and_latency(self):
        def fake_post(url, payload, timeout_seconds):
            return {"reply": "Câu trả lời live [P1]", "latency_ms": 42, "model": "mock-live"}

        row = capture_query(
            FakeRetriever([_hit()]),
            QUERY_SPEC,
            kb_dir="fake-kb",
            mode="live",
            endpoint="http://localhost:8000/chat",
            http_post=fake_post,
        )

        self.assertEqual(row["metadata"]["mode"], "live")
        self.assertEqual(row["metadata"]["provider"], "mock-live")
        self.assertEqual(row["metadata"]["strategy"], "endpoint")
        self.assertIsInstance(row["metadata"]["latency_ms"], int)

    def test_template_mode_outputs_answer_file_compatible_schema(self):
        row = capture_query(
            FakeRetriever([_hit()]),
            QUERY_SPEC,
            kb_dir="fake-kb",
            mode="template",
            k=5,
        )

        self.assertEqual(row["metadata"]["mode"], "template")
        self.assertEqual(row["metadata"]["provider"], "template")
        self.assertEqual(row["metadata"]["strategy"], "template")
        self.assertIn("[P1]", row["answer"])
        self.assertIn("retrieval_hits", row)
        self.assertTrue(row["retrieval_hits"])

    def test_continue_on_error_keeps_batch_item(self):
        original_load_kb = harness.load_kb
        original_generate_live_answer = harness.generate_live_answer
        try:
            harness.load_kb = lambda kb_dir: FakeRetriever([_hit()])

            def fail_live(*args, **kwargs):
                raise RuntimeError("mock failure")

            harness.generate_live_answer = fail_live
            with tempfile.TemporaryDirectory() as tmpdir:
                queries = Path(tmpdir) / "queries.json"
                queries.write_text(json.dumps([QUERY_SPEC], ensure_ascii=False), encoding="utf-8")

                rows = harness.run_capture(
                    "fake-kb",
                    str(queries),
                    mode="live",
                    continue_on_error=True,
                )
        finally:
            harness.load_kb = original_load_kb
            harness.generate_live_answer = original_generate_live_answer

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["answer"], "")
        self.assertIn("mock failure", rows[0]["error"])
        self.assertEqual(harness.summarize_outputs(rows)["failed_count"], 1)


if __name__ == "__main__":
    unittest.main()
