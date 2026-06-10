import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["CHATBOT_TEST_MODE"] = "1"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="chatbot-sales-store-logs-")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app import server  # noqa: E402
from app.retrievers import RetrievalResult  # noqa: E402
from app.sales_handoff import InMemorySalesHandoffService, StoredSalesHandoffService  # noqa: E402
from app.sales_handoff_store import (  # noqa: E402
    SQLiteHandoffStore,
    build_idempotency_key,
    mask_email,
    mask_phone,
)
from app.sales_state import SalesConversationState  # noqa: E402
from tools.inspect_sales_handoffs import inspect_handoffs  # noqa: E402


def draft(phone="0987654321", email="buyer@example.com", quantity=1, sku="SKU-1"):
    return {
        "tenant_id": "tenant-a",
        "conversation_id": "conv-a",
        "products": [{
            "sku": sku,
            "product_name": "Rèm cuốn test",
            "source_url": "https://example.test/p1",
            "price": 700000,
            "quantity": quantity,
        }],
        "contact": {"phone": phone, "email": email},
        "location": "Hà Nội",
        "address": "",
        "status": "draft",
    }


def hit(doc_id, product_name, sku, price, url):
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=product_name,
        text=f"{product_name} SKU {sku} giá {price} VND.",
        source=url,
        score=10.0,
        metadata={
            "doc_type": "product",
            "product_name": product_name,
            "category": "Rèm",
            "price": price,
            "currency": "VND",
            "sku": sku,
            "source_url": url,
        },
    )


class FakeRetriever:
    def __init__(self):
        self.hits = [
            hit("p1", "Rèm cuốn test", "SKU-1", 700000, "https://example.test/p1"),
            hit("p2", "Rèm vải test", "SKU-2", 900000, "https://example.test/p2"),
        ]

    def search(self, query: str, k: int = 4):
        return self.hits[:k]


class SQLiteHandoffStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "handoff.sqlite3")
        self.store = SQLiteHandoffStore(self.db_path)
        self.state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-a")

    def tearDown(self):
        self.tmp.cleanup()

    def test_sqlite_store_creates_schema(self):
        conn = sqlite3.connect(self.db_path)
        try:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        finally:
            conn.close()
        self.assertIn("handoff_requests", tables)
        self.assertIn("handoff_events", tables)

    def test_create_or_get_request_is_idempotent(self):
        payload = draft()
        key = build_idempotency_key(payload, self.state)

        first = self.store.create_or_get_request(payload, self.state, key)
        second = self.store.create_or_get_request(payload, self.state, key)

        self.assertEqual(first["handoff_id"], second["handoff_id"])
        self.assertEqual(self.store.total_count("tenant-a"), 1)

    def test_mark_sent_persists_sent(self):
        record = self.store.create_or_get_request(draft(), self.state, build_idempotency_key(draft(), self.state))

        sent = self.store.mark_sent(record["handoff_id"], {"ok": True})

        self.assertEqual(sent["status"], "sent")
        self.assertEqual(sent["confirmation_status"], "confirmed")
        self.assertIsNotNone(sent["sent_at"])

    def test_reload_store_keeps_record_and_duplicate_key(self):
        payload = draft()
        key = build_idempotency_key(payload, self.state)
        first = self.store.create_or_get_request(payload, self.state, key)
        reloaded = SQLiteHandoffStore(self.db_path)

        by_key = reloaded.get_by_idempotency_key(key)
        duplicate = reloaded.create_or_get_request(payload, self.state, key)

        self.assertEqual(by_key["handoff_id"], first["handoff_id"])
        self.assertEqual(duplicate["handoff_id"], first["handoff_id"])
        self.assertEqual(reloaded.total_count("tenant-a"), 1)

    def test_events_appended_and_masked(self):
        payload = draft()
        record = self.store.create_or_get_request(payload, self.state, build_idempotency_key(payload, self.state))
        self.store.append_event(record["handoff_id"], "custom", {"phone": "0987654321", "email": "buyer@example.com"})

        events = self.store.list_events(record["handoff_id"])
        event_text = json.dumps(events, ensure_ascii=False)

        self.assertGreaterEqual(len(events), 3)
        self.assertNotIn("0987654321", event_text)
        self.assertNotIn("buyer@example.com", event_text)
        self.assertIn(mask_phone("0987654321"), event_text)
        self.assertIn(mask_email("buyer@example.com"), event_text)

    def test_masked_summary_has_no_raw_contact(self):
        payload = draft()
        record = self.store.create_or_get_request(payload, self.state, build_idempotency_key(payload, self.state))
        summary_text = json.dumps(record["masked_summary"], ensure_ascii=False)

        self.assertNotIn("0987654321", summary_text)
        self.assertNotIn("buyer@example.com", summary_text)
        self.assertIn("098****321", summary_text)
        self.assertIn("b***@example.com", summary_text)

    def test_cancel_persists_cancelled(self):
        payload = draft()
        record = self.store.create_or_get_request(payload, self.state, build_idempotency_key(payload, self.state))

        cancelled = self.store.mark_cancelled(record["handoff_id"], "user_cancelled")

        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["confirmation_status"], "cancelled")
        self.assertIsNotNone(cancelled["cancelled_at"])

    def test_failure_persists_failed(self):
        payload = draft()
        record = self.store.create_or_get_request(payload, self.state, build_idempotency_key(payload, self.state))

        failed = self.store.mark_failed(record["handoff_id"], "boom")

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"], "boom")
        self.assertIsNotNone(failed["failed_at"])

    def test_inspect_cli_output_masks_contact(self):
        payload = draft()
        record = self.store.create_or_get_request(payload, self.state, build_idempotency_key(payload, self.state))
        self.store.append_event(record["handoff_id"], "custom", {"phone": "0987654321", "email": "buyer@example.com"})

        report = inspect_handoffs(self.db_path, tenant_id="tenant-a", include_events=True)
        text = json.dumps(report, ensure_ascii=False)

        self.assertEqual(report["total"], 1)
        self.assertNotIn("0987654321", text)
        self.assertNotIn("buyer@example.com", text)


class ServerSQLiteHandoffIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_kb = server.KB
        cls.previous_by_mode = dict(server.KB_BY_MODE)
        server.KB = FakeRetriever()
        server.KB_BY_MODE.clear()
        server.KB_BY_MODE["keyword"] = server.KB
        server._set_ready(True, None)
        cls.client = TestClient(server.app)

    @classmethod
    def tearDownClass(cls):
        server.KB = cls.previous_kb
        server.KB_BY_MODE.clear()
        server.KB_BY_MODE.update(cls.previous_by_mode)
        server.SALES_STATE_STORE.clear()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "server-handoff.sqlite3")
        self.previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_STATE_STORE.clear()
        server.SALES_HANDOFF_SERVICE = StoredSalesHandoffService(SQLiteHandoffStore(self.db_path))

    def tearDown(self):
        server.SALES_HANDOFF_SERVICE = self.previous_service
        server.SALES_STATE_STORE.clear()
        self.tmp.cleanup()

    def post(self, conversation_id, message, sales_mode="active"):
        return self.client.post(
            "/chat",
            json={
                "message": message,
                "history": [],
                "conversation_id": conversation_id,
                "tenant_id": "tenant-a",
                "channel": "web",
                "gen": {
                    "provider": "stub",
                    "mode": "general_compare",
                    "retrieval_mode": "keyword",
                    "retrieval_top_k": 4,
                    "answer_mode": "template",
                    "sales_mode": sales_mode,
                },
            },
        )

    def create_pending(self, conversation_id="sqlite-server"):
        self.post(conversation_id, "Có rèm nào dưới 1 triệu không?")
        self.post(conversation_id, "tôi lấy P1, số tôi 0987654321, email buyer@example.com")

    def test_server_active_confirm_with_sqlite_store_creates_record(self):
        self.create_pending("sqlite-active")

        response = self.post("sqlite-active", "ok gửi")

        payload = response.json()
        store = SQLiteHandoffStore(self.db_path)
        self.assertEqual(payload["debug"]["sales_action_taken"], "handoff_sent")
        self.assertEqual(store.total_count("tenant-a"), 1)
        self.assertEqual(store.count_by_status("tenant-a"), {"sent": 1})
        debug_text = json.dumps(payload["debug"], ensure_ascii=False)
        self.assertNotIn("0987654321", debug_text)
        self.assertNotIn("buyer@example.com", debug_text)

    def test_server_confirm_again_does_not_create_duplicate(self):
        self.create_pending("sqlite-duplicate")
        first = self.post("sqlite-duplicate", "ok gửi").json()
        second = self.post("sqlite-duplicate", "xác nhận").json()

        store = SQLiteHandoffStore(self.db_path)
        self.assertEqual(store.total_count("tenant-a"), 1)
        self.assertEqual(second["debug"]["sales_action_taken"], "handoff_already_sent")
        self.assertEqual(second["debug"]["handoff_id"], first["debug"]["handoff_id"])

    def test_duplicate_after_reloading_store_service_returns_same_handoff_id(self):
        self.create_pending("sqlite-reload")
        first = self.post("sqlite-reload", "ok gửi").json()
        server.SALES_HANDOFF_SERVICE = StoredSalesHandoffService(SQLiteHandoffStore(self.db_path))
        state = server.SALES_STATE_STORE[("tenant-a", "sqlite-reload")]
        state.confirmation_status = "pending"
        state.handoff_status = "pending_confirmation"

        second = self.post("sqlite-reload", "ok gửi").json()

        self.assertEqual(SQLiteHandoffStore(self.db_path).total_count("tenant-a"), 1)
        self.assertEqual(second["debug"]["sales_action_taken"], "handoff_already_sent")
        self.assertEqual(second["debug"]["handoff_id"], first["debug"]["handoff_id"])

    def test_sales_mode_off_does_not_write_store(self):
        response = self.post("sqlite-off", "tôi lấy P1, số tôi 0987654321", sales_mode="off")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SQLiteHandoffStore(self.db_path).total_count("tenant-a"), 0)

    def test_sales_mode_shadow_does_not_write_sent_handoff(self):
        self.post("sqlite-shadow", "Có rèm nào dưới 1 triệu không?", sales_mode="shadow")
        self.post("sqlite-shadow", "tôi lấy P1, số tôi 0987654321", sales_mode="shadow")
        self.post("sqlite-shadow", "ok gửi", sales_mode="shadow")

        self.assertEqual(SQLiteHandoffStore(self.db_path).count_by_status("tenant-a").get("sent", 0), 0)


class StoredSalesHandoffServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "service.sqlite3")
        self.store = SQLiteHandoffStore(self.db_path)
        self.service = StoredSalesHandoffService(self.store)
        self.state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-a")

    def tearDown(self):
        self.tmp.cleanup()

    def test_send_duplicate_after_reload_returns_existing_handoff(self):
        payload = draft()
        first = self.service.send_purchase_request(payload, self.state)
        reloaded = StoredSalesHandoffService(SQLiteHandoffStore(self.db_path))
        second = reloaded.send_purchase_request(payload, self.state)

        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertTrue(second.already_sent)
        self.assertEqual(second.handoff_id, first.handoff_id)
        self.assertEqual(SQLiteHandoffStore(self.db_path).total_count("tenant-a"), 1)


if __name__ == "__main__":
    unittest.main()
