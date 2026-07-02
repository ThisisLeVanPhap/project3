import time
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List

try:
    from .sales_slots import extract_sales_slots, fold_text, repair_mojibake, score_lead
    from .purchase_intent_score import score_purchase_intent
except ImportError:  # pragma: no cover - direct script imports
    from app.sales_slots import extract_sales_slots, fold_text, repair_mojibake, score_lead
    from app.purchase_intent_score import score_purchase_intent


CONSULTATION_STAGES = {"discover", "suggest", "compare", "handle_objection", "confirm", "purchase_request"}


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


def known_consultation_slots(state: SalesConversationState) -> Dict[str, Any]:
    keys = (
        "product_type", "product_category", "room", "budget", "budget_text", "budget_usd", "style",
        "space", "material", "color", "constraints", "pets", "kids", "children", "back_pain",
        "health_need", "easy_clean", "selected_product_name", "selected_product_id", "objection_type",
    )
    return {key: state.slots.get(key) for key in keys if state.slots.get(key) not in (None, "", [], {})}


def consultation_missing_slots(state: SalesConversationState) -> List[str]:
    missing: List[str] = []
    slots = state.slots or {}
    has_product = bool(slots.get("product_type") or slots.get("product_category") or state.selected_products)
    if not has_product:
        missing.append("product_type")
    if has_product and not (slots.get("room") or slots.get("space")):
        missing.append("room_or_space")
    if has_product and not (slots.get("budget") or slots.get("budget_text") or slots.get("budget_usd") or slots.get("price_target") or slots.get("price_max")):
        missing.append("budget")
    if state.current_stage == "confirm" and not state.contact and not state.handoff_required:
        missing.append("contact")
    return missing[:2]


def _has_recommendation_readiness(slots: Dict[str, Any]) -> bool:
    """Has enough detail to suggest products: product + substantive constraint.
    Lifestyle signals (pets/kids/back_pain/easy_clean) don't count toward readiness.
    Room alone + bare category doesn't count if no other constraint.
    """
    has_product = bool(slots.get("product_type") or slots.get("product_category"))
    if not has_product:
        return False
    # Subtype (e.g. "ghế văn phòng", "sofa góc", "tủ tivi") counts as readiness
    if has_product and _has_specific_product_subtype(slots):
        return True
    # Substantive constraints that justify listing
    return any(slots.get(key) for key in (
        "budget", "budget_text", "budget_usd", "price_target", "price_max",
        "material", "style", "color", "size",
    ))


def _has_specific_product_subtype(slots: Dict[str, Any]) -> bool:
    """Check if product_type is a specific subtype, not just a bare category.
    A bare category is a single generic furniture word (sofa, ghế, bàn, etc.)
    while a subtype adds qualifiers (ghế văn phòng, sofa góc, bàn ăn, etc.)
    """
    from .retrievers.text import fold_accents
    raw_type = str(slots.get("product_type") or slots.get("product_category") or "")
    folded = fold_accents(raw_type).strip().lower()
    # Generic single-word categories (folded, lowercased)
    generic = {"sofa", "ghe", "ban", "ghe sofa", "tu", "giuong", "ke", "den", "tham", "tranh", "guong", "rem"}
    words = folded.split()
    if len(words) >= 2:
        return True  # "ghế văn phòng", "sofa góc", "bàn ăn"
    return folded not in generic


def consultation_stage_for(state: SalesConversationState, slots: Dict[str, Any] | None = None) -> str:
    slots = slots or {}
    new_intents = slots.get("intents") or []
    # Phase 6: treat ["unknown"] as no intent, fall back to preserved last_intents
    intents = new_intents if new_intents not in ([], ["unknown"]) else (state.slots.get("last_intents") or [])
    if state.handoff_status == "sent":
        return "purchase_request"
    # Phase 6: purchase_intent overrides reference question detection
    if not ("purchase_intent" in intents) and (slots.get("is_product_reference_question") or slots.get("has_product_reference")):
        return "compare"
    if slots.get("objection_type") or state.slots.get("objection_type"):
        return "handle_objection"
    # Phase 7: purchase_intent only confirms if user has selected a specific product
    if "purchase_intent" in intents:
        has_product_ref = slots.get("has_product_reference") or bool(slots.get("product_sku_ref"))
        # Also check if the message itself references a past recommendation
        has_position_ref = bool(state.last_recommended_products) and (
            slots.get("has_product_reference") or bool(state.selected_products))
        # Phase 9C: purchase_request with needs_product status does not indicate a real purchase
        _purchase_has_product = state.purchase_request is not None and (
            state.purchase_request.get("status") not in (None, "needs_product"))
        if state.selected_products or _purchase_has_product or has_product_ref or has_position_ref:
            return "confirm"
        # Vague purchase intent without specific product -> stay in discover/suggest
        if _has_recommendation_readiness(state.slots):
            return "suggest"
        return "discover"
    if state.selected_products and state.contact:
        return "confirm"
    if state.last_recommended_products or state.selected_products:
        return "suggest"
    if _has_recommendation_readiness(state.slots):
        return "suggest"
    return "discover"


def next_best_action(state: SalesConversationState, slots: Dict[str, Any] | None = None) -> str:
    slots = slots or {}
    intents = slots.get("intents") or []
    if state.handoff_status == "sent":
        return "send_purchase_request"
    # Objection takes priority over purchase_intent (prevents false-positive "dat"/"đắt" matching)
    if slots.get("objection_type") or state.slots.get("objection_type"):
        return "handle_objection"
    # Phase 7: purchase_intent only routes to handoff if user selected a specific product
    if "purchase_intent" in intents:
        has_product_ref = slots.get("has_product_reference") or bool(slots.get("product_sku_ref"))
        has_pos_ref = bool(state.last_recommended_products) and has_product_ref
        if state.selected_products:
            if not state.contact and not state.handoff_required:
                return "ask_contact"
            return "ask_confirmation"
        if has_product_ref or has_pos_ref:
            return "ask_product"
        # Phase 7: vague purchase intent without specific product -> always consult/discover
        missing = consultation_missing_slots(state)
        if missing:
            return "ask_discovery_question"
        if _has_recommendation_readiness(state.slots):
            return "suggest_from_kb"
        return "ask_discovery_question"
    if slots.get("is_product_reference_question") or slots.get("has_product_reference"):
        return "compare_options"
    if state.confirmation_status == "pending":
        return "ask_confirmation"
    missing = consultation_missing_slots(state)
    if missing and state.current_stage == "discover":
        return "ask_discovery_question"
    if state.current_stage == "suggest":
        return "suggest_from_kb"
    return "continue_consultation"


def apply_message_to_state(state: SalesConversationState, message: str) -> Dict[str, Any]:
    slots = extract_sales_slots(message)
    incoming = {k: v for k, v in slots.items() if k not in {"intents", "intent", "missing_fields"}}
    old_category = state.slots.get("product_category") or state.slots.get("product_type")
    new_category = incoming.get("product_category") or incoming.get("product_type")
    if old_category and new_category and fold_text(old_category) != fold_text(new_category):
        state.slots["product_category_prev"] = old_category
        state.selected_products = []
        state.purchase_request = None
        state.confirmation_status = "none"
        state.handoff_status = "not_ready"
    state.slots.update(incoming)
    # Phase 6: preserve last_intents if new message has no meaningful intent
    new_intent = slots.get("intent")
    new_intents = slots.get("intents", [])
    if new_intent not in (None, "unknown") and new_intents not in ([], ["unknown"]):
        state.slots["last_intent"] = new_intent
        state.slots["last_intents"] = new_intents
    elif state.slots.get("last_intent") is None:
        state.slots["last_intent"] = new_intent or "unknown"
        state.slots["last_intents"] = new_intents or ["unknown"]
    state.slots["last_nlu_intent"] = slots.get("nlu_intent")
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
        state.slots["selected_product_id"] = resolved.product.get("sku") or resolved.product.get("pid") or resolved.product.get("source_url")
        state.slots["selected_product_name"] = resolved.product.get("product_name")
    # Phase 6B: if user provided SKU reference but resolve failed, store pending SKU reference
    # (do NOT create synthetic selected_product that blocks exact KB lookup)
    sku_ref = slots.get("product_sku_ref")
    if sku_ref:
        state.slots["pending_sku_ref"] = sku_ref

    state.lead_score, state.lead_status = score_lead(slots, has_selected_product=bool(state.selected_products))
    purchase_score = score_purchase_intent(
        slots,
        has_selected_product=bool(state.selected_products),
        has_contact=bool(state.contact),
        has_address=bool(state.slots.get("address") or state.slots.get("location") or state.slots.get("delivery_area")),
    )
    state.slots["purchase_intent_score"] = purchase_score.score
    state.slots["purchase_intent_signals"] = purchase_score.signals
    purchase_missing = suggest_missing_fields(state, slots)
    stage = consultation_stage_for(state, slots)
    state.current_stage = stage
    consult_missing = consultation_missing_slots(state)
    state.missing_fields = purchase_missing or consult_missing
    action = next_best_action(state, slots)
    state.slots["consultation_stage"] = stage
    state.slots["next_best_action"] = action
    # Phase 9: always update consultation_missing_slots, even when empty (clears stale values)
    state.slots["consultation_missing_slots"] = consult_missing
    state.updated_at = time.time()
    return {"slots": slots, "resolved_product": resolved, "stage": stage, "next_best_action": action, "missing_slots": consult_missing}


def suggest_missing_fields(state: SalesConversationState, slots: Dict[str, Any] | None = None) -> List[str]:
    slots = slots or {}
    missing: List[str] = []
    # Phase 9B: only require product for genuine purchase intent (has specific product ref/SKU)
    has_real_purchase = bool(
        state.selected_products or slots.get("has_product_reference") or slots.get("product_sku_ref")
    ) if "purchase_intent" in slots.get("intents", []) else False
    if not state.selected_products and has_real_purchase:
        missing.append("product")
    if state.selected_products and not state.contact and not state.handoff_required:
        missing.append("contact")
    if state.selected_products and state.contact and not (state.slots.get("address") or state.slots.get("location") or state.slots.get("delivery_area")):
        if (state.slots.get("purchase_intent_score") or 0) >= 0.85:
            missing.append("address")
    return missing
