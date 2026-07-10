import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.llm_client import LLMResult
from app.retrievers import RetrievalResult
from app.sales_state import SalesConversationState
from app.sales_slots import fold_text


GEN = {
    "provider": "stub",
    "mode": "tenant_sales",
    "retrieval_mode": "keyword",
    "retrieval_top_k": 4,
    "answer_mode": "template",
    "sales_mode": "active",
}

RAW_RENDERER_PHRASES = (
    "Mình tìm thấy một số sản phẩm phù hợp trong dữ liệu hiện có",
    "Phù hợp vì:",
    "Thuộc tính chính:",
)


def _planner(**overrides):
    payload = {
        "mode": "tenant_sales",
        "intent": "consult",
        "need_retrieval": False,
        "search_query": "",
        "filters": {},
        "memory_delta": {},
        "response_goal": "consult",
        "ask_user": "",
        "safety_notes": [],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _client(monkeypatch):
    monkeypatch.setenv("CONVERSATION_ORCHESTRATOR_ENABLED", "1")
    monkeypatch.setenv("SALES_USE_LLM_STATE_INTERPRETER", "0")
    import app.server as server_module

    server_module.SALES_STATE_STORE.clear()
    return TestClient(server_module.app), server_module


def _post(client, message, conv="phase-b"):
    return client.post("/chat", json={
        "message": message,
        "history": [],
        "conversation_id": conv,
        "tenant_id": "t",
        "channel": "web",
        "gen": GEN,
    })


def _hit(doc_id, name, sku, category):
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=name,
        text=f"{name} là sản phẩm nội thất.",
        source=f"https://example.test/{sku.lower()}",
        score=10.0,
        metadata={
            "doc_type": "product",
            "product_name": name,
            "category": category,
            "price": 2500000,
            "currency": "VND",
            "sku": sku,
            "source_url": f"https://example.test/{sku.lower()}",
        },
    )


def _mock_complete(responses, prompts=None):
    queue = list(responses)

    def complete(*args, **kwargs):
        purpose = kwargs.get("purpose")
        prompt = kwargs.get("prompt", "")
        if prompts is not None:
            prompts.append({"purpose": purpose, "prompt": prompt})
        if not queue:
            return LLMResult(text="", called=True, skip_reason="fake_empty")
        return LLMResult(text=queue.pop(0), called=True)

    return complete


def test_tenant_sales_new_home_consult_planner_first(monkeypatch):
    client, server_module = _client(monkeypatch)
    server_module.KB = None
    server_module.KB_BY_MODE.clear()
    final = "Nhà mới mua thì nên bắt đầu từ cách sinh hoạt, rồi ưu tiên phòng khách, phòng ngủ và khu bếp cho đồng bộ. Bạn muốn bắt đầu với phòng khách hay phòng ngủ trước?"
    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(memory_delta={"home_context": "nhà mới"}),
        final,
    ])):
        r = _post(client, "t đang nghĩ đến việc mua nội thất cho nhà t, nhà t mới mua luôn", "b-new-home")

    payload = r.json()
    debug = payload["debug"]
    assert debug["orchestrator_enabled"] is True
    assert debug["planner_intent"] == "consult"
    assert debug["planner_need_retrieval"] is False
    assert debug["customer_brief"].get("product_focus") != "Đèn"
    assert "voi den" not in fold_text(payload["reply"])
    assert "nha moi" in fold_text(payload["reply"])


def test_tenant_sales_living_room_empty_consult_planner_first(monkeypatch):
    client, server_module = _client(monkeypatch)
    server_module.KB = None
    server_module.KB_BY_MODE.clear()
    final = "Với phòng khách đang trống, mình sẽ ưu tiên chỗ ngồi trước, rồi thêm bàn/kệ để cân không gian và ánh sáng/trang trí cho phòng ấm hơn. Bạn muốn đi từ sofa/bộ ghế hay bàn/kệ trước?"
    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(memory_delta={"room": "phòng khách"}),
        final,
    ])):
        r = _post(client, "t muốn mua đồ đặt trong phòng khách của t tại nó đang khá trống, có cái bàn hay bộ ghế nào hay không", "b-living")

    reply = r.json()["reply"]
    folded = fold_text(reply)
    assert "sofa, ban, giuong, tu hay mon khac" not in folded
    assert "phong khach" in folded
    assert "cho ngoi" in folded
    assert "ban/ke" in folded or "ban" in folded
    assert "anh sang" in folded or "trang tri" in folded
    assert reply.count("?") <= 1
    assert r.json()["debug"]["planner_need_retrieval"] is False


def test_tenant_sales_old_home_idea_does_not_read_ban_or_vai_false_positive(monkeypatch):
    client, server_module = _client(monkeypatch)
    server_module.KB = None
    server_module.KB_BY_MODE.clear()
    final = "Nhà cũ muốn làm mới để đón khách thì mình sẽ ưu tiên phòng khách trước: chỗ ngồi thoải mái, bàn/kệ gọn lại, rồi thêm ánh sáng hoặc decor để không gian sáng và có điểm nhấn hơn. Bạn muốn làm mới theo hướng ấm cúng hay gọn hiện đại?"
    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(memory_delta={"home_context": "nhà cũ", "needs": ["đón khách", "làm mới không gian"]}),
        final,
    ])):
        r = _post(client, "nhà t cũ vài chưởng rồi, t đang định thay 1 vài nội thất để đón khách đến chơi nhà, bạn có ý tưởng hay đề xuất gì không?", "b-old-home-idea")

    payload = r.json()
    debug = payload["debug"]
    brief = debug["customer_brief"]
    folded = fold_text(payload["reply"])
    assert brief.get("product_focus", "") not in {"Bàn", "ban"}
    assert brief.get("material", "") not in {"vai", "vải"}
    assert "voi ban" not in folded
    assert "phong khach" in folded
    assert payload["debug"]["planner_need_retrieval"] is False


def test_tenant_sales_change_from_table_to_chair_updates_memory(monkeypatch):
    client, server_module = _client(monkeypatch)
    server_module.KB = None
    server_module.KB_BY_MODE.clear()
    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(memory_delta={"room": "phòng khách"}),
        "Phòng khách nên cân chỗ ngồi, bàn/kệ và ánh sáng trước. Bạn muốn ưu tiên món nào?",
        _planner(memory_delta={"product_focus": "Ghế", "dislikes": ["Bàn"]}),
        "Được, mình chuyển sang bộ ghế nhé; với phòng khách nên ưu tiên ngồi thoải mái, kích thước vừa phòng và chất liệu dễ vệ sinh. Bạn thích ghế mềm thư giãn hay gọn hiện đại hơn?",
    ])):
        _post(client, "t muốn mua bàn hay bộ ghế cho phòng khách", "b-change")
        r2 = _post(client, "thôi, t muốn hỏi bộ ghế hơn, t hết thích bàn rồi", "b-change")

    debug = r2.json()["debug"]
    brief = debug["customer_brief"]
    assert debug["sales_action_taken"] != "cancelled"
    assert brief.get("product_focus") == "Ghế"
    assert "Bàn" in brief.get("dislikes", [])
    assert "ghe" in fold_text(r2.json()["reply"])


def test_tenant_sales_focus_change_clears_stale_products(monkeypatch):
    client, server_module = _client(monkeypatch)
    server_module.KB = None
    server_module.KB_BY_MODE.clear()
    conv = "b-change-clears-products"
    state = SalesConversationState(tenant_id="t", conversation_id=conv)
    state.slots.update({"product_category": "BÃ n", "product_type": "BÃ n"})
    state.selected_products = [{"sku": "BAN-OLD", "product_name": "BÃ n cÅ©"}]
    state.last_recommended_products = [{"sku": "BAN-OLD", "product_name": "BÃ n cÅ©"}]
    state.purchase_request = {"status": "draft", "items": [{"sku": "BAN-OLD"}]}
    state.confirmation_status = "none"
    state.handoff_required = False
    state.handoff_status = "not_ready"
    server_module.SALES_STATE_STORE[("t", conv)] = state

    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(memory_delta={"product_focus": "Gháº¿", "dislikes": ["BÃ n"]}),
        "ÄÆ°á»£c, mÃ¬nh chuyá»ƒn sang gháº¿ vÃ  bá» cÃ¡c gá»£i Ã½ bÃ n cÅ© khá»i ngá»¯ cáº£nh nhÃ©.",
    ])):
        r = _post(client, "thÃ´i Ä‘á»•i sang gháº¿ Ä‘i, t khÃ´ng thÃ­ch bÃ n ná»¯a", conv)

    payload = r.json()
    debug = payload["debug"]
    final_state = server_module.SALES_STATE_STORE[("t", conv)]
    assert debug["memory_product_focus_changed"] is True
    assert fold_text(debug["memory_product_focus_before"]) == "ban"
    assert fold_text(debug["memory_product_focus_after"]) == "ghe"
    assert final_state.selected_products == []
    assert final_state.last_recommended_products == []
    assert final_state.purchase_request is None
    assert final_state.confirmation_status == "none"
    assert final_state.handoff_required is False
    assert fold_text(final_state.slots["product_category"]) == "ghe"


def test_tenant_sales_chair_styles_no_raw_renderer(monkeypatch):
    client, server_module = _client(monkeypatch)
    server_module.KB = None
    server_module.KB_BY_MODE.clear()
    final = "Với ghế kiểu mềm, mình sẽ chia vài hướng: lounge êm, hiện đại gọn, Bắc Âu sáng màu hoặc cổ điển nhẹ. Nếu dùng phòng khách hằng ngày thì nên ưu tiên đệm vừa phải, tựa chắc và chất liệu dễ vệ sinh. Bạn thích hướng lounge mềm hay tối giản gọn hơn?"
    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(memory_delta={"product_focus": "Ghế"}),
        "Mình sẽ tư vấn ghế theo cách dùng và không gian trước. Bạn thích ngồi thư giãn hay tiếp khách?",
        _planner(memory_delta={"product_focus": "Ghế", "needs": ["êm và mềm"]}),
        final,
    ])):
        _post(client, "t muốn mua ghế", "b-style")
        r2 = _post(client, "cơ mà t thích ghế kiểu mềm mềm cơ, với cả bên cửa hàng m bán ghế có những phong cách gì?", "b-style")

    reply = r2.json()["reply"]
    assert all(phrase not in reply for phrase in RAW_RENDERER_PHRASES)
    folded = fold_text(reply)
    assert "lounge" in folded or "bac au" in folded or "hien dai" in folded
    assert r2.json()["debug"]["planner_need_retrieval"] is False


def test_tenant_sales_listing_uses_finalizer_once(monkeypatch):
    client, server_module = _client(monkeypatch)
    hits = [
        _hit("chair-1", "Ghế mềm phòng khách", "GHE-SOFT-01", "Ghế"),
        _hit("table-1", "Bàn trà gỗ", "BAN-RAW-99", "Bàn"),
        _hit("chair-2", "Bộ ghế lounge", "GHE-LOUNGE-02", "Ghế"),
    ]
    server_module.KB = SimpleNamespace(search=lambda q, k=4: hits)
    server_module.KB_BY_MODE.clear()
    server_module.KB_BY_MODE["keyword"] = server_module.KB
    prompts = []
    final = "FINALIZER_OK: Mình chọn GHE-SOFT-01 và GHE-LOUNGE-02 vì đều là hướng ghế mềm để tham khảo trước. Bạn muốn so theo độ êm hay kích thước?"
    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(
            intent="browse_products",
            need_retrieval=True,
            search_query="ghế mềm phòng khách",
            filters={"product_category": "Ghế"},
            memory_delta={"product_focus": "Ghế"},
        ),
        final,
    ], prompts)):
        r = _post(client, "cho t vài bộ ghế mềm để tham khảo đi", "b-listing")

    finalizer_prompts = [p["prompt"] for p in prompts if p["purpose"] == "finalizer"]
    assert len(finalizer_prompts) == 1
    assert "GHE-SOFT-01" in finalizer_prompts[0]
    assert "GHE-LOUNGE-02" in finalizer_prompts[0]
    assert "BAN-RAW-99" not in finalizer_prompts[0]
    payload = r.json()
    assert payload["reply"] == final
    assert all(phrase not in payload["reply"] for phrase in RAW_RENDERER_PHRASES)
    assert payload["debug"]["planner_need_retrieval"] is True
    assert payload["debug"]["retrieval_count"] > 0


def test_tenant_sales_listing_fallback_not_raw_renderer_when_finalizer_blocked(monkeypatch):
    client, server_module = _client(monkeypatch)
    hits = [
        _hit("chair-1", "Ghế mềm phòng khách", "GHE-SOFT-01", "Ghế"),
        _hit("table-1", "Bàn trà gỗ", "BAN-RAW-99", "Bàn"),
    ]
    server_module.KB = SimpleNamespace(search=lambda q, k=4: hits)
    server_module.KB_BY_MODE.clear()
    server_module.KB_BY_MODE["keyword"] = server_module.KB
    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(
            intent="browse_products",
            need_retrieval=True,
            search_query="ghế mềm",
            filters={"product_category": "Ghế"},
            memory_delta={"product_focus": "Ghế"},
        ),
        "",
    ])):
        r = _post(client, "cho t vài bộ ghế mềm để tham khảo đi", "b-listing-fallback")

    payload = r.json()
    assert "GHE-SOFT-01" in payload["reply"]
    assert "BAN-RAW-99" not in payload["reply"]
    assert all(phrase not in payload["reply"] for phrase in RAW_RENDERER_PHRASES)
    assert payload["debug"]["finalizer_skip_reason"] == "empty_finalizer_fallback"
    assert payload["debug"]["orchestrator_fallback_reason"] == "finalizer_fallback"


def test_tenant_sales_pytest_blocks_real_claude_even_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-that-must-not-be-used")
    monkeypatch.delenv("RUN_REAL_CLAUDE_TESTS", raising=False)
    client, server_module = _client(monkeypatch)
    server_module.KB = None
    server_module.KB_BY_MODE.clear()
    with patch("app.llm_client.call_claude_api", side_effect=AssertionError("real Claude must not be called")) as mocked:
        r = _post(client, "t đang nghĩ đến việc mua nội thất cho nhà t, nhà t mới mua luôn", "b-pytest-block")

    payload = r.json()
    assert r.status_code == 200
    assert payload["reply"]
    assert mocked.call_count == 0
    assert payload["debug"]["planner_skip_reason"] == "pytest_real_claude_disabled"
    assert payload["debug"]["orchestrator_enabled"] is True


def test_tenant_sales_room_size_thoi_does_not_cancel_pending_consult(monkeypatch):
    client, server_module = _client(monkeypatch)
    conv = "b-room-size-thoi"
    state = SalesConversationState(tenant_id="t", conversation_id=conv)
    state.confirmation_status = "pending"
    state.handoff_status = "pending_confirmation"
    state.purchase_request = {"status": "draft", "items": [{"sku": "SOFA-OLD"}]}
    state.slots.update({"product_focus": "Sofa", "room": "phong khach"})
    server_module.SALES_STATE_STORE[("t", conv)] = state
    server_module.KB = None
    server_module.KB_BY_MODE.clear()
    final = "Phong 3x3 m thi minh se uu tien sofa bang nho hoac sofa goc gon, tranh bo qua sau de loi di van thoang. Minh se loc tiep theo kich thuoc nho va tam 10 trieu cho ban."

    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=_mock_complete([
        _planner(memory_delta={"room_size": "3x3 m", "room": "phong khach"}),
        final,
    ])):
        r = _post(client, "cho day cua t chac khoang 3x3 m thoi", conv)

    payload = r.json()
    folded = fold_text(payload["reply"])
    debug = payload["debug"]
    assert "huy yeu cau" not in folded
    assert debug["sales_action_taken"] != "confirmation_cancelled"
    assert debug["sales_action_taken"] != "cancelled"
    assert debug["orchestrator_enabled"] is True
    assert payload["reply"] == final


def test_new_reset_bypass_orchestrator(monkeypatch):
    client, _server_module = _client(monkeypatch)
    with patch("app.llm_client.ClaudeLLMClient.complete", side_effect=AssertionError("LLM must not be called")):
        for message in ("/new", "/reset"):
            r = _post(client, message, f"b-{message}")
            payload = r.json()
            assert payload["reply"] == "Xong."
            assert payload["debug"]["planner_attempted"] is False
            assert payload["debug"]["finalizer_attempted"] is False
