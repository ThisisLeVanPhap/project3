import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["CHATBOT_TEST_MODE"] = "1"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="chatbot-smoke-handoff-logs-")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.sales_handoff_store import SQLiteHandoffStore  # noqa: E402
from tools.smoke_handoff_e2e import (  # noqa: E402
    SMOKE_EMAIL,
    SMOKE_PHONE,
    SmokeConfig,
    configure_environment,
    run_smoke_flow,
)


class FakeSmokeChatClient:
    def __init__(self, handoff_id="handoff_fake", sent_count_after_first=1):
        self.handoff_id = handoff_id
        self.calls = []
        self._sent_count = 0
        self.sent_count_after_first = sent_count_after_first

    def post_turn(self, message):
        self.calls.append(message)
        if message == "ok gui":
            self._sent_count = self.sent_count_after_first
            return {
                "_http_status": 200,
                "model": "sales-template",
                "debug": {
                    "sales_action_taken": "handoff_sent",
                    "handoff_status": "sent",
                    "confirmation_status": "confirmed",
                    "handoff_id": self.handoff_id,
                },
            }
        if message == "xac nhan":
            return {
                "_http_status": 200,
                "model": "sales-template",
                "debug": {
                    "sales_action_taken": "handoff_already_sent",
                    "handoff_status": "sent",
                    "confirmation_status": "confirmed",
                    "handoff_id": self.handoff_id,
                },
            }
        return {
            "_http_status": 200,
            "model": "sales-template",
            "debug": {
                "sales_action_taken": "ask_confirmation",
                "handoff_status": "pending_confirmation",
                "confirmation_status": "pending",
                "handoff_id": self.handoff_id,
            },
        }

    def handoff_sent_count(self):
        return self._sent_count


class SmokeHandoffE2ETests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "smoke.sqlite3")
        self.store = SQLiteHandoffStore(self.db_path)
        self.config = SmokeConfig(
            chatbot_kb_dir="chatbot/kb/demo-tenant-products",
            backend_url="http://localhost:8080",
            service_token="test-token",
            tenant_id="tenant-a",
            conversation_id="conv-smoke",
            db=self.db_path,
            output=os.path.join(self.tmp.name, "report.json"),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def seed_sent_record(self, handoff_id="handoff_fake"):
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO handoff_requests (
                    handoff_id, tenant_id, conversation_id, idempotency_key, status,
                    confirmation_status, purchase_request_status, created_at, updated_at,
                    sent_at, payload_json, masked_summary_json, external_id, correlation_id,
                    adapter_name, retryable
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    handoff_id,
                    "tenant-a",
                    "conv-smoke",
                    "idem-fake",
                    "sent",
                    "confirmed",
                    "draft",
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:01+00:00",
                    "2026-01-01T00:00:01+00:00",
                    "{}",
                    "{}",
                    "321",
                    "corr_fake",
                    "http",
                    0,
                ),
            )

    def test_smoke_report_passes_and_masks_contact(self):
        self.seed_sent_record()
        client = FakeSmokeChatClient()

        report = run_smoke_flow(self.config, client, self.store)
        text = json.dumps(report, ensure_ascii=False)

        self.assertTrue(report["passed"])
        self.assertEqual(report["backend_endpoint"], "http://localhost:8080/api/chatbot/purchase-requests")
        self.assertEqual(report["handoff_id"], "handoff_fake")
        self.assertEqual(report["external_id"], "321")
        self.assertEqual(report["sqlite_status"], "sent")
        self.assertTrue(report["duplicate_safe"])
        self.assertEqual(report["admin_visible"], "skipped")
        self.assertNotIn(SMOKE_PHONE, text)
        self.assertNotIn(SMOKE_EMAIL, text)

    def test_smoke_report_fails_when_duplicate_creates_new_record(self):
        self.seed_sent_record()

        class DuplicateUnsafeClient(FakeSmokeChatClient):
            def post_turn(self, message):
                response = super().post_turn(message)
                if message == "xac nhan":
                    with self.store.connect() as conn:
                        conn.execute(
                            """
                            INSERT INTO handoff_requests (
                                handoff_id, tenant_id, conversation_id, idempotency_key, status,
                                created_at, updated_at, payload_json, masked_summary_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                "handoff_duplicate",
                                "tenant-a",
                                "conv-smoke",
                                "idem-duplicate",
                                "sent",
                                "2026-01-01T00:00:02+00:00",
                                "2026-01-01T00:00:02+00:00",
                                "{}",
                                "{}",
                            ),
                        )
                return response

        client = DuplicateUnsafeClient()
        client.store = self.store

        report = run_smoke_flow(self.config, client, self.store)

        self.assertFalse(report["passed"])
        self.assertFalse(report["duplicate_safe"])
        self.assertIn("duplicate confirm was not safe", report["errors"])

    def test_configure_environment_sets_http_adapter_env(self):
        configure_environment(self.config)

        self.assertEqual(os.environ["KB_DIR"], self.config.chatbot_kb_dir)
        self.assertEqual(os.environ["SALES_HANDOFF_STORE"], "sqlite")
        self.assertEqual(os.environ["SALES_HANDOFF_DB_PATH"], self.config.db)
        self.assertEqual(os.environ["SALES_HANDOFF_ADAPTER"], "http")
        self.assertEqual(
            os.environ["SALES_HANDOFF_ENDPOINT"],
            "http://localhost:8080/api/chatbot/purchase-requests",
        )
        self.assertEqual(os.environ["SALES_HANDOFF_SERVICE_TOKEN"], "test-token")


if __name__ == "__main__":
    unittest.main()
