import os
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ["CHATBOT_TEST_MODE"] = "1"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="chatbot-sales-runtime-logs-")

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


def _hit(doc_id, product_name, sku, price, url):
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=product_name,
        text=f"{product_name} là sản phẩm nội thất trong dữ liệu hiện có.",
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


class SalesRuntimeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SERVER_IMPORT_ERROR is not None:
            return
        cls.previous_kb = server.KB
        cls.previous_by_mode = dict(server.KB_BY_MODE)
        cls.previous_env_mode = os.environ.get("SALES_CONVERSATION_MODE")
        cls.kb = FakeRetriever([
            _hit("p1", "Rèm cuốn P1", "REM-P1", 700000, "https://example.test/rem-p1"),
            _hit("p2", "Rèm cuốn P2", "REM-P2", 900000, "https://example.test/rem-p2"),
        ])
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
        server.SALES_STATE_STORE.clear()
        if cls.previous_env_mode is None:
            os.environ.pop("SALES_CONVERSATION_MODE", None)
        else:
            os.environ["SALES_CONVERSATION_MODE"] = cls.previous_env_mode

    def setUp(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")
        os.environ.pop("SALES_CONVERSATION_MODE", None)
        server.SALES_STATE_STORE.clear()

    def _post(self, conversation_id, message, sales_mode=None, tenant_id="tenant-a", answer_mode="template"):
        reset_state(conversation_id)
        gen = {
            "provider": "stub",
            "mode": "general_compare",
            "retrieval_mode": "keyword",
            "retrieval_top_k": 4,
            "answer_mode": answer_mode,
        }
        if sales_mode is not None:
            gen["sales_mode"] = sales_mode
        return self.client.post(
            "/chat",
            json={
                "message": message,
                "history": [],
                "conversation_id": conversation_id,
                "tenant_id": tenant_id,
                "channel": "web",
                "gen": gen,
            },
        )

    def _turn(self, conversation_id, message, sales_mode="active", tenant_id="tenant-a", answer_mode="template"):
        gen = {
            "provider": "stub",
            "mode": "general_compare",
            "retrieval_mode": "keyword",
            "retrieval_top_k": 4,
            "answer_mode": answer_mode,
            "sales_mode": sales_mode,
        }
        return self.client.post(
            "/chat",
            json={
                "message": message,
                "history": [],
                "conversation_id": conversation_id,
                "tenant_id": tenant_id,
                "channel": "web",
                "gen": gen,
            },
        )

    def _turn_without_conversation_id(self, message, sales_mode="active", tenant_id="tenant-a", answer_mode="template"):
        return self.client.post(
            "/chat",
            json={
                "message": message,
                "history": [],
                "tenant_id": tenant_id,
                "channel": "web",
                "gen": {
                    "provider": "stub",
                    "mode": "general_compare",
                    "retrieval_mode": "keyword",
                    "retrieval_top_k": 4,
                    "answer_mode": answer_mode,
                    "sales_mode": sales_mode,
                },
            },
        )

    def test_default_off_keeps_old_behavior_without_sales_debug(self):
        response = self._post("sales-default-off", "Có rèm nào dưới 1 triệu không?", sales_mode=None)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"], "product-template")
        self.assertNotIn("sales_mode", payload["debug"])
        self.assertNotEqual(payload["model"], "sales-template")

    def test_shadow_updates_debug_and_recommendations_without_reply_override(self):
        response = self._post("sales-shadow", "Có rèm nào dưới 1 triệu không?", sales_mode="shadow")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"], "product-template")
        self.assertEqual(payload["debug"]["sales_mode"], "shadow")
        self.assertEqual(payload["debug"]["last_recommended_count"], 2)
        self.assertEqual(payload["debug"]["sales_action_taken"], "none")

    def test_state_persists_and_resolves_second_product(self):
        conversation_id = "sales-persist"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="shadow")

        response = self._turn(conversation_id, "Tôi lấy mẫu thứ 2", sales_mode="active")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"], "sales-template")
        self.assertEqual(payload["debug"]["selected_products"][0]["sku"], "REM-P2")
        self.assertEqual(payload["debug"]["purchase_request_status"], "needs_contact")

    def test_discover_purchase_intent_asks_for_missing_context(self):
        response = self._turn("sales-discover-sofa", "Tôi muốn mua sofa", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["model"], "sales-template")
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_discovery")
        self.assertIn("room_or_space", payload["debug"]["missing_slots"])
        self.assertFalse(payload.get("trigger_purchase_request"))
        self.assertIn("phòng", payload["reply"].lower())

    def test_handle_objection_gets_controlled_reply(self):
        response = self._turn("sales-objection-price", "Mẫu này đắt quá", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["model"], "sales-template")
        self.assertEqual(payload["debug"]["sales_action_taken"], "handle_objection")
        self.assertEqual(payload["debug"]["objection_type"], "too_expensive")
        self.assertIn("ngân sách", payload["reply"].lower())

    def test_suggest_with_context_stays_rag_grounded(self):
        response = self._turn("sales-suggest-rag", "Tôi cần rèm cho phòng khách ngân sách dưới 1 triệu", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["model"], "product-template")
        self.assertGreaterEqual(payload["debug"]["retrieval_count"], 1)
        self.assertEqual(payload["debug"]["sales_action_taken"], "none")
        self.assertIn("Rèm cuốn", payload["reply"])

    def test_market_price_mode_never_handoff_even_with_purchase_text(self):
        response = self._turn("sales-market-guard", "Tôi muốn mua sofa, số tôi 0987654321", sales_mode="active", answer_mode="llm")
        payload = response.json()

        self.assertNotEqual(payload["debug"].get("sales_action_taken"), "ask_confirmation")
        self.assertFalse(payload.get("trigger_purchase_request"))

    def test_active_purchase_needs_contact(self):
        conversation_id = "sales-needs-contact"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")

        response = self._turn(conversation_id, "Tôi lấy P1", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["model"], "sales-template")
        self.assertIn("số điện thoại hoặc email", payload["reply"])
        self.assertEqual(payload["debug"]["purchase_request_status"], "needs_contact")
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_contact")

    def test_active_purchase_creates_draft_without_order_confirmation(self):
        conversation_id = "sales-draft"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")

        response = self._turn(conversation_id, "Tôi lấy P1, số tôi 0987654321", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["debug"]["purchase_request_status"], "draft")
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_confirmation")
        self.assertEqual(payload["debug"]["confirmation_status"], "pending")
        self.assertEqual(payload["debug"]["handoff_status"], "pending_confirmation")
        self.assertIn("yêu cầu mua hàng nháp", payload["reply"])
        self.assertIn("xác nhận gửi", payload["reply"])
        self.assertNotIn("order confirmed", payload["reply"].lower())
        self.assertNotIn("đơn hàng đã chốt", payload["reply"].lower().replace("chưa phải đơn hàng đã chốt", ""))

    def test_contact_only_after_previous_purchase_completes_draft(self):
        conversation_id = "sales-contact-later"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")
        self._turn(conversation_id, "Tôi lấy P1", sales_mode="active")

        response = self._turn(conversation_id, "0987654321", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["debug"]["purchase_request_status"], "draft")
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_confirmation")
        self.assertEqual(payload["debug"]["confirmation_status"], "pending")

    def test_cancel_after_draft(self):
        conversation_id = "sales-cancel"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")
        self._turn(conversation_id, "Tôi lấy P1, số tôi 0987654321", sales_mode="active")

        response = self._turn(conversation_id, "thôi hủy", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["debug"]["purchase_request_status"], "cancelled")
        self.assertEqual(payload["debug"]["sales_action_taken"], "confirmation_cancelled")
        self.assertFalse(payload["debug"]["handoff_required"])

    def test_handoff_requests_contact(self):
        response = self._turn("sales-handoff", "cho tôi gặp tư vấn viên", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["debug"]["sales_action_taken"], "handoff")
        self.assertTrue(payload["debug"]["handoff_required"])
        self.assertIn("số điện thoại hoặc email", payload["reply"])

    def test_tenant_isolation(self):
        conversation_id = "sales-tenant-isolation"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="shadow", tenant_id="tenant-a")

        response = self._turn(conversation_id, "Tôi lấy P1", sales_mode="active", tenant_id="tenant-b")

        payload = response.json()
        self.assertEqual(payload["debug"]["purchase_request_status"], "needs_product")
        self.assertEqual(payload["debug"]["selected_products"], [])
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_product")

    def test_request_off_overrides_env_active(self):
        os.environ["SALES_CONVERSATION_MODE"] = "active"

        response = self._post("sales-env-override", "Tôi lấy P1, số tôi 0987654321", sales_mode="off", answer_mode="llm")

        payload = response.json()
        self.assertNotEqual(payload["model"], "sales-template")
        self.assertNotIn("sales_mode", payload["debug"])

    def test_template_answer_mode_still_handles_product_query_in_active_mode(self):
        response = self._post("sales-template-active", "Có rèm nào dưới 1 triệu không?", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["model"], "product-template")
        self.assertIn("Rèm cuốn P1", payload["reply"])
        self.assertEqual(payload["debug"]["sales_mode"], "active")
        self.assertEqual(payload["debug"]["sales_action_taken"], "none")

    def test_product_reference_questions_do_not_create_purchase_draft(self):
        conversation_id = "sales-reference-questions"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")
        questions = [
            "P1 có kích thước bao nhiêu?",
            "mẫu thứ 2 có chất liệu gì?",
            "so sánh P1 với P2",
            "mẫu 2 đắt không?",
            "P1 còn màu khác không?",
            "cho tôi xem kỹ P2",
        ]

        for idx, question in enumerate(questions):
            with self.subTest(question=question):
                response = self._turn(f"{conversation_id}-{idx}", "Có rèm nào dưới 1 triệu không?", sales_mode="active")
                self.assertEqual(response.status_code, 200)
                response = self._turn(f"{conversation_id}-{idx}", question, sales_mode="active")
                payload = response.json()
                self.assertEqual(payload["model"], "product-template")
                self.assertEqual(payload["debug"]["sales_action_taken"], "none")
                self.assertIsNone(payload["debug"]["purchase_request_status"])
                self.assertNotIn("yêu cầu mua hàng nháp", payload["reply"])

    def test_contact_with_reference_without_purchase_context_does_not_override(self):
        conversation_id = "sales-contact-with-reference-no-context"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")

        response = self._turn(conversation_id, "P1, số tôi 0987654321", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["model"], "product-template")
        self.assertEqual(payload["debug"]["sales_action_taken"], "none")
        self.assertIsNone(payload["debug"]["purchase_request_status"])

    def test_contact_with_reference_after_needs_contact_creates_draft(self):
        conversation_id = "sales-contact-reference-after-needs-contact"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")
        self._turn(conversation_id, "Tôi lấy P1", sales_mode="active")

        response = self._turn(conversation_id, "P1, số tôi 0987654321", sales_mode="active")

        payload = response.json()
        self.assertEqual(payload["model"], "sales-template")
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_confirmation")
        self.assertEqual(payload["debug"]["purchase_request_status"], "draft")

    def test_missing_conversation_id_uses_ephemeral_sales_state(self):
        first = self._turn_without_conversation_id("Có rèm nào dưới 1 triệu không?", sales_mode="shadow")
        second = self._turn_without_conversation_id("Tôi lấy P1", sales_mode="active")

        first_payload = first.json()
        second_payload = second.json()
        self.assertFalse(first_payload["debug"]["sales_state_persistent"])
        self.assertEqual(first_payload["debug"]["sales_state_warning"], "missing_conversation_id_ephemeral_state")
        self.assertFalse(second_payload["debug"]["sales_state_persistent"])
        self.assertEqual(second_payload["debug"]["purchase_request_status"], "needs_product")
        self.assertEqual(second_payload["debug"]["selected_products"], [])
        self.assertEqual(server.SALES_STATE_STORE, {})

    def test_sales_debug_masks_contact_details(self):
        conversation_id = "sales-debug-mask"
        self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")

        response = self._turn(conversation_id, "Tôi lấy P1, số tôi 0987654321, email buyer@example.com", sales_mode="active")

        debug_text = json.dumps(response.json()["debug"], ensure_ascii=False)
        self.assertNotIn("0987654321", debug_text)
        self.assertNotIn("buyer@example.com", debug_text)

    def test_sales_state_ttl_cleanup_removes_expired_state(self):
        state = server.SalesConversationState(tenant_id="tenant-a", conversation_id="old-conv")
        state.updated_at = time.time() - server.SALES_STATE_TTL_SECONDS - 5
        server.SALES_STATE_STORE[("tenant-a", "old-conv")] = state

        expired = server._cleanup_sales_states()

        self.assertEqual(expired, 1)
        self.assertNotIn(("tenant-a", "old-conv"), server.SALES_STATE_STORE)

    def test_confirm_pending_calls_fake_handoff_once(self):
        conversation_id = "sales-confirm-handoff"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")
            self._turn(conversation_id, "Tôi lấy P1, số tôi 0987654321", sales_mode="active")

            response = self._turn(conversation_id, "ok gửi", sales_mode="active")

            payload = response.json()
            self.assertEqual(payload["debug"]["sales_action_taken"], "handoff_sent")
            self.assertEqual(payload["debug"]["confirmation_status"], "confirmed")
            self.assertEqual(payload["debug"]["handoff_status"], "sent")
            self.assertEqual(len(service.sent_payloads), 1)
            self.assertIn("Mã yêu cầu", payload["reply"])
            self.assertNotIn("đã chốt đơn", payload["reply"].lower())
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_repeated_confirm_does_not_send_duplicate(self):
        conversation_id = "sales-confirm-idempotent"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")
            self._turn(conversation_id, "Tôi lấy P1, số tôi 0987654321", sales_mode="active")
            first = self._turn(conversation_id, "ok gửi", sales_mode="active").json()
            second = self._turn(conversation_id, "xác nhận", sales_mode="active").json()

            self.assertEqual(len(service.sent_payloads), 1)
            self.assertEqual(second["debug"]["sales_action_taken"], "handoff_already_sent")
            self.assertEqual(second["debug"]["handoff_id"], first["debug"]["handoff_id"])
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_confirm_without_pending_does_not_call_handoff(self):
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            response = self._turn("sales-confirm-no-pending", "ok gửi", sales_mode="active")

            payload = response.json()
            self.assertEqual(payload["model"], "sales-template")
            self.assertEqual(payload["debug"]["sales_action_taken"], "confirmation_without_pending")
            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_confirm_with_missing_contact_does_not_call_handoff(self):
        conversation_id = "sales-confirm-missing-contact"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "CÃ³ rÃ¨m nÃ o dÆ°á»›i 1 triá»‡u khÃ´ng?", sales_mode="active")
            self._turn(conversation_id, "TÃ´i láº¥y P1", sales_mode="active")

            response = self._turn(conversation_id, "ok gá»­i", sales_mode="active")

            payload = response.json()
            self.assertEqual(payload["debug"]["sales_action_taken"], "confirmation_without_pending")
            self.assertEqual(payload["debug"]["purchase_request_status"], "needs_contact")
            self.assertEqual(payload["debug"]["confirmation_status"], "none")
            self.assertEqual(payload["debug"]["handoff_status"], "not_ready")
            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_confirm_with_missing_product_does_not_call_handoff(self):
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            response = self._turn("sales-confirm-missing-product", "TÃ´i muá»‘n mua, sá»‘ tÃ´i 0987654321", sales_mode="active")
            self.assertEqual(response.json()["debug"]["purchase_request_status"], "needs_product")

            response = self._turn("sales-confirm-missing-product", "xÃ¡c nháº­n", sales_mode="active")

            payload = response.json()
            self.assertEqual(payload["debug"]["sales_action_taken"], "confirmation_without_pending")
            self.assertEqual(payload["debug"]["purchase_request_status"], "needs_product")
            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_confirm_after_cancel_does_not_call_handoff(self):
        conversation_id = "sales-confirm-after-cancel"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "CÃ³ rÃ¨m nÃ o dÆ°á»›i 1 triá»‡u khÃ´ng?", sales_mode="active")
            self._turn(conversation_id, "TÃ´i láº¥y P1, sá»‘ tÃ´i 0987654321", sales_mode="active")
            self._turn(conversation_id, "khÃ´ng gá»­i", sales_mode="active")

            response = self._turn(conversation_id, "ok gá»­i", sales_mode="active")

            payload = response.json()
            self.assertEqual(payload["debug"]["sales_action_taken"], "confirmation_without_pending")
            self.assertEqual(payload["debug"]["confirmation_status"], "cancelled")
            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_confirm_after_state_missing_does_not_call_handoff(self):
        conversation_id = "sales-confirm-state-missing"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "CÃ³ rÃ¨m nÃ o dÆ°á»›i 1 triá»‡u khÃ´ng?", sales_mode="active")
            self._turn(conversation_id, "TÃ´i láº¥y P1, sá»‘ tÃ´i 0987654321", sales_mode="active")
            server.SALES_STATE_STORE.clear()

            response = self._turn(conversation_id, "ok gá»­i", sales_mode="active")

            payload = response.json()
            self.assertEqual(payload["debug"]["sales_action_taken"], "confirmation_without_pending")
            self.assertEqual(payload["debug"]["confirmation_status"], "none")
            self.assertEqual(payload["debug"]["handoff_status"], "not_ready")
            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_handoff_failure_updates_status_and_safe_reply(self):
        conversation_id = "sales-handoff-failure"
        service = server.InMemorySalesHandoffService(fail_next=True)
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="active")
            self._turn(conversation_id, "Tôi lấy P1, số tôi 0987654321", sales_mode="active")

            response = self._turn(conversation_id, "ok gửi", sales_mode="active")

            payload = response.json()
            self.assertEqual(payload["debug"]["sales_action_taken"], "handoff_failed")
            self.assertEqual(payload["debug"]["handoff_status"], "failed")
            self.assertIn("chưa gửi được", payload["reply"])
            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_handoff_failure_can_retry_on_explicit_confirm(self):
        conversation_id = "sales-handoff-failure-retry"
        service = server.InMemorySalesHandoffService(fail_next=True)
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "CÃ³ rÃ¨m nÃ o dÆ°á»›i 1 triá»‡u khÃ´ng?", sales_mode="active")
            self._turn(conversation_id, "TÃ´i láº¥y P1, sá»‘ tÃ´i 0987654321", sales_mode="active")
            failed = self._turn(conversation_id, "ok gá»­i", sales_mode="active").json()
            retried = self._turn(conversation_id, "xÃ¡c nháº­n", sales_mode="active").json()

            self.assertEqual(failed["debug"]["sales_action_taken"], "handoff_failed")
            self.assertEqual(retried["debug"]["sales_action_taken"], "handoff_sent")
            self.assertEqual(len(service.sent_payloads), 1)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_cancel_after_sent_keeps_handoff_sent(self):
        conversation_id = "sales-cancel-after-sent"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "CÃ³ rÃ¨m nÃ o dÆ°á»›i 1 triá»‡u khÃ´ng?", sales_mode="active")
            self._turn(conversation_id, "TÃ´i láº¥y P1, sá»‘ tÃ´i 0987654321", sales_mode="active")
            self._turn(conversation_id, "ok gá»­i", sales_mode="active")

            response = self._turn(conversation_id, "huy", sales_mode="active")

            payload = response.json()
            self.assertEqual(payload["debug"]["sales_action_taken"], "handoff_already_sent")
            self.assertEqual(payload["debug"]["handoff_status"], "sent")
            self.assertEqual(payload["debug"]["confirmation_status"], "confirmed")
            self.assertEqual(len(service.sent_payloads), 1)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_pending_update_quantity_keeps_confirmation_pending_without_handoff(self):
        conversation_id = "sales-pending-update-quantity"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "CÃ³ rÃ¨m nÃ o dÆ°á»›i 1 triá»‡u khÃ´ng?", sales_mode="active")
            self._turn(conversation_id, "TÃ´i láº¥y P1, sá»‘ tÃ´i 0987654321", sales_mode="active")

            response = self._turn(conversation_id, "sua lai lay 2 cai", sales_mode="active")

            payload = response.json()
            state = server.SALES_STATE_STORE[("tenant-a", conversation_id)]
            self.assertEqual(payload["debug"]["sales_action_taken"], "ask_confirmation")
            self.assertEqual(payload["debug"]["confirmation_status"], "pending")
            self.assertEqual(payload["debug"]["handoff_status"], "pending_confirmation")
            self.assertEqual(state.purchase_request["products"][0]["quantity"], 2)
            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_pending_update_contact_keeps_confirmation_pending_without_raw_debug(self):
        conversation_id = "sales-pending-update-contact"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "CÃ³ rÃ¨m nÃ o dÆ°á»›i 1 triá»‡u khÃ´ng?", sales_mode="active")
            self._turn(conversation_id, "TÃ´i láº¥y P1, sá»‘ tÃ´i 0987654321", sales_mode="active")

            response = self._turn(conversation_id, "doi so thanh 0987654322", sales_mode="active")

            payload = response.json()
            debug_text = json.dumps(payload["debug"], ensure_ascii=False)
            state = server.SALES_STATE_STORE[("tenant-a", conversation_id)]
            self.assertEqual(payload["debug"]["sales_action_taken"], "ask_confirmation")
            self.assertEqual(payload["debug"]["confirmation_status"], "pending")
            self.assertEqual(state.purchase_request["contact"]["phone"], "0987654322")
            self.assertNotIn("0987654322", debug_text)
            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_pending_update_product_keeps_confirmation_pending_without_handoff(self):
        conversation_id = "sales-pending-update-product"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "CÃ³ rÃ¨m nÃ o dÆ°á»›i 1 triá»‡u khÃ´ng?", sales_mode="active")
            self._turn(conversation_id, "TÃ´i láº¥y P1, sá»‘ tÃ´i 0987654321", sales_mode="active")

            response = self._turn(conversation_id, "thoi lay P2", sales_mode="active")

            payload = response.json()
            self.assertEqual(payload["debug"]["sales_action_taken"], "ask_confirmation")
            self.assertEqual(payload["debug"]["confirmation_status"], "pending")
            self.assertEqual(payload["debug"]["selected_products"][0]["sku"], "REM-P2")
            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_tenant_b_cannot_confirm_tenant_a_pending_draft(self):
        conversation_id = "sales-tenant-confirm-isolation"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "CÃ³ rÃ¨m nÃ o dÆ°á»›i 1 triá»‡u khÃ´ng?", sales_mode="active", tenant_id="tenant-a")
            self._turn(conversation_id, "TÃ´i láº¥y P1, sá»‘ tÃ´i 0987654321", sales_mode="active", tenant_id="tenant-a")

            tenant_b = self._turn(conversation_id, "ok gá»­i", sales_mode="active", tenant_id="tenant-b").json()
            tenant_a = self._turn(conversation_id, "ok gá»­i", sales_mode="active", tenant_id="tenant-a").json()

            self.assertEqual(tenant_b["debug"]["sales_action_taken"], "confirmation_without_pending")
            self.assertEqual(tenant_b["debug"]["handoff_status"], "not_ready")
            self.assertEqual(tenant_a["debug"]["sales_action_taken"], "handoff_sent")
            self.assertEqual(tenant_a["debug"]["handoff_status"], "sent")
            self.assertEqual(len(service.sent_payloads), 1)
            self.assertEqual(service.sent_payloads[0]["tenant_id"], "tenant-a")
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service

    def test_shadow_mode_does_not_call_handoff_on_confirm(self):
        conversation_id = "sales-shadow-no-handoff"
        service = server.InMemorySalesHandoffService()
        previous_service = server.SALES_HANDOFF_SERVICE
        server.SALES_HANDOFF_SERVICE = service
        try:
            self._turn(conversation_id, "Có rèm nào dưới 1 triệu không?", sales_mode="shadow")
            self._turn(conversation_id, "Tôi lấy P1, số tôi 0987654321", sales_mode="shadow")
            self._turn(conversation_id, "ok gửi", sales_mode="shadow")

            self.assertEqual(len(service.sent_payloads), 0)
        finally:
            server.SALES_HANDOFF_SERVICE = previous_service


if __name__ == "__main__":
    unittest.main()
