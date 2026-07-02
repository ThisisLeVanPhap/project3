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


def _hit(doc_id, product_name, sku, price, url, category="Rèm"):
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
            "category": category,
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

    def _turn(self, conversation_id, message, sales_mode="active", tenant_id="tenant-a", answer_mode="template", mode="general_compare"):
        gen = {
            "provider": "stub",
            "mode": mode,
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

    def test_tenant_sales_filters_products_by_requested_category(self):
        # Override KB with mixed-category products
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            mixed_kb = FakeRetriever([
                _hit("ghe-vp", "Ghế văn phòng Ergo", "GHE-001", 2300000, "https://example.test/ghe-vp"),
                _hit("vach-ngan", "Vách ngăn trang trí GHO-595", "GHO-595", 2100000, "https://example.test/vach-ngan"),
                _hit("den-tha", "Đèn thả trần GHO-256", "GHO-256", 400000, "https://example.test/den-tha"),
            ])
            server.KB = mixed_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = mixed_kb

            conv_id = "sales-category-filter"
            response = self._turn(conv_id, "tư vấn ghế văn phòng dưới 3 triệu",
                                  sales_mode="active", mode="tenant_sales", answer_mode="template")

            payload = response.json()
            self.assertEqual(payload["model"], "product-template")
            reply = payload["reply"]
            self.assertIn("Ghế văn phòng", reply)
            self.assertNotIn("Vách ngăn", reply)
            self.assertNotIn("Đèn thả trần", reply)
            self.assertNotIn("GHO-595", reply)
            self.assertNotIn("GHO-256", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_vague_ghe_query_does_not_list_products_in_active_mode(self):
        response = self._turn("sales-vague-ghe", "tu van t 1 cai ghe di", sales_mode="active")
        payload = response.json()
        self.assertEqual(payload["model"], "sales-template")
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_discovery")
        self.assertEqual(payload["debug"]["current_stage"], "discover")
        self.assertEqual(payload["debug"]["next_best_action"], "ask_discovery_question")
        reply = payload["reply"]
        self.assertNotIn("Mình tìm thấy", reply)
        self.assertNotIn("một số sản phẩm", reply)
        self.assertNotIn("[P", reply)
        self.assertNotIn("Link nguồn:", reply)
        self.assertNotIn("https://", reply)
        # Should ask about purpose/use of the chair
        self.assertIn("ghế", reply.lower())
        self.assertIn("mục đích", reply)

    def test_vague_sofa_query_does_not_list_products_in_active_mode(self):
        response = self._turn("sales-vague-sofa", "goi y sofa di", sales_mode="active")
        payload = response.json()
        self.assertEqual(payload["model"], "sales-template")
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_discovery")
        self.assertEqual(payload["debug"]["current_stage"], "discover")
        self.assertEqual(payload["debug"]["next_best_action"], "ask_discovery_question")
        reply = payload["reply"]
        self.assertNotIn("Mình tìm thấy", reply)
        self.assertNotIn("một số sản phẩm", reply)
        self.assertNotIn("[P", reply)
        self.assertNotIn("Link nguồn:", reply)
        self.assertNotIn("https://", reply)
        # Should ask about space/room for the sofa
        self.assertIn("sofa", reply.lower())
        self.assertIn("không gian", reply)

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
        # Phase 7: vague purchase intent without specific product -> ask_discovery
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_discovery")
        self.assertIn("sofa", payload["reply"].lower())
        self.assertIn("không gian", payload["reply"].lower())
        self.assertFalse(payload.get("trigger_purchase_request"))

    def test_sku_purchase_intent_resolves_and_asks_contact(self):
        """First-turn SKU + purchase_intent: resolve from KB, ask contact, not discovery/product."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            sku_kb = FakeRetriever([
                _hit("den-gho239", "Đèn thả trần trang trí GHO-239", "GHO-239", 450000,
                     "https://example.test/den-gho239", category="Đèn"),
            ])
            server.KB = sku_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = sku_kb

            conv_id = "sales-sku-resolve"
            response = self._turn(conv_id, "Đèn thả trần trang trí kiểu dáng đẹp và giá rẻ GHO-239 mẫu a hay đấy, t muốn mua",
                                  sales_mode="active", mode="tenant_sales")
            payload = response.json()
            self.assertEqual(payload["model"], "sales-template")
            self.assertEqual(payload["debug"]["sales_action_taken"], "ask_contact")
            self.assertGreater(len(payload["debug"]["selected_products"]), 0)
            sp = payload["debug"]["selected_products"][0]
            real_url = "https://example.test/den-gho239"
            self.assertEqual(sp.get("source_url"), real_url)
            # purchase_request_status should reflect resolved product (needs contact, not product)
            pr_status = payload["debug"].get("purchase_request_status")
            self.assertNotEqual(pr_status, "needs_product", msg=f"status was {pr_status}")
            reply = payload["reply"]
            self.assertIn("GHO-239", reply)
            self.assertIn("Đèn thả trần", reply)
            self.assertIn(real_url, reply)
            self.assertNotIn("Sản phẩm mã", reply)
            self.assertNotIn("Bạn chia sẻ thêm 1–2 ưu tiên", reply)
            self.assertNotIn("Mình chưa tìm thấy", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_sku_purchase_multi_turn_preserves_selected_product(self):
        """Multi-turn: SKU resolve first turn, follow-up preserves product context."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            sku_kb = FakeRetriever([
                _hit("den-gho239", "Đèn thả trần trang trí GHO-239", "GHO-239", 450000,
                     "https://example.test/den-gho239", category="Đèn"),
            ])
            server.KB = sku_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = sku_kb

            conv_id = "sales-sku-multi"
            turn1 = self._turn(conv_id,
                "Đèn thả trần trang trí kiểu dáng đẹp và giá rẻ GHO-239 mẫu a hay đấy, t muốn mua",
                sales_mode="active", mode="tenant_sales")
            p1 = turn1.json()
            self.assertIn("GHO-239", p1["reply"])

            turn2 = self._turn(conv_id, "phòng học đi của tôi đi",
                               sales_mode="active", mode="tenant_sales")
            p2 = turn2.json()
            reply2 = p2["reply"]
            self.assertNotIn("Mình chưa tìm thấy sản phẩm phù hợp", reply2)
            self.assertNotIn("Mình chưa tìm thấy thông tin", reply2)
            # Verify selected product is still the real KB product (not synthetic/fallback)
            sp2 = p2["debug"].get("selected_products", [])
            self.assertGreater(len(sp2), 0)
            sp2_first = sp2[0]
            self.assertEqual(sp2_first.get("sku"), "GHO-239")
            self.assertEqual(sp2_first.get("source_url"), "https://example.test/den-gho239")
            self.assertNotIn("Sản phẩm mã", sp2_first.get("product_name", ""))
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_sku_not_in_kb_does_not_create_fake_product(self):
        """SKU not in KB: no synthetic selected_product, ask_product with clear message."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            # KB has GHO-239 but user asks for GHO-999
            sku_kb = FakeRetriever([
                _hit("den-gho239", "Đèn thả trần trang trí GHO-239", "GHO-239", 450000,
                     "https://example.test/den-gho239", category="Đèn"),
            ])
            server.KB = sku_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = sku_kb

            conv_id = "sales-sku-notfound"
            response = self._turn(conv_id, "GHO-999 t muốn mua",
                                  sales_mode="active", mode="tenant_sales")
            payload = response.json()
            self.assertEqual(payload["model"], "sales-template")
            selected = payload["debug"].get("selected_products", [])
            self.assertEqual(len(selected), 0)
            reply = payload["reply"]
            self.assertIn("GHO-999", reply)
            self.assertNotIn("Sản phẩm mã", reply)
            self.assertNotIn("Bạn chia sẻ thêm 1–2 ưu tiên", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_fresh_ghp_phong_khach_purchase_does_not_list(self):
        """Phase 7: fresh 'tôi muốn mua ghế cho phòng khách' -> ask_discovery, not listing."""
        response = self._turn("sales-fresh-ghp", "tôi muốn mua ghế cho phòng khách",
                              sales_mode="active", mode="tenant_sales")
        payload = response.json()
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_discovery")
        self.assertEqual(payload["debug"]["current_stage"], "discover")
        reply = payload["reply"]
        self.assertNotIn("Bạn muốn đặt sản phẩm nào", reply)
        self.assertNotIn("P1", reply)
        self.assertNotIn("Mình tìm thấy", reply)
        self.assertNotIn("[P", reply)
        self.assertNotEqual(payload["model"], "product-template")

    def test_room_level_consultation_does_not_list(self):
        """Phase 7B: 'tôi muốn tìm đồ cho phòng khách' -> ask_discovery, no listing."""
        response = self._turn("sales-room-level", "tôi muốn tìm đồ cho phòng khách",
                              sales_mode="active", mode="tenant_sales")
        payload = response.json()
        self.assertEqual(payload["debug"]["sales_action_taken"], "ask_discovery")
        self.assertEqual(payload["debug"]["current_stage"], "discover")
        reply = payload["reply"]
        self.assertNotIn("Bạn muốn đặt sản phẩm nào", reply)
        self.assertNotIn("P1", reply)
        self.assertNotIn("Mình tìm thấy", reply)
        self.assertNotIn("[P", reply)

    def test_multi_turn_tu_tivi_does_not_list(self):
        """Phase 7B: room consult -> 'thiếu tủ để ti vi' -> ask_discovery, not listing."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            mock_kb = FakeRetriever([
                _hit("tu-tivi", "Kệ tivi gỗ", "TU-001", 5000000,
                     "https://example.test/tu-tivi", category="Tủ"),
            ])
            server.KB = mock_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = mock_kb

            conv_id = "sales-tu-tivi"
            self._turn(conv_id, "tôi muốn tìm đồ cho phòng khách",
                       sales_mode="active", mode="tenant_sales")

            response = self._turn(conv_id, "nhà tôi đang thiếu tủ để ti vi",
                                  sales_mode="active", mode="tenant_sales")
            payload = response.json()
            self.assertEqual(payload["debug"]["sales_action_taken"], "ask_discovery")
            self.assertEqual(payload["debug"]["current_stage"], "discover")
            reply = payload["reply"]
            self.assertNotIn("Mình tìm thấy", reply)
            self.assertNotIn("[P1]", reply)
            self.assertNotIn("Bạn muốn đặt sản phẩm nào", reply)
            self.assertNotIn("https://", reply)
            self.assertNotIn("Bạn muốn đặt sản phẩm nào", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_multi_turn_tu_tivi_budget_leads_to_suggest(self):
        """Phase 7B: room -> category -> budget+color -> suggest, listing đúng loại."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            mock_kb = FakeRetriever([
                _hit("tu-tivi", "Kệ tivi gỗ sáng", "TU-001", 5000000,
                     "https://example.test/tu-tivi", category="Tủ"),
                _hit("ghe", "Ghế văn phòng", "GHE-001", 2300000,
                     "https://example.test/ghe", category="Ghế"),
                _hit("den", "Đèn thả trần", "DEN-001", 400000,
                     "https://example.test/den", category="Đèn"),
            ])
            server.KB = mock_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = mock_kb

            conv_id = "sales-tu-tivi-budget"
            self._turn(conv_id, "tôi muốn tìm đồ cho phòng khách",
                       sales_mode="active", mode="tenant_sales")
            self._turn(conv_id, "nhà tôi đang thiếu tủ để ti vi",
                       sales_mode="active", mode="tenant_sales")

            response = self._turn(conv_id, "ngân sách 5 triệu, màu gỗ sáng",
                                  sales_mode="active", mode="tenant_sales")
            payload = response.json()
            self.assertIn(payload["debug"]["sales_action_taken"], ("none", "suggest_from_kb"))
            reply = payload["reply"]
            self.assertIn("Kệ tivi", reply)
            self.assertNotIn("Ghế văn phòng", reply)
            self.assertNotIn("Đèn thả", reply)
            self.assertNotIn("Ghế", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_multi_turn_budget_uses_accumulated_category(self):
        """Phase 8: room -> category -> budget: listing must use accumulated state, not last message only."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            accum_kb = FakeRetriever([
                _hit("ghe-1", "Ghế phòng ngủ", "GHE-1", 2500000,
                     "https://example.test/ghe-1", category="Ghế"),
                _hit("tranh-1", "Tranh treo tường", "TR-1", 1500000,
                     "https://example.test/tranh-1", category="Tranh"),
            ])
            server.KB = accum_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = accum_kb

            conv_id = "sales-accum-state"
            self._turn(conv_id, "t muốn mua đồ cho phòng ngủ của t",
                       sales_mode="active", mode="tenant_sales")
            self._turn(conv_id, "ghế đi",
                       sales_mode="active", mode="tenant_sales")

            response = self._turn(conv_id, "dưới 3 triệu",
                                  sales_mode="active", mode="tenant_sales")
            payload = response.json()
            reply = payload["reply"]
            self.assertIn("Ghế", reply)
            self.assertNotIn("Tranh", reply)
            self.assertNotIn("TR-1", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_multi_turn_budget_no_match_does_not_fallback_wrong_category(self):
        """Phase 8: room->Ghế->budget, KB has wrong-category only -> no-result, not wrong listing."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            no_ghe_kb = FakeRetriever([
                _hit("tranh-1", "Tranh treo tường", "TR-1", 1500000,
                     "https://example.test/tranh-1", category="Tranh"),
                _hit("den-1", "Đèn bàn", "DEN-1", 500000,
                     "https://example.test/den-1", category="Đèn"),
            ])
            server.KB = no_ghe_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = no_ghe_kb

            conv_id = "sales-accum-nomatch"
            self._turn(conv_id, "t muốn mua đồ cho phòng ngủ của t",
                       sales_mode="active", mode="tenant_sales")
            self._turn(conv_id, "ghế đi",
                       sales_mode="active", mode="tenant_sales")

            response = self._turn(conv_id, "dưới 3 triệu",
                                  sales_mode="active", mode="tenant_sales")
            payload = response.json()
            reply = payload["reply"]
            self.assertNotIn("Tranh", reply)
            self.assertNotIn("Đèn", reply)
            self.assertNotIn("TR-1", reply)
            self.assertNotIn("DEN-1", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_tranh_consultation_full_flow_kb_match(self):
        """Phase 9C: tranh -> room+size -> budget => suggest Tranh listing, not contact/generic."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            tranh_kb = FakeRetriever([
                _hit("tranh-a", "Tranh treo tường phòng khách GHX-6101", "GHX-6101", 2100000,
                     "https://example.test/tranh-a", category="Tranh"),
            ])
            server.KB = tranh_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = tranh_kb

            conv_id = "sales-tranh-full"
            self._turn(conv_id, "t muốn mua 1 bức tranh",
                       sales_mode="active", mode="tenant_sales")
            self._turn(conv_id, "phòng khách đi, chắc khoảng 3m x 5m là to nhất rồi",
                       sales_mode="active", mode="tenant_sales")

            response = self._turn(conv_id, "5 triệu trở xuống",
                                  sales_mode="active", mode="tenant_sales")
            payload = response.json()
            reply = payload["reply"]
            # Must list Tranh, not generic/contact
            self.assertIn("Tranh", reply)
            self.assertNotIn("Bạn chia sẻ thêm", reply)
            self.assertNotIn("số điện thoại", reply.lower())
            self.assertNotIn("phòng đặt", reply)
            # No wrong category
            self.assertNotIn("Ghế", reply)
            self.assertNotIn("Đèn", reply)
            # Must have retrieval
            self.assertGreaterEqual(payload["debug"].get("retrieval_count", 0), 1)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_tranh_consultation_no_kb_match(self):
        """Phase 9C: Tranh consultation, KB no match => no-result for Tranh, not generic."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            no_tranh_kb = FakeRetriever([
                _hit("ghe-1", "Ghế rẻ", "GHE-1", 2000000,
                     "https://example.test/ghe-1", category="Ghế"),
                _hit("den-1", "Đèn bàn", "DEN-1", 500000,
                     "https://example.test/den-1", category="Đèn"),
            ])
            server.KB = no_tranh_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = no_tranh_kb

            conv_id = "sales-tranh-nomatch"
            self._turn(conv_id, "t muốn mua 1 bức tranh",
                       sales_mode="active", mode="tenant_sales")
            self._turn(conv_id, "phòng khách đi, chắc khoảng 3m x 5m là to nhất rồi",
                       sales_mode="active", mode="tenant_sales")

            response = self._turn(conv_id, "5 triệu trở xuống",
                                  sales_mode="active", mode="tenant_sales")
            payload = response.json()
            reply = payload["reply"]
            # Must be no-result, not wrong category listing, not generic
            self.assertNotIn("Ghế", reply)
            self.assertNotIn("Đèn", reply)
            self.assertNotIn("Bạn chia sẻ thêm", reply)
            self.assertNotIn("phòng đặt", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

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

    def test_similar_suggestion_filters_by_category_in_tenant_sales(self):
        """Similar suggestion with mixed-category KB: only Ghế in output.
        Must pass through server.py:1604, NOT template/LlM return."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            mixed_kb = FakeRetriever([
                _hit("ghe-a", "Ghế văn phòng A", "GHE-A", 2000000, "https://example.test/ghe-a", category="Ghế"),
                _hit("vach-ngan", "Vách ngăn trang trí GHO-595", "GHO-595", 2100000, "https://example.test/vach-ngan", category="Đồ trang trí"),
                _hit("den-tha", "Đèn thả trần GHO-256", "GHO-256", 400000, "https://example.test/den-tha", category="Đèn"),
            ])
            server.KB = mixed_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = mixed_kb

            conv_id = "sales-similar-filter"
            self._turn(conv_id, "ghe van phong duoi 3 trieu",
                       sales_mode="active", mode="tenant_sales")

            # llm mode bypasses template return so similar path at 1604 is reached
            response = self._turn(conv_id, "co mau ghe nao tuong tu khong?",
                                  sales_mode="active", mode="tenant_sales", answer_mode="llm")
            payload = response.json()
            reply = payload["reply"]
            # Similar path fires and returns its own template text before LLM is called.
            # The reply text is the similar suggestion template, NOT a stub LLM string.
            self.assertIn("gợi ý một vài sản phẩm tương tự", reply)
            self.assertIn("Ghế văn phòng", reply)
            self.assertNotIn("GHO-595", reply)
            self.assertNotIn("GHO-256", reply)
            self.assertNotIn("Vách ngăn", reply)
            self.assertNotIn("Đèn thả trần", reply)
            # Not template mode, not stub-generator text
            self.assertNotIn("[stub]", reply)
            # Not sales-template (ask_discovery/ask_contact/etc.)
            self.assertNotEqual(payload["model"], "sales-template")
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_similar_suggestion_no_result_when_no_matching_category(self):
        """Similar suggestion with only wrong-category hits: no-product fallback."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            wrong_kb = FakeRetriever([
                _hit("vach-ngan", "Vách ngăn trang trí GHO-595", "GHO-595", 2100000, "https://example.test/vach-ngan", category="Đồ trang trí"),
                _hit("den-tha", "Đèn thả trần GHO-256", "GHO-256", 400000, "https://example.test/den-tha", category="Đèn"),
            ])
            server.KB = wrong_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = wrong_kb

            conv_id = "sales-similar-no-match"
            self._turn(conv_id, "ghe van phong duoi 3 trieu",
                       sales_mode="active", mode="tenant_sales")

            response = self._turn(conv_id, "co mau tuong tu khong?",
                                  sales_mode="active", mode="tenant_sales", answer_mode="llm")
            payload = response.json()
            reply = payload["reply"]
            # Similar path fires with no items -> no-result fallback text
            self.assertIn("chưa tìm thấy sản phẩm cùng loại", reply)
            self.assertNotIn("GHO-595", reply)
            self.assertNotIn("GHO-256", reply)
            self.assertNotIn("Vách ngăn", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

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

    def test_main_listing_one_match_no_padding(self):
        """Template listing with 1 Ghế + nhiều product sai loại: chỉ 1 Ghế, không pad."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            mixed_kb = FakeRetriever([
                _hit("ghe-1", "Ghế làm việc Z", "GHE-1", 2500000, "https://example.test/ghe-1", category="Ghế"),
                _hit("vach-ngan", "Vách ngăn trang trí", "VN-1", 2100000, "https://example.test/vach-ngan", category="Đồ trang trí"),
                _hit("den-tha", "Đèn thả trần", "DEN-1", 400000, "https://example.test/den-tha", category="Đèn"),
            ])
            server.KB = mixed_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = mixed_kb

            conv_id = "sales-listing-one"
            # template mode -> render_product_answer -> render_listing_answer path
            response = self._turn(conv_id, "ghe van phong duoi 3 trieu",
                                  sales_mode="active", mode="tenant_sales", answer_mode="template")
            payload = response.json()
            reply = payload["reply"]
            self.assertIn("Ghế làm việc", reply)
            self.assertNotIn("Vách ngăn", reply)
            self.assertNotIn("Đèn thả", reply)
            self.assertNotIn("VN-1", reply)
            self.assertNotIn("DEN-1", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

    def test_main_listing_zero_match_no_suggest(self):
        """Template listing with 0 product đúng loại: no-result, không listing sai."""
        prev_kb = server.KB
        prev_by_mode = dict(server.KB_BY_MODE)
        try:
            mixed_kb = FakeRetriever([
                _hit("vach-ngan", "Vách ngăn trang trí", "VN-1", 2100000, "https://example.test/vach-ngan", category="Đồ trang trí"),
                _hit("den-tha", "Đèn thả trần", "DEN-1", 400000, "https://example.test/den-tha", category="Đèn"),
            ])
            server.KB = mixed_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE["keyword"] = mixed_kb

            conv_id = "sales-listing-zero"
            response = self._turn(conv_id, "ghe van phong duoi 3 trieu",
                                  sales_mode="active", mode="tenant_sales", answer_mode="template")
            payload = response.json()
            reply = payload["reply"]
            self.assertIn("Mình chưa tìm thấy", reply)
            self.assertNotIn("Vách ngăn", reply)
            self.assertNotIn("Đèn thả", reply)
            self.assertNotIn("VN-1", reply)
            self.assertNotIn("DEN-1", reply)
        finally:
            server.KB = prev_kb
            server.KB_BY_MODE.clear()
            server.KB_BY_MODE.update(prev_by_mode)

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
