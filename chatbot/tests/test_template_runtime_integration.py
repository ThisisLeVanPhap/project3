import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["CHATBOT_TEST_MODE"] = "1"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="chatbot-template-runtime-logs-")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVER_IMPORT_ERROR = None
server = None
TestClient = None
reset_state = None

from app.retrievers import RetrievalResult  # noqa: E402

try:
    from fastapi.testclient import TestClient  # noqa: E402

    from app import server  # noqa: E402
    from app.state import reset_state  # noqa: E402
except ModuleNotFoundError as exc:
    SERVER_IMPORT_ERROR = exc


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query: str, k: int = 4):
        return self.hits[:k]


def _product_hit() -> RetrievalResult:
    return RetrievalResult(
        doc_id="p1",
        chunk_id="p1#0",
        title="Rèm cuốn tranh cao cấp GHO-607",
        text="Rèm cuốn tranh cho phòng khách.",
        source="kb://p1",
        score=10.0,
        metadata={
            "doc_type": "product",
            "product_name": "Rèm cuốn tranh cao cấp GHO-607",
            "category": "Rèm",
            "price": 700000,
            "currency": "VND",
            "material": "Vải",
            "sku": "GHO-607",
            "availability": "https://schema.org/InStock",
            "source_url": "https://example.test/rem-cuon",
        },
    )


class TemplateRuntimeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SERVER_IMPORT_ERROR is not None:
            return
        cls.previous_kb = server.KB
        cls.previous_by_mode = dict(server.KB_BY_MODE)
        cls.previous_template_default = server.PRODUCT_TEMPLATE_ANSWERS_DEFAULT
        cls.previous_stub_generate = server._stub_generate
        cls.kb = FakeRetriever([_product_hit()])
        server.KB = cls.kb
        server.KB_BY_MODE.clear()
        server.KB_BY_MODE["keyword"] = cls.kb
        server._set_ready(True, None)
        cls.client = TestClient(server.app)

    @classmethod
    def tearDownClass(cls):
        if SERVER_IMPORT_ERROR is not None:
            return
        server.KB = cls.previous_kb
        server.KB_BY_MODE.clear()
        server.KB_BY_MODE.update(cls.previous_by_mode)
        server.PRODUCT_TEMPLATE_ANSWERS_DEFAULT = cls.previous_template_default
        server._stub_generate = cls.previous_stub_generate

    def setUp(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")
        server.PRODUCT_TEMPLATE_ANSWERS_DEFAULT = False
        server._stub_generate = type(self).previous_stub_generate

    def _post_chat(self, message: str, gen=None):
        conversation_id = f"template-runtime-{self._testMethodName}"
        reset_state(conversation_id)
        payload = {
            "message": message,
            "history": [],
            "conversation_id": conversation_id,
            "tenant_id": "tenant-test",
            "channel": "web",
            "gen": {
                "provider": "stub",
                "mode": "general_compare",
                "retrieval_mode": "keyword",
                "retrieval_top_k": 4,
            },
        }
        if gen:
            payload["gen"].update(gen)
        return self.client.post("/chat", json=payload)

    def test_generation_config_accepts_answer_mode(self):
        cfg = server.GenerationConfig(answer_mode="template")

        self.assertEqual(cfg.answer_mode, "template")

    def test_generation_config_default_keeps_llm_mode(self):
        cfg = server.GenerationConfig()

        self.assertIsNone(cfg.answer_mode)
        self.assertEqual(server._resolve_answer_mode(cfg), "llm")

    def test_env_default_enables_template_when_request_omits_answer_mode(self):
        server.PRODUCT_TEMPLATE_ANSWERS_DEFAULT = True

        response = self._post_chat("Có rèm nào dưới 1 triệu không?")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"], "product-template")
        self.assertEqual(payload["debug"]["answer_mode"], "template")

    def test_request_llm_overrides_env_template_default(self):
        server.PRODUCT_TEMPLATE_ANSWERS_DEFAULT = True

        response = self._post_chat("Có rèm nào dưới 1 triệu không?", {"answer_mode": "llm"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"], "stub")
        self.assertEqual(payload["debug"]["answer_mode"], "llm")

    def test_chat_template_mode_skips_llm_provider(self):
        def fail_stub(*args, **kwargs):
            raise AssertionError("stub generator should not be called in template mode")

        server._stub_generate = fail_stub

        response = self._post_chat("Có rèm nào dưới 1 triệu không?", {"answer_mode": "template"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"], "product-template")
        self.assertIn("Rèm cuốn tranh cao cấp GHO-607 [P1]", payload["reply"])
        self.assertIn("700.000 VND", payload["reply"])
        self.assertIn("https://example.test/rem-cuon", payload["reply"])
        self.assertEqual(payload["debug"]["answer_mode"], "template")
        self.assertTrue(payload["debug"]["template_renderer"])
        self.assertEqual(payload["debug"]["retrieval_count"], 1)

    def test_chat_llm_mode_keeps_old_stub_branch(self):
        response = self._post_chat("Có rèm nào dưới 1 triệu không?", {"answer_mode": "llm"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"], "stub")
        self.assertIn("[stub]", payload["reply"])

    def test_template_out_of_scope_does_not_recommend_products(self):
        response = self._post_chat("Tôi muốn mua điện thoại", {"answer_mode": "template"})

        self.assertEqual(response.status_code, 200)
        reply = response.json()["reply"]
        self.assertIn("Mình chưa thấy thông tin này trong dữ liệu hiện có.", reply)
        self.assertNotIn("Rèm cuốn", reply)

    def test_template_smoke_queries(self):
        queries = [
            "Có rèm nào dưới 1 triệu không?",
            "So sánh sofa và ghế thư giãn",
            "Có bàn trà nào hợp với kệ tivi không?",
            "Chính sách đổi trả thế nào?",
        ]
        for query in queries:
            response = self._post_chat(query, {"answer_mode": "template"})
            self.assertEqual(response.status_code, 200, query)
            self.assertEqual(response.json()["debug"]["answer_mode"], "template")


if __name__ == "__main__":
    unittest.main()
