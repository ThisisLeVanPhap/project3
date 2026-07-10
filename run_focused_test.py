"""
Run focused flow test and print readable result.
"""
import os
import sys
from unittest.mock import patch
from types import SimpleNamespace

os.environ['CHATBOT_TEST_MODE'] = '1'

sys.path.insert(0, 'chatbot')
from fastapi.testclient import TestClient
import app.server as server_module
from app.retrievers import RetrievalResult

print("=== Focused Flow Test ===")
print()
print("Input flow:")
print("1. t muốn mua 1 cái đèn")
print("2. phòng khách")
print("3. từ 15 triệu trở xuống")
print()

prev_kb = server_module.KB
prev_by_mode = dict(server_module.KB_BY_MODE)

try:
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
        with patch("app.server._is_pytest_blocking_real_claude", return_value=False):
            with patch("app.server.call_state_interpreter", side_effect=mock_interpreter):
                with patch("app.server._sales_action_from_state", side_effect=action_side):
                    with patch("app.server._call_claude_api", side_effect=mock_claude_listing):
                        client = TestClient(server_module.app)
                        conv = "flow-den-pk-15tr"

                        r1 = client.post("/chat", json={
                            "message": "t muốn mua 1 cái đèn",
                            "history": [], "conversation_id": conv, "tenant_id": "t", "channel": "web",
                            "gen": {"provider": "stub", "mode": "tenant_sales", "retrieval_mode": "keyword", "retrieval_top_k": 4, "answer_mode": "template", "sales_mode": "active"},
                        })

                        r2 = client.post("/chat", json={
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

                        print("Final answer:")
                        print(reply)
                        print()
                        print("Debug:")
                        print(f"real_claude_response_attempted={dbg.get('real_claude_response_attempted')}")
                        print(f"real_claude_response_called={dbg.get('real_claude_response_called')}")
                        print(f"real_claude_response_mode={dbg.get('real_claude_response_mode')}")
                        print(f"real_claude_skip_reason={dbg.get('real_claude_skip_reason')}")
                        print(f"real_claude_error_type={dbg.get('real_claude_error_type')}")
                        print()
                        print(f"Claude mock call count: {claude_calls[0]}")

                        raw1 = "Mình tìm thấy một số sản phẩm phù hợp trong dữ liệu hiện có"
                        raw2 = "Phù hợp vì: khớp với nhóm Đèn"
                        raw3 = "Thuộc tính chính:"
                        raw_present = (raw1 in reply) or (raw2 in reply) or (raw3 in reply)
                        print(f"Raw renderer phrase present: {raw_present}")
                        print(f"Non-matching product present: {'TRANH-001' in reply}")
finally:
    server_module.KB = prev_kb
    server_module.KB_BY_MODE.clear()
    server_module.KB_BY_MODE.update(prev_by_mode)
