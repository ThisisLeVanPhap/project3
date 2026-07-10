"""
Phase 11C: LLM-based state interpreter for tenant_sales conversation flow.

When Claude is available, interprets user intent and suggests safe state updates.
When Claude is unavailable/error, returns None — caller falls through to existing logic.
Deterministic parsed fields (budget, SKU, size, etc.) always override LLM suggestions.

Interpreter MUST run BEFORE action selection.
Consultation LLM runs AFTER interpreter/action decision for response wording only.
"""

import json
import os
import re
import unicodedata
from typing import Any, Dict, Optional, List

try:
    from .sales_flow import STYLE_MAP_VI, STYLE_TO_VI
except ImportError:
    from app.sales_flow import STYLE_MAP_VI, STYLE_TO_VI

ALLOWED_SEMANTIC_KEYS = {
    "product_category", "product_type", "room", "style", "color", "material",
    "space", "purpose", "product_subtype", "constraints",
}

# Phase 11C: Add missing_slots, response_mode to schema
STATE_INTERPRETER_PROMPT = """Bạn là trợ lý tư vấn nội thất thông minh. Phân tích tin nhắn của khách hàng và trả về JSON cập nhật trạng thái tư vấn.

QUAN TRỌNG:
- Nếu khách hàng chỉ thêm budget/phòng/phong cách mà không nói đổi sản phẩm, GIỮ NGUYÊN product_category cũ.
- "đổi sang X", "thôi lấy Y", "chuyển sang Z" = replace_need, thay đổi product_category.
- "có mẫu tương tự không", "còn mẫu khác không" = similar_request, giữ category/budget.
- "thôi hiện đại đi" = update_slot style, không đổi category.
- "à không phòng khách chứ" = update_slot room, không đổi category.

Trạng thái hiện tại:
{state_json}

Tin nhắn: {user_message}

Trả về JSON hợp lệ (chỉ JSON, không markdown):
{{
  "intent": "consultation|add_constraint|update_slot|replace_need|similar_request|purchase_specific_product|confirm|cancel|chitchat|unknown",
  "change_type": "add|update|replace|clear|none",
  "slot_updates": {{}},
  "slots_to_keep": [],
  "slots_to_clear": [],
  "missing_slots": [],
  "should_retrieve": false,
  "should_handoff": false,
  "should_ask": true,
  "response_mode": "consultation_llm|product_listing|handoff|fallback_template",
  "confidence": 0.0,
  "user_facing_ack": ""
}}
"""

CONSULTATION_PROMPT = """Bạn là nhân viên tư vấn nội thất. Trả lời khách hàng bằng tiếng Việt tự nhiên, ngắn gọn (2-3 câu).

Quy tắc:
- KHÔNG bịa sản phẩm, SKU, giá, link.
- KHÔNG nói "mình tìm thấy" nếu chưa có kết quả tìm kiếm.
- Đưa ra 1-2 câu tư vấn ngắn về loại sản phẩm, chất liệu, phong cách.
- HỎI ĐÚNG MỘT câu hỏi tiếp theo hữu ích nhất.
- Nếu khách hàng vừa thay đổi ý kiến, xác nhận thay đổi đó.

Current state: {state_json}
Thiếu thông tin: {missing_info}
"""


def _build_state_snapshot(slots: Dict[str, Any]) -> Dict[str, Any]:
    """Build a safe summary snapshot for the LLM prompt (no contact details)."""
    keys = {
        "product_category", "product_type", "room", "budget", "budget_text",
        "budget_usd", "budget_min", "price_min", "price_max", "price_target",
        "style", "color", "material", "space", "size", "room_size",
        "constraints", "pets", "kids", "objection_type",
    }
    return {k: v for k, v in slots.items() if k in keys and v not in (None, "", [], {})}


def _is_pytest_blocking_real_claude() -> bool:
    if os.getenv("RUN_REAL_CLAUDE_TESTS", "0").strip().lower() in ("1", "true", "yes", "on"):
        return False
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def call_state_interpreter(
    user_message: str,
    current_slots: Dict[str, Any],
    *,
    api_key: Optional[str] = None,
    api_model: str = "claude-sonnet-4-6",
    api_base_url: str = "https://api.anthropic.com",
) -> Optional[Dict[str, Any]]:
    """Call Claude to interpret user message. Returns parsed JSON or None."""
    if not api_key:
        return None
    if _is_pytest_blocking_real_claude():
        return None
    state_snapshot = _build_state_snapshot(current_slots)
    prompt = STATE_INTERPRETER_PROMPT.format(
        state_json=json.dumps(state_snapshot, ensure_ascii=False),
        user_message=user_message,
    )
    from .claude_provider import call_claude_api
    text, error_code, error_preview = call_claude_api(
        prompt, api_key, api_model, api_base_url,
        max_tokens=1024, temperature=0.1, timeout_seconds=30,
    )
    if error_code or not text:
        return None
    return _parse_interpreter_output(text)


def _parse_interpreter_output(text: str) -> Optional[Dict[str, Any]]:
    t = text.strip()
    if "```" in t:
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    t = t.strip()
    try:
        parsed = json.loads(t)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {
        "intent": str(parsed.get("intent", "consultation")),
        "change_type": str(parsed.get("change_type", "none")),
        "slot_updates": parsed.get("slot_updates", {}),
        "slots_to_keep": list(parsed.get("slots_to_keep", [])),
        "slots_to_clear": list(parsed.get("slots_to_clear", [])),
        "missing_slots": list(parsed.get("missing_slots", [])),
        "should_retrieve": bool(parsed.get("should_retrieve", False)),
        "should_handoff": bool(parsed.get("should_handoff", False)),
        "should_ask": bool(parsed.get("should_ask", True)),
        "response_mode": str(parsed.get("response_mode", "consultation_llm")),
        "confidence": float(parsed.get("confidence", 0.0)),
        "user_facing_ack": str(parsed.get("user_facing_ack", "")),
    }


def apply_interpreter_to_state(
    state: Any,
    interpreter_result: Dict[str, Any],
    deterministic_slots: Dict[str, Any],
) -> None:
    """Apply interpreter result to sales state safely.

    Phase 11C: Safe application rules:
    1. Capture old_cat BEFORE applying slot_updates.
    2. Allowed semantic keys from LLM only.
    3. Forbidden raw LLM keys: budget_min/max, sku, phone, email, selected_*, purchase_request_*, etc.
    4. Deterministic slots override LLM and are applied last.
    5. Null values do not clear fields unless field is in slots_to_clear.
    6. Category replacement clears selected/recommended products.
    7. similar_request keeps category/budget/room/style.
    8. update_slot keeps unrelated slots.
    """
    # 1. Capture old category BEFORE any mutations
    old_cat = state.slots.get("product_category") or state.slots.get("product_type")
    old_cat_folded = _fold(str(old_cat)) if old_cat else ""

    slot_updates = interpreter_result.get("slot_updates", {})
    intent = interpreter_result.get("intent", "consultation")

    # 2. Apply slots_to_clear first (remove from state.slots and special attrs)
    for key in interpreter_result.get("slots_to_clear", []):
        if key == "last_recommended_products":
            state.last_recommended_products = []
        elif key == "selected_products":
            state.selected_products = []
        else:
            state.slots.pop(key, None)

    # 3. Apply LLM semantic slot_updates (only allowed keys)
    # Phase 11C: Explicitly block unsafe keys
    UNSAFE_LLM_KEYS = {
        "budget_min", "budget_max", "price_target",
        "sku", "phone", "email",
        "selected_product", "selected_products",
        "last_recommended_products", "purchase_request",
        "purchase_request_status", "handoff_status",
    }
    for key, value in slot_updates.items():
        if value is None or value == "null":
            continue
        if key not in ALLOWED_SEMANTIC_KEYS:
            continue
        if key in UNSAFE_LLM_KEYS:
            continue
        state.slots[key] = value

    # 4. Apply slots_to_keep (ensure these keys are preserved from old state)
    #    Already handled by not clearing them above; no-op.

    # 5. Apply deterministic overrides (authoritative) — LAST
    for key, value in deterministic_slots.items():
        if value is not None and value not in ("", [], {}):
            state.slots[key] = value
        else:
            state.slots.pop(key, None)

    # 6. Category change handling
    new_cat = (slot_updates.get("product_category")
               or slot_updates.get("product_type")
               or deterministic_slots.get("product_category")
               or deterministic_slots.get("product_type"))
    if new_cat and new_cat != "null":
        new_cat_folded = _fold(str(new_cat))
        if old_cat_folded and old_cat_folded != new_cat_folded:
            state.selected_products = []
            state.last_recommended_products = []
            state.purchase_request = None

    # 7. Intent-based actions
    if intent == "replace_need":
        state.selected_products = []
        state.last_recommended_products = []
    if intent == "similar_request":
        pass  # keep category/budget, just re-retrieve

    # 8. Room update clears room_size/area
    new_room = slot_updates.get("room") or deterministic_slots.get("room")
    if new_room:
        state.slots["room_size"] = None
        state.slots.pop("room_size", None)


def call_consultation_llm(
    user_message: str,
    current_slots: Dict[str, Any],
    missing_info: List[str],
    *,
    api_key: Optional[str] = None,
    api_model: str = "claude-sonnet-4-6",
    api_base_url: str = "https://api.anthropic.com",
) -> Optional[str]:
    """Call Claude for natural consultation response."""
    if not api_key:
        return None
    if _is_pytest_blocking_real_claude():
        return None
    state_snapshot = _build_state_snapshot(current_slots)
    prompt = CONSULTATION_PROMPT.format(
        state_json=json.dumps(state_snapshot, ensure_ascii=False),
        missing_info=", ".join(missing_info) if missing_info else "chưa xác định",
    )
    from .claude_provider import call_claude_api
    text, error_code, error_preview = call_claude_api(
        prompt, api_key, api_model, api_base_url,
        max_tokens=512, temperature=0.7, timeout_seconds=30,
    )
    if error_code or not text:
        return None
    return text.strip()


def _fold(text: str) -> str:
    """Simple accent folding for comparison."""
    t = text.lower().replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
