"""
Phase 11C: Staged mock tests for state interpreter and consultation LLM.

CRITICAL: All tests MUST monkeypatch/fake LLM and NEVER call real Claude API.
"""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["CHATBOT_TEST_MODE"] = "1"

from app.sales_state import SalesConversationState
from app.sales_slots import extract_sales_slots


class StateInterpreterStagedTests(unittest.TestCase):
    """Phase 11C: Tests for interpreter invoked before action selection."""

    def test_state_interpreter_invoked_before_action_selection(self):
        """Interpreter must be called before action selection.
        Budget-only turn must keep accumulated category."""
        from fastapi.testclient import TestClient
        import app.server as server_module

        # Override KB with Den products
        prev_kb = server_module.KB
        prev_by_mode = dict(server_module.KB_BY_MODE)
        try:
            from app.retrievers import RetrievalResult

            def _hit(doc_id, product_name, sku, price, url, category="Đèn"):
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

            den_kb = _hit("den-ok", "Đèn trần đẹp", "DEN-OK", 3500000, "https://example.test/den-ok", category="Đèn")
            server_module.KB = SimpleNamespace(search=lambda q, k=4: [den_kb])
            server_module.KB_BY_MODE.clear()
            server_module.KB_BY_MODE["keyword"] = server_module.KB

            # Monkeypatch call_state_interpreter
            mock_interpreter_result = {
                "intent": "consultation",
                "slot_updates": {"product_category": "Đèn"},
                "slots_to_keep": [],
                "slots_to_clear": [],
                "missing_slots": ["room_or_space"],
                "should_retrieve": False,
                "should_ask": True,
                "response_mode": "consultation_llm",
                "confidence": 0.95,
            }

            with patch('app.server.call_state_interpreter', return_value=mock_interpreter_result):
                client = TestClient(server_module.app)
                conv_id = "test-interpreter-before-action"
                # Force interpreter enabled via test mode + sales active
                r = client.post("/chat", json={
                    "message": "t muốn mua 1 cái đèn",
                    "history": [],
                    "conversation_id": conv_id,
                    "tenant_id": "tenant-a",
                    "channel": "web",
                    "gen": {
                        "provider": "stub",
                        "mode": "tenant_sales",
                        "retrieval_mode": "keyword",
                        "retrieval_top_k": 4,
                        "answer_mode": "template",
                        "sales_mode": "active",
                    },
                })

                self.assertEqual(r.status_code, 200)
                p = r.json()
                debug = p.get("debug", {})

                # Phase 11C: exact field names
                self.assertTrue(debug.get("state_interpreter_llm_attempted"), "interpreter should be attempted")
                self.assertTrue(debug.get("state_interpreter_llm_called"), "interpreter should be called")
                self.assertEqual(debug.get("state_interpreter_intent"), "consultation")
                slots_after = debug.get("slots_snapshot_after_interpreter", {})
                self.assertEqual(slots_after.get("product_category"), "Đèn")

                # Must not ask generic category question
                reply = p.get("reply", "")
                self.assertNotIn("sofa, bàn, giường, tủ", reply.lower())
        finally:
            server_module.KB = prev_kb
            server_module.KB_BY_MODE.clear()
            server_module.KB_BY_MODE.update(prev_by_mode)

    def test_consultation_llm_called_for_category_only(self):
        """Consultation LLM must be called for category-only turn.
        Must not use old template phrase."""
        from fastapi.testclient import TestClient
        import app.server as server_module

        prev_kb = server_module.KB
        prev_by_mode = dict(server_module.KB_BY_MODE)
        try:
            mock_consult_text = "Đèn có thể chọn theo vị trí dùng: đèn thả tạo điểm nhấn, đèn ốp trần gọn hơn. Bạn định dùng cho phòng khách hay phòng ngủ?"

            # Monkeypatch interpreter + consultation
            mock_interpreter_result = {
                "intent": "consultation",
                "slot_updates": {"product_category": "Đèn"},
                "slots_to_keep": [],
                "slots_to_clear": [],
                "missing_slots": ["room_or_space"],
                "should_retrieve": False,
                "should_ask": True,
                "response_mode": "consultation_llm",
                "confidence": 0.95,
            }

            with patch('app.server.call_state_interpreter', return_value=mock_interpreter_result):
                with patch('app.server._call_consultation_llm', return_value=mock_consult_text):
                    client = TestClient(server_module.app)
                    conv_id = "test-consultation-llm"
                    r = client.post("/chat", json={
                        "message": "t muốn mua 1 cái đèn",
                        "history": [],
                        "conversation_id": conv_id,
                        "tenant_id": "tenant-a",
                        "channel": "web",
                        "gen": {
                            "provider": "stub",
                            "mode": "tenant_sales",
                            "retrieval_mode": "keyword",
                            "retrieval_top_k": 4,
                            "answer_mode": "template",
                            "sales_mode": "active",
                        },
                    })

                    self.assertEqual(r.status_code, 200)
                    p = r.json()
                    debug = p.get("debug", {})

                    self.assertIn(mock_consult_text, p.get("reply", ""))
                    self.assertTrue(debug.get("consultation_llm_attempted"))
                    self.assertTrue(debug.get("consultation_llm_called"))
                    self.assertNotIn("Bạn định đặt sản phẩm ở phòng nào", p.get("reply", ""))
        finally:
            server_module.KB = prev_kb
            server_module.KB_BY_MODE.clear()
            server_module.KB_BY_MODE.update(prev_by_mode)

    def test_budget_only_keeps_category_and_lists_den(self):
        """Budget-only turn must keep accumulated category and list correct product."""
        from fastapi.testclient import TestClient
        import app.server as server_module
        from app.retrievers import RetrievalResult

        prev_kb = server_module.KB
        prev_by_mode = dict(server_module.KB_BY_MODE)
        try:
            def _hit(doc_id, product_name, sku, price, url, category):
                return RetrievalResult(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}#0",
                    title=product_name,
                    text=f"{product_name}",
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

            den_ok = _hit("den-ok", "Đèn trần đẹp", "DEN-OK", 3500000, "https://example.test/den-ok", "Đèn")
            tranh = _hit("tranh-001", "Tranh treo tường", "TRANH-001", 2100000, "https://example.test/tranh", "Tranh")
            mixed_kb = SimpleNamespace(search=lambda q, k=10: [den_ok, tranh])
            server_module.KB = mixed_kb
            server_module.KB_BY_MODE.clear()
            server_module.KB_BY_MODE["keyword"] = mixed_kb

            conv_id = "test-budget-keeps-cat"

            # Turn 1: category only -> interpreter says should_ask
            mock_int1 = {
                "intent": "consultation",
                "slot_updates": {"product_category": "Đèn"},
                "slots_to_keep": [],
                "slots_to_clear": [],
                "missing_slots": ["room_or_space"],
                "should_retrieve": False,
                "should_ask": True,
                "response_mode": "consultation_llm",
                "confidence": 0.95,
            }

            with patch('app.server.call_state_interpreter', return_value=mock_int1):
                with patch('app.server._call_consultation_llm', return_value="Bạn cần đèn cho không gian nào?"):
                    client = TestClient(server_module.app)
                    r1 = client.post("/chat", json={
                        "message": "t muốn mua 1 cái đèn",
                        "history": [],
                        "conversation_id": conv_id,
                        "tenant_id": "tenant-a",
                        "channel": "web",
                        "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                    })
                    self.assertEqual(r1.status_code, 200)

            # Turn 2: budget only -> interpreter says should_retrieve
            mock_int2 = {
                "intent": "add_constraint",
                "slot_updates": {},
                "slots_to_keep": ["product_category"],
                "slots_to_clear": [],
                "missing_slots": [],
                "should_retrieve": True,
                "should_ask": False,
                "response_mode": "product_listing",
                "confidence": 0.95,
            }

            with patch('app.server.call_state_interpreter', return_value=mock_int2):
                r2 = client.post("/chat", json={
                    "message": "10 triệu trở xuống",
                    "history": [],
                    "conversation_id": conv_id,
                    "tenant_id": "tenant-a",
                    "channel": "web",
                    "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                })

                p2 = r2.json()
                reply2 = p2.get("reply", "")
                debug2 = p2.get("debug", {})

                # Must have requested Den category
                self.assertIn("Đèn", str(debug2.get("requested_category", "")) or reply2)
                # Must contain DEN-OK, not TRANH
                self.assertIn("DEN-OK", reply2)
                self.assertNotIn("TRANH-001", reply2)
                # Must not ask generic category
                self.assertNotIn("sofa, bàn, giường, tủ", reply2.lower())
                self.assertGreater(debug2.get("retrieval_count", 0), 0)
        finally:
            server_module.KB = prev_kb
            server_module.KB_BY_MODE.clear()
            server_module.KB_BY_MODE.update(prev_by_mode)

    def test_style_update_keeps_other_slots(self):
        """Style update must keep unrelated slots, clear last_recommended."""
        from fastapi.testclient import TestClient
        import app.server as server_module

        prev_kb = server_module.KB
        try:
            state = SalesConversationState(tenant_id="t", conversation_id="c")
            state.slots["product_category"] = "Ghế"
            state.slots["room"] = "phòng khách"
            state.slots["room_size"] = "18m2"
            state.slots["budget_max"] = 5000000
            state.slots["style"] = "cổ điển"
            state.last_recommended_products = [{"sku": "G1"}]
            server_module.SALES_STATE_STORE[("t", "c")] = state

            mock_int = {
                "intent": "update_slot",
                "slot_updates": {"style": "modern"},
                "slots_to_keep": ["product_category", "room", "room_size", "budget_max"],
                "slots_to_clear": ["last_recommended_products"],
                "should_retrieve": True,
                "confidence": 0.95,
            }

            with patch('app.server.call_state_interpreter', return_value=mock_int):
                client = TestClient(server_module.app)
                r = client.post("/chat", json={
                    "message": "thôi hiện đại đi",
                    "history": [],
                    "conversation_id": "c",
                    "tenant_id": "t",
                    "channel": "web",
                    "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                })

                p = r.json()
                debug = p.get("debug", {})
                self.assertTrue(debug.get("state_interpreter_llm_called"))

                # Verify state kept values
                final_state = server_module.SALES_STATE_STORE.get(("t", "c"))
                self.assertEqual(final_state.slots.get("product_category"), "Ghế")
                self.assertEqual(final_state.slots.get("room"), "phòng khách")
                self.assertEqual(final_state.slots.get("room_size"), "18m2")
                self.assertEqual(final_state.slots.get("budget_max"), 5000000)
                self.assertEqual(final_state.slots.get("style"), "modern")
                self.assertEqual(len(final_state.last_recommended_products), 0)
        finally:
            server_module.KB = prev_kb
            server_module.SALES_STATE_STORE.clear()

    def test_category_replace_clears_recommendations(self):
        """Replace_need must clear selected and recommended products."""
        from fastapi.testclient import TestClient
        import app.server as server_module

        prev_kb = server_module.KB
        try:
            state = SalesConversationState(tenant_id="t", conversation_id="c2")
            state.slots["product_category"] = "Ghế"
            state.selected_products = [{"sku": "G1"}]
            state.last_recommended_products = [{"sku": "G1"}]
            state.slots["room"] = "phòng khách"
            state.slots["budget_max"] = 5000000
            server_module.SALES_STATE_STORE[("t", "c2")] = state

            mock_int = {
                "intent": "replace_need",
                "slot_updates": {"product_category": "Tranh"},
                "slots_to_keep": ["room", "budget_max"],
                "slots_to_clear": [],
                "should_retrieve": True,
                "confidence": 0.95,
            }

            with patch('app.server.call_state_interpreter', return_value=mock_int):
                client = TestClient(server_module.app)
                r = client.post("/chat", json={
                    "message": "đổi sang tranh treo tường đi",
                    "history": [],
                    "conversation_id": "c2",
                    "tenant_id": "t",
                    "channel": "web",
                    "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                })

                final_state = server_module.SALES_STATE_STORE.get(("t", "c2"))
                self.assertEqual(final_state.slots.get("product_category"), "Tranh")
                self.assertEqual(len(final_state.selected_products), 0)
                self.assertEqual(len(final_state.last_recommended_products), 0)
                self.assertEqual(final_state.slots.get("room"), "phòng khách")
        finally:
            server_module.KB = prev_kb
            server_module.SALES_STATE_STORE.clear()

    def test_interpreter_error_fallback_debug(self):
        """Interpreter error must set attempted=true, called=false, error_type."""
        from fastapi.testclient import TestClient
        import app.server as server_module

        with patch('app.server.call_state_interpreter', side_effect=RuntimeError("boom")):
            client = TestClient(server_module.app)
            r = client.post("/chat", json={
                "message": "t muốn mua 1 cái đèn",
                "history": [],
                "conversation_id": "err-int",
                "tenant_id": "t",
                "channel": "web",
                "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
            })

            p = r.json()
            debug = p.get("debug", {})
            self.assertTrue(debug.get("state_interpreter_llm_attempted"))
            self.assertFalse(debug.get("state_interpreter_llm_called", True))
            self.assertEqual(debug.get("state_interpreter_error_type"), "RuntimeError")
            self.assertIn("fallback", debug.get("state_interpreter_skip_reason", "").lower() or "error")

    def test_consultation_error_fallback_debug(self):
        """Consultation LLM error must set attempted=true, called=false, error_type."""
        from fastapi.testclient import TestClient
        import app.server as server_module

        mock_int = {
            "intent": "consultation",
            "slot_updates": {"product_category": "Đèn"},
            "slots_to_keep": [],
            "slots_to_clear": [],
            "missing_slots": ["room_or_space"],
            "should_retrieve": False,
            "should_ask": True,
            "response_mode": "consultation_llm",
            "confidence": 0.95,
        }

        with patch('app.sales_state_interpreter.call_state_interpreter', return_value=mock_int):
            with patch('app.server._call_consultation_llm', side_effect=RuntimeError("boom")):
                client = TestClient(server_module.app)
                r = client.post("/chat", json={
                    "message": "t muốn mua 1 cái đèn",
                    "history": [],
                    "conversation_id": "err-consult",
                    "tenant_id": "t",
                    "channel": "web",
                    "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                })

                p = r.json()
                debug = p.get("debug", {})
                self.assertTrue(debug.get("consultation_llm_attempted"))
                self.assertFalse(debug.get("consultation_llm_called", True))
                self.assertEqual(debug.get("consultation_llm_error_type"), "RuntimeError")
                self.assertEqual(debug.get("consultation_llm_skip_reason"), "fallback_after_error")

    def test_llm_slot_updates_do_not_leak_unsafe_fields(self):
        """Raw LLM slot_updates with unsafe fields must not leak into final state/slots."""
        from fastapi.testclient import TestClient
        import app.server as server_module

        # Mock interpreter returns unsafe fields
        mock_int = {
            "intent": "consultation",
            "slot_updates": {
                "product_category": "Đèn",
                "budget_max": 1,
                "sku": "FAKE-SKU",
                "phone": "0999999999",
                "selected_product": {"sku": "FAKE"},
                "purchase_request_status": "confirmed",
            },
            "slots_to_keep": [],
            "slots_to_clear": [],
            "should_retrieve": False,
            "should_ask": True,
            "response_mode": "consultation_llm",
            "confidence": 0.95,
        }

        with patch('app.server.call_state_interpreter', return_value=mock_int):
            client = TestClient(server_module.app)
            r = client.post("/chat", json={
                "message": "10 triệu trở xuống",
                "history": [],
                "conversation_id": "leak-test",
                "tenant_id": "t",
                "channel": "web",
                "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
            })

            p = r.json()
            debug = p.get("debug", {})
            slots = debug.get("known_slots", {}) or debug.get("slots_snapshot", {})

            # Unsafe fields from LLM must not be in final state
            self.assertNotIn("FAKE-SKU", str(slots))
            self.assertNotIn("0999999999", str(slots))
            self.assertNotIn("FAKE", str(slots))

            # Deterministic budget should win (from "10 triệu trở xuống")
            reply = p.get("reply", "")
            # No handoff/purchase triggered from unsafe LLM fields
            self.assertNotEqual(debug.get("sales_action_taken"), "handoff")
            self.assertNotEqual(debug.get("sales_action_taken"), "ask_confirmation")

    def test_tenant_sales_den_phong_khach_budget_uses_claude_listing_rewrite(self):
        """End-to-end: 3-turn flow uses mocked Claude to rewrite product listing, not raw renderer."""
        from fastapi.testclient import TestClient
        import app.server as server_module
        import os

        prev_kb = server_module.KB
        prev_by_mode = dict(server_module.KB_BY_MODE)
        try:
            from app.retrievers import RetrievalResult

            def _hit(sku, name, price, category="Đèn"):
                return RetrievalResult(
                    doc_id=sku.lower().replace("-", ""),
                    chunk_id=f"{sku.lower().replace('-','')}#0",
                    title=name,
                    text=f"{name} là sản phẩm nội thất.",
                    source=f"https://example.test/{sku.lower()}",
                    score=10.0,
                    metadata={
                        "doc_type": "product",
                        "product_name": name,
                        "category": category,
                        "price": price,
                        "currency": "VND",
                        "sku": sku,
                        "source_url": f"https://example.test/{sku.lower()}",
                    },
                )

            gho262 = _hit("GHO-262", "Đèn chùm GHO-262", 2_800_000)
            gho237 = _hit("GHO-237", "Đèn treo tường GHO-237", 400_000)
            tranh = _hit("TRANH-001", "Tranh canvas", 500_000, category="Tranh")

            def search_fn(q, k=4, tenant_id=None):
                return [gho262, gho237, tranh]

            server_module.KB = SimpleNamespace(search=search_fn)
            server_module.KB_BY_MODE.clear()
            server_module.KB_BY_MODE["keyword"] = server_module.KB

            # Interpreter sequence for 3 turns
            mock_intents = [
                {"intent": "consultation", "slot_updates": {"product_category": "Đèn"}, "slots_to_keep": [], "slots_to_clear": [], "missing_slots": ["room"], "should_retrieve": False, "should_ask": True, "response_mode": "consultation_llm", "confidence": 0.9},
                {"intent": "update_slot", "slot_updates": {"room": "phòng khách"}, "slots_to_keep": [], "slots_to_clear": [], "missing_slots": ["budget"], "should_retrieve": False, "should_ask": True, "response_mode": "consultation_llm", "confidence": 0.9},
                {"intent": "add_constraint", "slot_updates": {"budget": "từ 15 triệu trở xuống"}, "slots_to_keep": [], "slots_to_clear": [], "missing_slots": [], "should_retrieve": True, "should_ask": False, "response_mode": "product_listing", "confidence": 0.9},
            ]
            intent_idx = [0]

            def mock_interpreter(*a, **k):
                i = intent_idx[0]
                intent_idx[0] += 1
                return mock_intents[min(i, len(mock_intents) - 1)]

            claude_calls = [0]

            def mock_claude_listing(*args, **kwargs):
                claude_calls[0] += 1
                return (
                    "Mình lọc được vài mẫu đèn phù hợp cho phòng khách dưới 15 triệu. GHO-262 hợp nếu bạn muốn tạo điểm nhấn trung tâm, còn GHO-237 gọn hơn cho trang trí phụ. Bạn muốn ưu tiên đèn chùm hay đèn treo tường?",
                    None,
                    None,
                )

            action_idx = [0]

            def action_side(*a, **k):
                action_idx[0] += 1
                return "ask_discovery" if action_idx[0] <= 2 else "none"

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-for-test"}):
                with patch('app.server._is_pytest_blocking_real_claude', return_value=False):
                    with patch('app.server.call_state_interpreter', side_effect=mock_interpreter):
                        with patch('app.server._sales_action_from_state', side_effect=action_side):
                            with patch('app.server._call_claude_api', side_effect=mock_claude_listing):
                                client = TestClient(server_module.app)
                                conv = "flow-den-pk-15tr"

                                r1 = client.post("/chat", json={
                                    "message": "t muốn mua 1 cái đèn",
                                    "history": [], "conversation_id": conv, "tenant_id": "t", "channel": "web",
                                    "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                                })
                                self.assertEqual(r1.status_code, 200)

                                r2 = client.post("/chat", json={
                                    "message": "phòng khách",
                                    "history": [], "conversation_id": conv, "tenant_id": "t", "channel": "web",
                                    "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                                })
                                self.assertEqual(r2.status_code, 200)

                                # Reset counter before final listing turn to prove exactly 1 call for listing
                                claude_calls[0] = 0

                                r3 = client.post("/chat", json={
                                    "message": "từ 15 triệu trở xuống",
                                    "history": [], "conversation_id": conv, "tenant_id": "t", "channel": "web",
                                    "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                                })
                                self.assertEqual(r3.status_code, 200)

                                p = r3.json()
                                reply = p.get("reply", "")
                                dbg = p.get("debug", {})

                                self.assertIn("Mình lọc được vài mẫu đèn phù hợp cho phòng khách dưới 15 triệu", reply)
                                self.assertNotIn("Mình tìm thấy một số sản phẩm phù hợp trong dữ liệu hiện có", reply)
                                self.assertNotIn("Phù hợp vì: khớp với nhóm Đèn", reply)
                                self.assertNotIn("Thuộc tính chính:", reply)
                                self.assertTrue("GHO-262" in reply or "GHO-237" in reply)
                                self.assertNotIn("TRANH-001", reply)
                                self.assertTrue(dbg.get("real_claude_response_attempted"))
                                self.assertTrue(dbg.get("real_claude_response_called"))
                                self.assertEqual(dbg.get("real_claude_response_mode"), "product_listing")
                                self.assertIsNone(dbg.get("real_claude_error_type"))
                                self.assertEqual(claude_calls[0], 1)
        finally:
            server_module.KB = prev_kb
            server_module.KB_BY_MODE.clear()
            server_module.KB_BY_MODE.update(prev_by_mode)


def test_tenant_sales_den_phong_khach_budget_uses_claude_listing_rewrite():
    """Module-level pytest wrapper so exact command works:
    PYTHONPATH=chatbot python -m pytest chatbot/tests/test_sales_state_interpreter.py::test_tenant_sales_den_phong_khach_budget_uses_claude_listing_rewrite -q -s
    """
    from unittest.mock import patch
    from types import SimpleNamespace
    import os
    from fastapi.testclient import TestClient
    import app.server as server_module

    prev_kb = server_module.KB
    prev_by_mode = dict(server_module.KB_BY_MODE)
    try:
        from app.retrievers import RetrievalResult

        def _hit(sku, name, price, category="Đèn"):
            return RetrievalResult(
                doc_id=sku.lower().replace("-", ""),
                chunk_id=f"{sku.lower().replace('-','')}#0",
                title=name,
                text=f"{name} là sản phẩm nội thất.",
                source=f"https://example.test/{sku.lower()}",
                score=10.0,
                metadata={
                    "doc_type": "product",
                    "product_name": name,
                    "category": category,
                    "price": price,
                    "currency": "VND",
                    "sku": sku,
                    "source_url": f"https://example.test/{sku.lower()}",
                },
            )

        gho262 = _hit("GHO-262", "Đèn chùm GHO-262", 2_800_000)
        gho237 = _hit("GHO-237", "Đèn treo tường GHO-237", 400_000)
        tranh = _hit("TRANH-001", "Tranh canvas", 500_000, category="Tranh")

        def search_fn(q, k=4, tenant_id=None):
            return [gho262, gho237, tranh]

        server_module.KB = SimpleNamespace(search=search_fn)
        server_module.KB_BY_MODE.clear()
        server_module.KB_BY_MODE["keyword"] = server_module.KB

        mock_intents = [
            {"intent": "consultation", "slot_updates": {"product_category": "Đèn"}, "slots_to_keep": [], "slots_to_clear": [], "missing_slots": ["room"], "should_retrieve": False, "should_ask": True, "response_mode": "consultation_llm", "confidence": 0.9},
            {"intent": "update_slot", "slot_updates": {"room": "phòng khách"}, "slots_to_keep": [], "slots_to_clear": [], "missing_slots": ["budget"], "should_retrieve": False, "should_ask": True, "response_mode": "consultation_llm", "confidence": 0.9},
            {"intent": "add_constraint", "slot_updates": {"budget": "từ 15 triệu trở xuống"}, "slots_to_keep": [], "slots_to_clear": [], "missing_slots": [], "should_retrieve": True, "should_ask": False, "response_mode": "product_listing", "confidence": 0.9},
        ]
        intent_idx = [0]

        def mock_interpreter(*a, **k):
            i = intent_idx[0]
            intent_idx[0] += 1
            return mock_intents[min(i, len(mock_intents) - 1)]

        claude_calls = [0]

        def mock_claude_listing(*args, **kwargs):
            claude_calls[0] += 1
            return (
                "Mình lọc được vài mẫu đèn phù hợp cho phòng khách dưới 15 triệu. GHO-262 hợp nếu bạn muốn tạo điểm nhấn trung tâm, còn GHO-237 gọn hơn cho trang trí phụ. Bạn muốn ưu tiên đèn chùm hay đèn treo tường?",
                None,
                None,
            )

        action_idx = [0]

        def action_side(*a, **k):
            action_idx[0] += 1
            return "ask_discovery" if action_idx[0] <= 2 else "none"

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-for-test"}):
            with patch('app.server._is_pytest_blocking_real_claude', return_value=False):
                with patch('app.server.call_state_interpreter', side_effect=mock_interpreter):
                    with patch('app.server._sales_action_from_state', side_effect=action_side):
                        with patch('app.server._call_claude_api', side_effect=mock_claude_listing):
                            client = TestClient(server_module.app)
                            conv = "flow-den-pk-15tr"

                            client.post("/chat", json={
                                "message": "t muốn mua 1 cái đèn",
                                "history": [], "conversation_id": conv, "tenant_id": "t", "channel": "web",
                                "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                            })
                            client.post("/chat", json={
                                "message": "phòng khách",
                                "history": [], "conversation_id": conv, "tenant_id": "t", "channel": "web",
                                "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                            })
                            claude_calls[0] = 0

                            r3 = client.post("/chat", json={
                                "message": "từ 15 triệu trở xuống",
                                "history": [], "conversation_id": conv, "tenant_id": "t", "channel": "web",
                                "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                            })
                            p = r3.json()
                            reply = p.get("reply", "")
                            dbg = p.get("debug", {})

                            assert "Mình lọc được vài mẫu đèn phù hợp cho phòng khách dưới 15 triệu" in reply
                            assert "Mình tìm thấy một số sản phẩm phù hợp trong dữ liệu hiện có" not in reply
                            assert "Phù hợp vì: khớp với nhóm Đèn" not in reply
                            assert "Thuộc tính chính:" not in reply
                            assert "GHO-262" in reply or "GHO-237" in reply
                            assert "TRANH-001" not in reply
                            assert dbg.get("real_claude_response_attempted")
                            assert dbg.get("real_claude_response_called")
                            assert dbg.get("real_claude_response_mode") == "product_listing"
                            assert dbg.get("real_claude_error_type") is None
                            assert claude_calls[0] == 1
    finally:
        server_module.KB = prev_kb
        server_module.KB_BY_MODE.clear()
        server_module.KB_BY_MODE.update(prev_by_mode)


if __name__ == "__main__":
    unittest.main()
