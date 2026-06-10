import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

os.environ["CHATBOT_TEST_MODE"] = "1"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="chatbot-test-logs-")

SERVER_IMPORT_ERROR = None
server = None
TestClient = None
reset_state = None

from app.retrieval_service import format_context, load_kb, search_hits  # noqa: E402
from app.market_data import InternalCatalogProvider, MockMarketPriceProvider  # noqa: E402
from tools.build_kb import build_kb  # noqa: E402

try:
    from fastapi.testclient import TestClient  # noqa: E402

    from app import server  # noqa: E402
    from app.state import reset_state, set_stage  # noqa: E402
except ModuleNotFoundError as exc:
    SERVER_IMPORT_ERROR = exc


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class ServerRagStubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = Path(tempfile.mkdtemp(prefix="chatbot-rag-kb-"))
        docs_path = cls.tmp_dir / "docs.jsonl"
        chunks_path = cls.tmp_dir / "chunks.jsonl"
        index_path = cls.tmp_dir / "index.json"

        _write_jsonl(docs_path, [
            {
                "shop": "tenant-test",
                "url": "kb://sfg041",
                "title": "Sofa Model SFG041",
                "content": (
                    "Sofa model SFG041 cho can ho nho, chat lieu go soi, "
                    "kich thuoc 180cm, mau xam hien dai, gia tham chieu 12 trieu."
                ),
            },
            {
                "shop": "tenant-test",
                "url": "kb://sfg040",
                "title": "Sofa Model SFG040",
                "content": (
                    "Sofa model SFG040 khung go chac chan, nem em, kich thuoc 200cm, "
                    "phong cach toi gian, gia tham chieu 10 trieu."
                ),
            },
            {
                "shop": "tenant-test",
                "url": "kb://sfg039",
                "title": "Sofa Model SFG039",
                "content": (
                    "Sofa model SFG039 chat lieu go tu nhien, mau nau am, kich thuoc 220cm, "
                    "phu hop phong khach rong, gia tham chieu 15 trieu."
                ),
            },
            {
                "shop": "tenant-test",
                "url": "kb://dining-table",
                "title": "Dining Table DT01",
                "content": "Ban an go tu nhien cho phong an bon nguoi.",
            },
        ])
        build_kb(str(docs_path), str(chunks_path), str(index_path))

        cls.kb = load_kb(str(cls.tmp_dir), mode="keyword")
        cls.client = None
        if SERVER_IMPORT_ERROR is None:
            server.KB_DIR = str(cls.tmp_dir)
            server.KB_RETRIEVAL_MODE = "keyword"
            server.KB = cls.kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = server.KB
            server.INTERNAL_CATALOG_PROVIDER = InternalCatalogProvider(kb_dir=str(cls.tmp_dir))
            server._set_ready(True, None)
            cls.client = TestClient(server.app)

    def test_retrieval_returns_context(self):
        hits = search_hits(
            self.kb,
            "sofa model SFG041 cho can ho nho",
            k=4,
            tenant_id="tenant-test",
        )
        context = format_context(hits)

        self.assertGreater(len(hits), 0)
        self.assertIn("Sofa Model SFG041", context)
        self.assertIn("can ho nho", context)

    def test_chat_uses_retrieved_context_with_stub_generator(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        conversation_id = "rag-stub-test-conversation"
        reset_state(conversation_id)

        response = self.client.post(
            "/chat",
            json={
                "message": "Toi can sofa model SFG041 cho can ho nho va chat lieu go",
                "history": [],
                "conversation_id": conversation_id,
                "tenant_id": "tenant-test",
                "gen": {
                    "provider": "stub",
                    "mode": "tenant_sales",
                    "retrieval_mode": "keyword",
                    "retrieval_top_k": 4,
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        debug = payload["debug"]

        self.assertEqual(payload["model"], "stub")
        self.assertGreater(debug["retrieved_docs"], 0)
        self.assertGreater(debug["context_chars"], 0)
        self.assertEqual(debug["retrieval_mode"], "keyword")
        self.assertEqual(debug["mode"], "tenant_sales")
        self.assertIn("prompt_has_context=True", payload["reply"])
        self.assertIn("SFG041", payload["reply"])

    def test_tenant_sales_allows_purchase_request_trigger(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        conversation_id = "tenant-sales-purchase-trigger"
        reset_state(conversation_id)
        set_stage(conversation_id, "close")

        response = self.client.post(
            "/chat",
            json={
                "message": "yes please, confirm",
                "history": [],
                "conversation_id": conversation_id,
                "tenant_id": "tenant-test",
                "gen": {
                    "provider": "stub",
                    "mode": "tenant_sales",
                    "retrieval_mode": "keyword",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["debug"]["mode"], "tenant_sales")
        self.assertTrue(payload["trigger_purchase_request"])

    def test_general_compare_auto_detects_and_never_triggers_purchase(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        conversation_id = "general-compare-mode"
        reset_state(conversation_id)

        response = self.client.post(
            "/chat",
            json={
                "message": (
                    "So sanh 3 lua chon sofa SFG041 SFG040 SFG039 theo gia, "
                    "chat lieu, kich thuoc va phong cach"
                ),
                "history": [],
                "conversation_id": conversation_id,
                "tenant_id": "tenant-test",
                "gen": {
                    "provider": "stub",
                    "retrieval_mode": "keyword",
                    "retrieval_top_k": 4,
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        debug = payload["debug"]

        self.assertEqual(debug["mode"], "general_compare")
        self.assertGreaterEqual(debug["retrieved_docs"], 3)
        self.assertGreater(debug["context_chars"], 0)
        self.assertFalse(payload["trigger_purchase_request"])
        self.assertIn("[stub][general_compare]", payload["reply"])
        self.assertIn("Nguồn dữ liệu:", payload["reply"])
        self.assertIn("Các lựa chọn so sánh:", payload["reply"])
        self.assertIn("Tiêu chí so sánh: giá, chất liệu, kích thước/phong cách/mục đích dùng.", payload["reply"])
        self.assertIn("chưa có dữ liệu", payload["reply"])
        self.assertIn("No purchase request", payload["reply"])

    def test_general_compare_falls_back_to_retrieval_when_catalog_missing(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        conversation_id = "general-compare-retrieval-fallback"
        reset_state(conversation_id)
        previous_provider = server.INTERNAL_CATALOG_PROVIDER
        server.INTERNAL_CATALOG_PROVIDER = InternalCatalogProvider(catalog_path=str(self.tmp_dir / "missing.jsonl"))
        try:
            response = self.client.post(
                "/chat",
                json={
                    "message": "So sanh sofa SFG041 SFG040 SFG039 theo gia va chat lieu",
                    "history": [],
                    "conversation_id": conversation_id,
                    "tenant_id": "tenant-test",
                    "gen": {
                        "provider": "stub",
                        "mode": "general_compare",
                        "retrieval_mode": "keyword",
                        "retrieval_top_k": 4,
                    },
                },
            )
        finally:
            server.INTERNAL_CATALOG_PROVIDER = previous_provider

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        debug = payload["debug"]

        self.assertEqual(debug["mode"], "general_compare")
        self.assertEqual(debug["internal_candidates"], 0)
        self.assertEqual(debug["data_provider"], "retrieval")
        self.assertGreater(debug["retrieved_docs"], 0)
        self.assertFalse(payload["trigger_purchase_request"])

    def test_market_price_auto_detects_and_never_triggers_purchase(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        conversation_id = "market-price-mode"
        reset_state(conversation_id)

        response = self.client.post(
            "/chat",
            json={
                "message": "Gia thi truong cua sofa SFG041 co cao bat thuong khong, khoang gia hop ly la bao nhieu?",
                "history": [],
                "conversation_id": conversation_id,
                "tenant_id": "tenant-test",
                "gen": {
                    "provider": "stub",
                    "retrieval_mode": "keyword",
                    "retrieval_top_k": 4,
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        debug = payload["debug"]

        self.assertEqual(debug["mode"], "market_price")
        self.assertGreater(debug["retrieved_docs"], 0)
        self.assertGreater(debug["context_chars"], 0)
        self.assertEqual(debug["external_price_refs"], 0)
        self.assertFalse(debug["used_mock_price_data"])
        self.assertFalse(payload["trigger_purchase_request"])
        self.assertEqual(payload["model"], "structured_price")
        self.assertIn("Chưa có đủ dữ liệu giá có cấu trúc", payload["reply"])
        self.assertIn("phân tích sát hơn", payload["reply"])

    def test_market_price_debug_includes_mock_price_refs_when_enabled(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        conversation_id = "market-price-mock-provider"
        reset_state(conversation_id)
        previous_provider = server.PRICE_PROVIDER
        server.PRICE_PROVIDER = MockMarketPriceProvider()
        try:
            response = self.client.post(
                "/chat",
                json={
                    "message": "Gia sofa SFG041 khoang bao nhieu la hop ly?",
                    "history": [],
                    "conversation_id": conversation_id,
                    "tenant_id": "tenant-test",
                    "gen": {
                        "provider": "stub",
                        "mode": "market_price",
                        "retrieval_mode": "keyword",
                        "retrieval_top_k": 4,
                    },
                },
            )
        finally:
            server.PRICE_PROVIDER = previous_provider

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        debug = payload["debug"]

        self.assertEqual(debug["mode"], "market_price")
        self.assertEqual(debug["price_provider"], "mock_market_price")
        self.assertGreater(debug["external_price_refs"], 0)
        self.assertTrue(debug["used_mock_price_data"])
        self.assertEqual(debug["data_provider"], "mock_market_price")
        self.assertFalse(payload["trigger_purchase_request"])
        self.assertEqual(payload["model"], "structured_price")

    def test_market_price_mock_provider_formats_range_and_warning(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        conversation_id = "market-price-mock-format"
        reset_state(conversation_id)
        previous_provider = server.PRICE_PROVIDER
        server.PRICE_PROVIDER = MockMarketPriceProvider()
        try:
            response = self.client.post(
                "/chat",
                json={
                    "message": "Gia 14 trieu cho sofa SFG041 co hop ly khong?",
                    "history": [],
                    "conversation_id": conversation_id,
                    "tenant_id": "tenant-test",
                    "gen": {
                        "provider": "stub",
                        "mode": "market_price",
                        "retrieval_mode": "keyword",
                        "retrieval_top_k": 4,
                    },
                },
            )
        finally:
            server.PRICE_PROVIDER = previous_provider

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        debug = payload["debug"]

        self.assertEqual(debug["mode"], "market_price")
        self.assertGreater(debug["external_price_refs"], 0)
        self.assertTrue(debug["used_mock_price_data"])
        self.assertFalse(payload["trigger_purchase_request"])
        self.assertEqual(payload["model"], "structured_price")
        self.assertIn("## Tham khảo giá SFG041", payload["reply"])
        self.assertIn("Khoảng giá tham khảo: khoảng 12.0-15.0 triệu VND", payload["reply"])
        self.assertIn("Dữ liệu đối chiếu: 2 mẫu tham chiếu hiện có.", payload["reply"])
        self.assertIn("Nhận xét: Mức 14.0 triệu VND đang nằm trong khoảng tham chiếu.", payload["reply"])
        self.assertIn("Lưu ý: Khoảng giá có thể thay đổi", payload["reply"])
        self.assertNotIn("mock", payload["reply"].lower())
        self.assertNotIn("provider", payload["reply"].lower())
        self.assertNotIn("purchase request", payload["reply"].lower())

    def test_market_price_generic_oak_sofa_reply_hides_internal_terms(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        conversation_id = "market-price-oak-sofa"
        reset_state(conversation_id)
        previous_provider = server.PRICE_PROVIDER
        server.PRICE_PROVIDER = MockMarketPriceProvider()
        try:
            response = self.client.post(
                "/chat",
                json={
                    "message": "So sánh giá sofa gỗ sồi với mặt bằng chung",
                    "history": [],
                    "conversation_id": conversation_id,
                    "tenant_id": "tenant-test",
                    "gen": {
                        "provider": "stub",
                        "mode": "market_price",
                        "retrieval_mode": "keyword",
                        "retrieval_top_k": 4,
                    },
                },
            )
        finally:
            server.PRICE_PROVIDER = previous_provider

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["model"], "structured_price")
        self.assertIn("## Tham khảo giá sofa gỗ sồi", payload["reply"])
        self.assertIn("Khoảng giá tham khảo:", payload["reply"])
        self.assertIn("Dữ liệu đối chiếu:", payload["reply"])
        self.assertNotIn("mock", payload["reply"].lower())
        self.assertNotIn("provider", payload["reply"].lower())
        self.assertNotIn("purchase request", payload["reply"].lower())


    def test_local_pipeline_cache_evicts_lru_without_loading_real_model(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        previous_cache = dict(server.PIPE_CACHE)
        previous_max_cache = server.LOCAL_PIPELINE_MAX_CACHE
        previous_model_loader = sys.modules.get("app.model_loader")
        fake_model_loader = types.ModuleType("app.model_loader")

        def fake_get_pipeline(base, adapter, tokenizer_path):
            return types.SimpleNamespace(base=base, adapter=adapter, tokenizer_path=tokenizer_path)

        fake_model_loader.get_pipeline = fake_get_pipeline
        sys.modules["app.model_loader"] = fake_model_loader

        try:
            server.PIPE_CACHE.clear()
            server.LOCAL_PIPELINE_MAX_CACHE = 2

            first = server.get_or_create_pipe("model-a", None, None)
            second = server.get_or_create_pipe("model-b", None, None)
            server.PIPE_CACHE[("model-a", None, None)].last_used = 200.0
            server.PIPE_CACHE[("model-b", None, None)].last_used = 100.0

            third = server.get_or_create_pipe("model-c", None, None)

            self.assertIsNot(first, second)
            self.assertIsNot(second, third)
            self.assertEqual(len(server.PIPE_CACHE), 2)
            self.assertIn(("model-a", None, None), server.PIPE_CACHE)
            self.assertIn(("model-c", None, None), server.PIPE_CACHE)
            self.assertNotIn(("model-b", None, None), server.PIPE_CACHE)
        finally:
            server.PIPE_CACHE.clear()
            server.PIPE_CACHE.update(previous_cache)
            server.LOCAL_PIPELINE_MAX_CACHE = previous_max_cache
            if previous_model_loader is None:
                sys.modules.pop("app.model_loader", None)
            else:
                sys.modules["app.model_loader"] = previous_model_loader

    def test_local_pipeline_cleanup_evicts_idle_entries(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")

        previous_cache = dict(server.PIPE_CACHE)
        previous_ttl = server.LOCAL_PIPELINE_IDLE_TTL_SECONDS
        old_key = ("old-model", None, None)
        fresh_key = ("fresh-model", None, None)
        now = 500.0

        try:
            server.PIPE_CACHE.clear()
            server.LOCAL_PIPELINE_IDLE_TTL_SECONDS = 180
            server.PIPE_CACHE[old_key] = server.PipelineCacheEntry(
                pipe=object(),
                last_used=now - 181,
                key=old_key,
                base_model="old-model",
                adapter=None,
                tokenizer_path=None,
            )
            server.PIPE_CACHE[fresh_key] = server.PipelineCacheEntry(
                pipe=object(),
                last_used=now - 10,
                key=fresh_key,
                base_model="fresh-model",
                adapter=None,
                tokenizer_path=None,
            )

            evicted = server._cleanup_idle_pipelines_once(now=now)

            self.assertEqual(evicted, 1)
            self.assertNotIn(old_key, server.PIPE_CACHE)
            self.assertIn(fresh_key, server.PIPE_CACHE)
        finally:
            server.PIPE_CACHE.clear()
            server.PIPE_CACHE.update(previous_cache)
            server.LOCAL_PIPELINE_IDLE_TTL_SECONDS = previous_ttl


if __name__ == "__main__":
    unittest.main()
