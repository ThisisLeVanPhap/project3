import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.conversation_orchestrator import ConversationOrchestrator, OrchestratorContext, OrchestratorRequest
from app.llm_client import ClaudeLLMClient, FakeLLMClient
from app.sales_slots import fold_text


GEN = {
    "provider": "stub",
    "mode": "tenant_sales",
    "retrieval_mode": "keyword",
    "retrieval_top_k": 4,
    "answer_mode": "template",
    "sales_mode": "active",
}


def _post(client, message, conv="orch-test"):
    return client.post("/chat", json={
        "message": message,
        "history": [],
        "conversation_id": conv,
        "tenant_id": "t",
        "channel": "web",
        "gen": GEN,
    })


def test_planner_blocks_real_claude_in_pytest_even_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-that-must-not-be-used")
    monkeypatch.delenv("RUN_REAL_CLAUDE_TESTS", raising=False)
    client = ClaudeLLMClient()

    with patch("app.llm_client.call_claude_api", side_effect=AssertionError("must not call API")) as mocked:
        with pytest.raises(RuntimeError, match="pytest_real_claude_disabled"):
            client.complete(
                prompt="hello",
                mode="tenant_sales",
                purpose="planner",
                max_tokens=20,
                temperature=0,
            )
    assert mocked.call_count == 0


def test_new_home_consult_does_not_infer_lamp(monkeypatch):
    monkeypatch.setenv("CONVERSATION_ORCHESTRATOR_ENABLED", "1")
    monkeypatch.setenv("SALES_USE_LLM_STATE_INTERPRETER", "0")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)

    import app.server as server_module

    prev_kb = server_module.KB
    prev_by_mode = dict(server_module.KB_BY_MODE)
    prev_store = dict(server_module.SALES_STATE_STORE)
    try:
        server_module.KB = None
        server_module.KB_BY_MODE.clear()
        server_module.SALES_STATE_STORE.clear()
        client = TestClient(server_module.app)
        r = _post(client, "t đang nghĩ đến việc mua nội thất cho nhà t, nhà t mới mua luôn", "orch-new-home")
        assert r.status_code == 200
        payload = r.json()
        debug = payload.get("debug", {})
        reply_folded = fold_text(payload.get("reply", ""))

        assert debug.get("orchestrator_enabled") is True
        assert debug.get("planner_intent") == "consult"
        assert debug.get("planner_need_retrieval") is False
        assert (debug.get("planner_decision", {}).get("filters") or {}).get("product_category") != "Đèn"
        assert "voi den" not in reply_folded
        assert "nha moi" in reply_folded
    finally:
        server_module.KB = prev_kb
        server_module.KB_BY_MODE.clear()
        server_module.KB_BY_MODE.update(prev_by_mode)
        server_module.SALES_STATE_STORE.clear()
        server_module.SALES_STATE_STORE.update(prev_store)


def test_living_room_empty_consult_is_not_category_form(monkeypatch):
    monkeypatch.setenv("CONVERSATION_ORCHESTRATOR_ENABLED", "1")
    monkeypatch.setenv("SALES_USE_LLM_STATE_INTERPRETER", "0")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)

    import app.server as server_module

    prev_kb = server_module.KB
    prev_by_mode = dict(server_module.KB_BY_MODE)
    prev_store = dict(server_module.SALES_STATE_STORE)
    try:
        server_module.KB = None
        server_module.KB_BY_MODE.clear()
        server_module.SALES_STATE_STORE.clear()
        client = TestClient(server_module.app)
        r = _post(
            client,
            "t muốn mua đồ đặt trong phòng khách của t tại nó đang khá trống, có cái bàn hay bộ ghế nào hay không",
            "orch-living-room",
        )
        assert r.status_code == 200
        reply = r.json().get("reply", "")
        folded = fold_text(reply)

        assert "phong khach" in folded
        assert "cho ngoi" in folded
        assert "ban" in folded
        assert "ke" in folded or "den" in folded or "trang tri" in folded
        assert reply.count("?") <= 1
        assert "sofa, ban, giuong, tu hay mon khac" not in folded
    finally:
        server_module.KB = prev_kb
        server_module.KB_BY_MODE.clear()
        server_module.KB_BY_MODE.update(prev_by_mode)
        server_module.SALES_STATE_STORE.clear()
        server_module.SALES_STATE_STORE.update(prev_store)


def test_followup_style_uses_memory():
    planner_1 = json.dumps({
        "mode": "tenant_sales",
        "intent": "consult",
        "need_retrieval": False,
        "search_query": "",
        "filters": {},
        "memory_delta": {"room": "phòng khách", "home_context": "nhà mới"},
        "response_goal": "tư vấn setup phòng khách",
        "ask_user": "",
        "safety_notes": [],
    }, ensure_ascii=False)
    planner_2 = json.dumps({
        "mode": "tenant_sales",
        "intent": "consult",
        "need_retrieval": False,
        "search_query": "",
        "filters": {},
        "memory_delta": {"who_for": "người lớn tuổi"},
        "response_goal": "tư vấn an toàn",
        "ask_user": "",
        "safety_notes": [],
    }, ensure_ascii=False)
    planner_3 = json.dumps({
        "mode": "tenant_sales",
        "intent": "consult",
        "need_retrieval": False,
        "search_query": "",
        "filters": {},
        "memory_delta": {"has_children": True},
        "response_goal": "tư vấn cho người già và trẻ con",
        "ask_user": "",
        "safety_notes": [],
    }, ensure_ascii=False)
    final = (
        "Với phòng khách có người lớn tuổi và trẻ con, nên chọn đồ chắc chắn, bo góc, bề mặt dễ vệ sinh và ít chi tiết sắc cạnh. "
        "Ghế nên có tựa vững, đệm vừa phải để đứng lên ngồi xuống dễ hơn, còn bàn/kệ nên thấp vừa tầm và neo chắc. "
        "Bạn muốn mình ưu tiên ghế, bàn hay kệ trước?"
    )
    fake = FakeLLMClient([
        planner_1,
        "Phòng khách nhà mới nên ưu tiên chỗ ngồi, bàn/kệ và ánh sáng trước. Bạn muốn đi từ sofa/bộ ghế hay bàn/kệ trước?",
        planner_2,
        "Với người lớn tuổi, nên ưu tiên ghế có tựa chắc, chất liệu dễ lau và lối đi thoáng. Bạn muốn ưu tiên ghế hay bàn/kệ trước?",
        planner_3,
        final,
    ])
    orch = ConversationOrchestrator(fake)
    memory = {}

    r1 = orch.run(OrchestratorRequest(message="nhà mới / phòng khách", mode="tenant_sales"), OrchestratorContext(memory=memory))
    memory = r1.updated_memory
    r2 = orch.run(OrchestratorRequest(message="nhà t có người già thì nên dùng cái gì", mode="tenant_sales"), OrchestratorContext(memory=memory))
    memory = r2.updated_memory
    r3 = orch.run(OrchestratorRequest(message="cơ mà có cả trẻ con nữa", mode="tenant_sales"), OrchestratorContext(memory=memory))

    folded = fold_text(r3.reply)
    assert r3.updated_memory.get("room") in {"phòng khách", "phong khach"}
    assert r3.updated_memory.get("who_for") in {"người lớn tuổi", "nguoi lon tuoi"}
    assert r3.updated_memory.get("has_children") is True
    assert "de ve sinh" in folded
    assert "bo goc" in folded
    assert "chac" in folded
    assert "ban dinh uu tien phong nao truoc" not in folded


def test_generic_similar_followup_uses_memory_for_retrieval():
    planner = json.dumps({
        "mode": "tenant_sales",
        "intent": "browse_products",
        "need_retrieval": True,
        "search_query": "",
        "filters": {},
        "memory_delta": {},
        "response_goal": "goi y mau tuong tu",
        "ask_user": "",
        "safety_notes": [],
    }, ensure_ascii=False)
    final = "Mình lọc tiếp vài mẫu ghế mềm cho phòng khách theo ngân sách cũ."
    fake = FakeLLMClient([planner, final])
    calls = []

    def retrieve(query, filters):
        calls.append((query, filters))
        return [
            SimpleNamespace(
                title="Ghế mềm phòng khách",
                source="https://example.test/ghe-soft",
                metadata={
                    "sku": "GHE-SOFT",
                    "product_name": "Ghế mềm phòng khách",
                    "category": "Ghế",
                    "price": 2500000,
                    "source_url": "https://example.test/ghe-soft",
                },
            )
        ]

    orch = ConversationOrchestrator(fake)
    memory = {
        "product_focus": "Ghế",
        "room": "phòng khách",
        "budget": "dưới 5 triệu",
        "needs": ["êm và mềm"],
    }
    result = orch.run(
        OrchestratorRequest(message="có mẫu tương tự không", mode="tenant_sales"),
        OrchestratorContext(memory=memory, retrieval_tool=retrieve),
    )

    assert calls
    query, filters = calls[0]
    folded_query = fold_text(query)
    assert "ghe" in folded_query
    assert "phong khach" in folded_query
    assert "5 trieu" in folded_query
    assert filters.get("product_category") == "Ghế"
    assert result.debug["effective_retrieval_query"] == query
    assert result.debug["memory_retained"]


def test_phase_h_compare_fallback_uses_evidence_table():
    planner = json.dumps({
        "mode": "general_compare",
        "intent": "compare",
        "need_retrieval": True,
        "search_query": "sofa vai sofa da",
        "filters": {"product_category": "Sofa"},
        "memory_delta": {},
        "response_goal": "so sanh theo evidence",
        "ask_user": "",
        "safety_notes": [],
    })
    fake = FakeLLMClient([planner, ""])

    def retrieve(query, filters):
        return [
            SimpleNamespace(
                title="Sofa vai hien dai",
                source="https://example.test/sofa-a",
                metadata={
                    "sku": "SOFA-A",
                    "product_name": "Sofa vai hien dai",
                    "category": "Sofa",
                    "price": 9_500_000,
                    "source_url": "https://example.test/sofa-a",
                },
            ),
            SimpleNamespace(
                title="Sofa da de lau",
                source="https://example.test/sofa-b",
                metadata={
                    "sku": "SOFA-B",
                    "product_name": "Sofa da de lau",
                    "category": "Sofa",
                    "price": 12_000_000,
                    "source_url": "https://example.test/sofa-b",
                },
            ),
        ]

    result = ConversationOrchestrator(fake).run(
        OrchestratorRequest(message="so sanh sofa vai voi sofa da", mode="general_compare"),
        OrchestratorContext(memory={}, retrieval_tool=retrieve),
    )

    assert "| Tieu chi | Sofa vai hien dai (SOFA-A) | Sofa da de lau (SOFA-B) |" in result.reply
    assert "| Gia trong du lieu | 9.500.000 VND | 12.000.000 VND |" in result.reply
    assert "Ket luan:" in result.reply
    assert result.debug["phase_h_response_style"] == "criteria_table"


def test_phase_h_market_price_fallback_shows_price_reasoning():
    planner = json.dumps({
        "mode": "market_price",
        "intent": "price_check",
        "need_retrieval": True,
        "search_query": "sofa phong khach 12 trieu",
        "filters": {"product_category": "Sofa"},
        "memory_delta": {},
        "response_goal": "danh gia gia theo evidence",
        "ask_user": "",
        "safety_notes": [],
    })
    fake = FakeLLMClient([planner, ""])

    def retrieve(query, filters):
        return [
            SimpleNamespace(
                title="Sofa phong khach tam trung",
                source="https://example.test/sofa-10",
                metadata={"sku": "SOFA-10", "product_name": "Sofa phong khach tam trung", "category": "Sofa", "price": 10_500_000},
            ),
            SimpleNamespace(
                title="Sofa phong khach cao cap",
                source="https://example.test/sofa-14",
                metadata={"sku": "SOFA-14", "product_name": "Sofa phong khach cao cap", "category": "Sofa", "price": 14_000_000},
            ),
        ]

    result = ConversationOrchestrator(fake).run(
        OrchestratorRequest(message="sofa phong khach 12 trieu co dat khong", mode="market_price"),
        OrchestratorContext(memory={}, retrieval_tool=retrieve),
    )

    assert "Muc hoi: 12 trieu." in result.reply
    assert "Moc tham chieu: 10.500.000 VND - 14.000.000 VND" in result.reply
    assert "Nhan dinh:" in result.reply
    assert "Ket luan:" in result.reply
    assert result.debug["phase_h_response_style"] == "price_reasoning_with_evidence"


def test_reset_new_does_not_call_llm(monkeypatch):
    monkeypatch.setenv("CONVERSATION_ORCHESTRATOR_ENABLED", "1")
    monkeypatch.setenv("SALES_USE_LLM_STATE_INTERPRETER", "0")

    import app.server as server_module

    client = TestClient(server_module.app)
    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=AssertionError("LLM must not be called")):
        for message in ("/new", "/reset"):
            r = _post(client, message, f"orch-reset-{message}")
            assert r.status_code == 200
            payload = r.json()
            debug = payload.get("debug", {})
            assert payload.get("reply") == "Xong."
            assert debug.get("planner_attempted") is False
            assert debug.get("finalizer_attempted") is False
