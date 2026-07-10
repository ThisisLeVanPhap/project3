import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.llm_client import LLMResult
from app.retrievers import RetrievalResult


def _gen(mode, sales_mode="off"):
    return {
        "provider": "stub",
        "mode": mode,
        "retrieval_mode": "keyword",
        "retrieval_top_k": 4,
        "answer_mode": "template",
        "sales_mode": sales_mode,
    }


def _planner(mode, **overrides):
    payload = {
        "mode": mode,
        "intent": "consult",
        "need_retrieval": False,
        "search_query": "",
        "filters": {},
        "memory_delta": {},
        "response_goal": "",
        "ask_user": "",
        "safety_notes": [],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _hit(sku, name, price, category):
    return RetrievalResult(
        doc_id=sku.lower(),
        chunk_id=f"{sku.lower()}#0",
        title=name,
        text=f"{name} la san pham noi that.",
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


def _client(monkeypatch):
    monkeypatch.setenv("CONVERSATION_ORCHESTRATOR_ENABLED", "1")
    monkeypatch.setenv("SALES_USE_LLM_STATE_INTERPRETER", "0")
    import app.server as server_module

    server_module.SALES_STATE_STORE.clear()
    return TestClient(server_module.app), server_module


def _mock_complete(responses, prompts=None):
    queue = list(responses)

    def complete(*args, **kwargs):
        if prompts is not None:
            prompts.append({"purpose": kwargs.get("purpose"), "prompt": kwargs.get("prompt", "")})
        if not queue:
            return LLMResult(text="", called=True, skip_reason="fake_empty")
        return LLMResult(text=queue.pop(0), called=True)

    return complete


def test_general_compare_uses_orchestrator_and_never_creates_lead(monkeypatch):
    client, server_module = _client(monkeypatch)
    hits = [
        _hit("SOFA-A", "Sofa vai hien dai", 9_500_000, "Sofa"),
        _hit("SOFA-B", "Sofa da de lau", 12_000_000, "Sofa"),
    ]
    server_module.KB = SimpleNamespace(search=lambda q, k=4, tenant_id=None: hits)
    server_module.KB_BY_MODE.clear()
    server_module.KB_BY_MODE["keyword"] = server_module.KB
    prompts = []
    final = "COMPARE_FINAL: Sofa vai mem hon va am hon, sofa da de lau hon neu nha co tre nho. Neu uu tien phong khach dung hang ngay, minh nghieng ve sofa da de lau."

    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(
            "general_compare",
            intent="compare",
            need_retrieval=True,
            search_query="sofa vai sofa da phong khach",
            filters={"product_category": "Sofa"},
        ),
        final,
    ], prompts)):
        r = client.post("/chat", json={
            "message": "so sanh sofa vai voi sofa da cho phong khach nha co tre nho",
            "history": [],
            "conversation_id": "phase-c-compare",
            "tenant_id": "t",
            "channel": "web",
            "gen": _gen("general_compare", sales_mode="active"),
        })

    payload = r.json()
    debug = payload["debug"]
    assert payload["reply"] == final
    assert payload["trigger_purchase_request"] is False
    assert server_module.SALES_STATE_STORE == {}
    assert debug["orchestrator_enabled"] is True
    assert debug["planner_called"] is True
    assert debug["finalizer_called"] is True
    assert debug["planner_intent"] == "compare"
    assert debug["planner_need_retrieval"] is True
    assert debug["phase_h_response_style"] == "criteria_table"
    assert debug["sales_boundary"] == "non_sales_no_lead"
    assert "retrieval" in debug["tool_calls"]
    panel = debug["production_debug_panel"]
    assert panel == debug["phase_e_debug_panel"]
    assert panel["phase"] == "E"
    assert panel["mode"] == "general_compare"
    assert panel["planner_intent"] == "compare"
    assert panel["need_retrieval"] is True
    assert panel["retrieval_count"] == 2
    assert panel["retrieved_skus"] == ["SOFA-A", "SOFA-B"]
    assert panel["finalizer_called"] is True
    assert panel["sales_action"] == "none"
    assert panel["lead_created"] is False
    assert any(p["purpose"] == "finalizer" and "Vai tro general_compare" in p["prompt"] for p in prompts)
    assert any(p["purpose"] == "finalizer" and "PHASE H FORMAT general_compare" in p["prompt"] for p in prompts)
    assert any(p["purpose"] == "finalizer" and "markdown table" in p["prompt"] for p in prompts)


def test_market_price_uses_orchestrator_and_price_role_prompt(monkeypatch):
    client, server_module = _client(monkeypatch)
    hits = [
        _hit("SOFA-10", "Sofa phong khach tam trung", 10_500_000, "Sofa"),
        _hit("SOFA-14", "Sofa phong khach cao cap", 14_000_000, "Sofa"),
    ]
    server_module.KB = SimpleNamespace(search=lambda q, k=4, tenant_id=None: hits)
    server_module.KB_BY_MODE.clear()
    server_module.KB_BY_MODE["keyword"] = server_module.KB
    prompts = []
    final = "PRICE_FINAL: Tam 12 trieu cho sofa phong khach la muc co the chap nhan neu kich thuoc vua va chat lieu de ve sinh; neu chi la sofa co ban thi nen so them mau quanh 10 trieu."

    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(
            "market_price",
            intent="price_check",
            need_retrieval=True,
            search_query="sofa phong khach 12 trieu",
            filters={"product_category": "Sofa"},
        ),
        final,
    ], prompts)):
        r = client.post("/chat", json={
            "message": "sofa phong khach 12 trieu co dat khong",
            "history": [],
            "conversation_id": "phase-c-price",
            "tenant_id": "t",
            "channel": "web",
            "gen": _gen("market_price"),
        })

    payload = r.json()
    debug = payload["debug"]
    assert payload["reply"] == final
    assert payload["trigger_purchase_request"] is False
    assert server_module.SALES_STATE_STORE == {}
    assert debug["planner_intent"] == "price_check"
    assert debug["planner_need_retrieval"] is True
    assert debug["finalizer_called"] is True
    assert debug["phase_h_response_style"] == "price_reasoning_with_evidence"
    assert debug["sales_boundary"] == "non_sales_no_lead"
    panel = debug["production_debug_panel"]
    assert panel["mode"] == "market_price"
    assert panel["planner_intent"] == "price_check"
    assert panel["retrieval_count"] == 2
    assert panel["retrieved_skus"] == ["SOFA-10", "SOFA-14"]
    assert panel["finalizer_called"] is True
    assert panel["lead_created"] is False
    assert any(p["purpose"] == "finalizer" and "Vai tro market_price" in p["prompt"] for p in prompts)
    assert any(p["purpose"] == "finalizer" and "PHASE H FORMAT market_price" in p["prompt"] for p in prompts)
    assert any(p["purpose"] == "finalizer" and "Muc hoi" in p["prompt"] and "Moc tham chieu" in p["prompt"] and "Ket luan" in p["prompt"] for p in prompts)


def test_three_mode_orchestrator_pytest_blocks_real_claude(monkeypatch):
    monkeypatch.setenv("CONVERSATION_ORCHESTRATOR_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-that-must-not-be-used")
    monkeypatch.delenv("RUN_REAL_CLAUDE_TESTS", raising=False)
    client, server_module = _client(monkeypatch)
    server_module.KB = None
    server_module.KB_BY_MODE.clear()

    with patch("app.llm_client.call_claude_api", side_effect=AssertionError("real Claude must not be called")) as mocked:
        r = client.post("/chat", json={
            "message": "so sanh sofa vai voi sofa da",
            "history": [],
            "conversation_id": "phase-c-pytest-guard",
            "tenant_id": "t",
            "channel": "web",
            "gen": _gen("general_compare"),
        })

    payload = r.json()
    debug = payload["debug"]
    assert r.status_code == 200
    assert payload["reply"]
    assert mocked.call_count == 0
    assert debug["orchestrator_enabled"] is True
    assert debug["planner_called"] is False
    assert debug["finalizer_called"] is False
    assert debug["production_debug_panel"]["skip_reason"] == "pytest_real_claude_disabled"
    assert "pytest_real_claude_disabled" in (
        debug.get("planner_skip_reason") or debug.get("finalizer_skip_reason") or ""
    )
