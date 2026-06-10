import time
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List

try:
    from .sales_slots import extract_sales_slots, fold_text, repair_mojibake, score_lead
except ImportError:  # pragma: no cover - direct script imports
    from app.sales_slots import extract_sales_slots, fold_text, repair_mojibake, score_lead


@dataclass
class ProductReferenceResult:
    matched: bool
    product: Dict[str, Any] | None = None
    reason: str = "no_match"
    confidence: float = 0.0


@dataclass
class SalesConversationState:
    tenant_id: str | None = None
    conversation_id: str | None = None
    current_stage: str = "discover"
    slots: Dict[str, Any] = field(default_factory=dict)
    last_recommended_products: List[Dict[str, Any]] = field(default_factory=list)
    selected_products: List[Dict[str, Any]] = field(default_factory=list)
    lead_score: float = 0.0
    lead_status: str = "cold"
    contact: Dict[str, Any] = field(default_factory=dict)
    purchase_request: Dict[str, Any] | None = None
    last_purchase_draft: Dict[str, Any] | None = None
    handoff_required: bool = False
    missing_fields: List[str] = field(default_factory=list)
    confirmation_status: str = "none"
    handoff_status: str = "not_ready"
    handoff_id: str | None = None
    handoff_error: str | None = None
    confirmed_at: float | None = None
    sent_at: float | None = None
    updated_at: float = field(default_factory=time.time)


def state_to_dict(state: SalesConversationState) -> Dict[str, Any]:
    return asdict(state)


def state_from_dict(data: Dict[str, Any] | None) -> SalesConversationState:
    if not data:
        return SalesConversationState()
    fields = SalesConversationState.__dataclass_fields__
    return SalesConversationState(**{key: data.get(key) for key in fields if key in data})


def _metadata(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        metadata = item.get("metadata") or {}
    else:
        metadata = getattr(item, "metadata", {}) or {}
    return metadata if isinstance(metadata, dict) else {}


def _field(item: Any, *names: str) -> Any:
    metadata = _metadata(item)
    for name in names:
        if isinstance(item, dict) and item.get(name) not in (None, ""):
            return item.get(name)
        value = getattr(item, name, None)
        if value not in (None, ""):
            return value
        if metadata.get(name) not in (None, ""):
            return metadata.get(name)
    return None


def _price_number(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def normalize_product(item: Any, idx: int) -> Dict[str, Any]:
    product = dict(item) if isinstance(item, dict) else {}
    product.update({
        "pid": _field(item, "pid") or product.get("pid") or f"P{idx}",
        "product_name": _field(item, "product_name", "title", "name") or "",
        "sku": _field(item, "sku") or "",
        "source_url": _field(item, "source_url", "canonical_url", "url", "source") or "",
        "price": _field(item, "price") or product.get("price"),
    })
    product["price_number"] = _price_number(product.get("price"))
    return product


def update_recommended_products(
    state: SalesConversationState,
    retrieval_hits_or_context_products: List[Any],
) -> SalesConversationState:
    state.last_recommended_products = [
        normalize_product(item, idx)
        for idx, item in enumerate(retrieval_hits_or_context_products or [], start=1)
    ]
    return state


def clear_or_replace_recommendations(
    state: SalesConversationState,
    products: List[Any] | None = None,
) -> SalesConversationState:
    state.last_recommended_products = []
    if products:
        update_recommended_products(state, products)
    return state


def _ordinal_index(message: str) -> int | None:
    text = fold_text(message)
    direct = __import__("re").search(r"\bp\s*([1-9]\d*)\b", text)
    if direct:
        return int(direct.group(1)) - 1
    mau = __import__("re").search(r"\b(?:mau|san pham)\s*(?:thu\s*)?([1-9]\d*)\b", text)
    if mau:
        return int(mau.group(1)) - 1
    words = {
        "mot": 0, "nhat": 0, "dau": 0,
        "hai": 1, "nhi": 1,
        "ba": 2,
        "bon": 3, "tu": 3,
        "nam": 4,
        "cuoi": -1,
    }
    for phrase, idx in (
        ("cai dau", 0),
        ("mau dau", 0),
        ("san pham dau", 0),
        ("cai cuoi", -1),
        ("mau cuoi", -1),
        ("san pham cuoi", -1),
        ("mau thu hai", 1),
        ("san pham thu hai", 1),
    ):
        if phrase in text:
            return idx
    for word, idx in words.items():
        if f"thu {word}" in text:
            return idx
    return None


def _target_price(message: str) -> int | None:
    text = fold_text(message).replace(".", "").replace(",", "")
    import re
    match = re.search(r"\b([1-9]\d{1,3})\s*k\b", text)
    if match:
        return int(match.group(1)) * 1000
    match = re.search(r"\b([1-9]\d{5,8})\b", text)
    if match:
        return int(match.group(1))
    return None


def resolve_product_reference(message: str, state: SalesConversationState) -> ProductReferenceResult:
    products = state.last_recommended_products or []
    if not products:
        return ProductReferenceResult(False, None, "no_recommendations", 0.0)

    idx = _ordinal_index(message)
    if idx is not None:
        if idx == -1:
            idx = len(products) - 1
        if 0 <= idx < len(products):
            return ProductReferenceResult(True, products[idx], "position_reference", 0.95)
        return ProductReferenceResult(False, None, "position_out_of_range", 0.2)

    text = fold_text(repair_mojibake(message or ""))
    for product in products:
        sku = fold_text(product.get("sku"))
        if sku and sku in text:
            return ProductReferenceResult(True, product, "sku_match", 0.98)

    target_price = _target_price(message)
    if target_price is not None:
        priced = [(abs((p.get("price_number") or 0) - target_price), p) for p in products if p.get("price_number")]
        if priced:
            diff, product = min(priced, key=lambda item: item[0])
            tolerance = max(50_000, int(target_price * 0.08))
            if diff <= tolerance:
                return ProductReferenceResult(True, product, "price_match", 0.82)

    best_product = None
    best_score = 0.0
    generic_name_tokens = {
        "sofa", "ban", "ghe", "tu", "giuong", "ke", "mau", "san", "pham",
        "chair", "table", "cabinet", "bed", "shelf",
    }
    for product in products:
        name = fold_text(product.get("product_name"))
        if not name:
            continue
        name_tokens = [token for token in name.split() if len(token) >= 4 and token not in generic_name_tokens]
        if name in text or any(token in text for token in name_tokens):
            score = 0.75
        else:
            score = SequenceMatcher(None, name, text).ratio()
        if score > best_score:
            best_score = score
            best_product = product
    if best_product and best_score >= 0.45:
        return ProductReferenceResult(True, best_product, "name_match", min(0.9, best_score))
    return ProductReferenceResult(False, None, "no_match", best_score)


def apply_message_to_state(state: SalesConversationState, message: str) -> Dict[str, Any]:
    slots = extract_sales_slots(message)
    state.slots.update({k: v for k, v in slots.items() if k not in {"intents", "intent", "missing_fields"}})
    state.slots["last_intent"] = slots.get("intent")
    state.slots["last_intents"] = slots.get("intents", [])
    for key in ("phone", "email"):
        if slots.get(key):
            state.contact[key] = slots[key]

    if slots.get("intent") == "handoff_request":
        state.handoff_required = True
    if slots.get("intent") == "cancel":
        state.current_stage = "cancelled"
        state.purchase_request = None
    elif slots.get("intent") == "purchase_intent":
        state.current_stage = "purchase_intent"

    resolved = resolve_product_reference(message, state)
    if resolved.matched and resolved.product:
        if not any((p.get("sku"), p.get("source_url"), p.get("product_name")) == (resolved.product.get("sku"), resolved.product.get("source_url"), resolved.product.get("product_name")) for p in state.selected_products):
            state.selected_products.append(resolved.product)

    state.lead_score, state.lead_status = score_lead(slots, has_selected_product=bool(state.selected_products))
    state.missing_fields = suggest_missing_fields(state, slots)
    state.updated_at = time.time()
    return {"slots": slots, "resolved_product": resolved}


def suggest_missing_fields(state: SalesConversationState, slots: Dict[str, Any] | None = None) -> List[str]:
    slots = slots or {}
    missing: List[str] = []
    if not state.selected_products and ("purchase_intent" in slots.get("intents", []) or state.contact):
        missing.append("product")
    if state.selected_products and not state.contact and not state.handoff_required:
        missing.append("contact")
    return missing
