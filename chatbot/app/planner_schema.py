import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .sales_slots import fold_text, repair_mojibake


ALLOWED_MODES = {"tenant_sales", "general_compare", "market_price"}
ALLOWED_INTENTS = {
    "consult",
    "clarify",
    "browse_products",
    "compare",
    "price_check",
    "lead",
    "reset",
    "out_of_scope",
}


@dataclass
class PlannerDecision:
    mode: str
    intent: str = "consult"
    need_retrieval: bool = False
    search_query: str = ""
    filters: Dict[str, Any] = field(default_factory=dict)
    memory_delta: Dict[str, Any] = field(default_factory=dict)
    response_goal: str = ""
    ask_user: str = ""
    safety_notes: List[str] = field(default_factory=list)


def fallback_planner_decision(mode: str, reason: str = "fallback") -> PlannerDecision:
    return PlannerDecision(
        mode=mode if mode in ALLOWED_MODES else "tenant_sales",
        intent="consult",
        need_retrieval=False,
        safety_notes=[reason],
    )


def parse_planner_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def _specific_retrieval_signal(message: str, query: str, filters: Dict[str, Any]) -> bool:
    text = fold_text(repair_mojibake(message or ""))
    query_text = fold_text(query or "")
    has_browse_verb = bool(re.search(r"\b(xem|loc|mau|san pham|goi y|tim|tham khao|co .*khong|vai|list|danh sach)\b", text))
    table_signal = _has_table_signal(message, text) or _has_table_signal(query, query_text)
    has_specific_product = bool(
        re.search(r"\b(sofa|ghe|tu|giuong|ke|den|tranh|tham|guong|rem)\b", text)
        or filters.get("product_category")
        or filters.get("product_type")
        or table_signal
        or re.search(r"\b(sofa|ghe|tu|giuong|ke|den|tranh|tham|guong|rem)\b", query_text)
    )
    return has_browse_verb and (has_specific_product or bool(query_text.strip()))


def _has_table_signal(raw_message: str, folded: str) -> bool:
    raw = repair_mojibake(raw_message or "").lower()
    if re.search(r"\bbàn\b", raw):
        return True
    return bool(
        re.search(r"\b(?:mua|tim|chon|lay|can|xem|goi y|tu van|kiem)\s+(?:\d+\s+)?(?:cai\s+)?ban\b", folded)
        or re.search(r"\bban\s+(?:tra|an|hoc|lam viec|sofa|may tinh|trang diem|phu|go|nho|lon|keo|gap)\b", folded)
        or re.search(r"\b(?:bo ban|mat ban|chan ban|table|desk)\b", folded)
    )


def _remove_false_lamp_filter(message: str, filters: Dict[str, Any], memory_delta: Dict[str, Any]) -> None:
    text = fold_text(repair_mojibake(message or ""))
    category = fold_text(filters.get("product_category") or filters.get("product_type") or "")
    if category != "den":
        return
    explicit_lamp = bool(re.search(r"\b(mua|tim|chon|xem|loc|can|goi y)\s+(?:\d+\s+)?(?:cai\s+)?den\b", text))
    explicit_lamp = explicit_lamp or bool(re.search(r"\bden\s+(trang tri|chum|tha|tran|tuong|ban|cay|ngu|led|hoc|doc sach)\b", text))
    if explicit_lamp:
        return
    filters.pop("product_category", None)
    if fold_text(filters.get("product_type") or "") == "den":
        filters.pop("product_type", None)
    if fold_text(memory_delta.get("product_category") or "") == "den":
        memory_delta.pop("product_category", None)
    if fold_text(memory_delta.get("product_type") or "") == "den":
        memory_delta.pop("product_type", None)


def validate_planner_decision(data: Dict[str, Any], *, request_mode: str, user_message: str) -> PlannerDecision:
    mode = str(data.get("mode") or request_mode).strip()
    if mode != request_mode or mode not in ALLOWED_MODES:
        raise ValueError("planner_mode_mismatch")

    intent = str(data.get("intent") or "consult").strip()
    if intent not in ALLOWED_INTENTS:
        intent = "consult"
    if mode != "tenant_sales" and intent == "lead":
        intent = "consult"
    if mode == "tenant_sales":
        pass

    filters = dict(data.get("filters") or {})
    memory_delta = dict(data.get("memory_delta") or {})
    _remove_false_lamp_filter(user_message, filters, memory_delta)
    _repair_preference_change(user_message, filters, memory_delta)

    need_retrieval = bool(data.get("need_retrieval"))
    search_query = str(data.get("search_query") or "").strip()
    mode_retrieval_ok = _mode_specific_retrieval_signal(mode, user_message, search_query, filters, intent)
    if need_retrieval and not (_specific_retrieval_signal(user_message, search_query, filters) or mode_retrieval_ok):
        need_retrieval = False
    if not need_retrieval and (
        (intent == "browse_products" and _specific_retrieval_signal(user_message, search_query, filters))
        or mode_retrieval_ok
    ):
        need_retrieval = True

    return PlannerDecision(
        mode=mode,
        intent=intent,
        need_retrieval=need_retrieval,
        search_query=search_query,
        filters=filters,
        memory_delta=memory_delta,
        response_goal=str(data.get("response_goal") or ""),
        ask_user=str(data.get("ask_user") or ""),
        safety_notes=[str(v) for v in (data.get("safety_notes") or [])],
    )


def _mode_specific_retrieval_signal(
    mode: str,
    message: str,
    query: str,
    filters: Dict[str, Any],
    intent: str,
) -> bool:
    text = fold_text(repair_mojibake(message or ""))
    query_text = fold_text(query or "")
    has_subject = bool(query_text.strip() or filters.get("product_category") or filters.get("product_type"))
    if mode == "general_compare":
        compare_signal = bool(
            intent == "compare"
            or re.search(r"\b(so sanh|khac nhau|nen chon|chon cai nao|cai nao hon|a hay b|voi)\b", text)
        )
        product_signal = bool(
            re.search(r"\b(sofa|ghe|ban|tu|giuong|ke|den|tranh|tham|guong|rem)\b", text)
            or _has_table_signal(message, text)
        )
        return compare_signal and (has_subject or product_signal)
    if mode == "market_price":
        price_signal = bool(
            intent == "price_check"
            or re.search(r"\b(gia|dat|re|hop ly|dang tien|bao nhieu|tam gia|thi truong|market|price)\b", text)
        )
        product_signal = bool(
            re.search(r"\b(sofa|ghe|ban|tu|giuong|ke|den|tranh|tham|guong|rem)\b", text)
            or _has_table_signal(message, text)
        )
        return price_signal and (has_subject or product_signal)
    return False


def _repair_preference_change(message: str, filters: Dict[str, Any], memory_delta: Dict[str, Any]) -> None:
    text = fold_text(repair_mojibake(message or ""))
    if "ghe" in text and ("het thich ban" in text or "khong thich ban" in text or re.search(r"\bthoi\b.*\bban\b", text)):
        memory_delta["product_focus"] = "Ghế"
        filters.setdefault("product_category", "Ghế")
        dislikes = list(memory_delta.get("dislikes") or [])
        if not any(fold_text(item) == "ban" for item in dislikes):
            dislikes.append("Bàn")
        memory_delta["dislikes"] = dislikes


def decision_from_planner_text(text: str, *, request_mode: str, user_message: str) -> Tuple[PlannerDecision, str]:
    try:
        data = parse_planner_json(text)
        return validate_planner_decision(data, request_mode=request_mode, user_message=user_message), ""
    except Exception as exc:
        return fallback_planner_decision(request_mode, exc.__class__.__name__), "invalid_planner_json"
