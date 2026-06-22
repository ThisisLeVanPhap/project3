from dataclasses import dataclass
from typing import Any, Dict, Iterable


SHOW_CTA = 0.45
CREATE_LEAD = 0.65
HANDOFF_READY = 0.85


@dataclass(frozen=True)
class PurchaseIntentScore:
    score: float
    show_cta: bool
    create_lead: bool
    handoff_ready: bool
    signals: Dict[str, bool]


def _has_any(slots: Dict[str, Any], keys: Iterable[str]) -> bool:
    return any(bool(slots.get(key)) for key in keys)


def score_purchase_intent(
    slots: Dict[str, Any] | None,
    *,
    has_selected_product: bool = False,
    has_contact: bool = False,
    has_address: bool = False,
) -> PurchaseIntentScore:
    slots = slots or {}
    intents = set(slots.get("intents") or [])
    nlu_intent = slots.get("nlu_intent")
    explicit_buy = "purchase_intent" in intents or nlu_intent == "BUY_INTENT"
    asked_shipping_payment = bool(
        slots.get("has_ship_or_stock_question")
        or nlu_intent in {"ASK_SHIPPING", "ASK_PAYMENT"}
        or "shipping_or_payment" in intents
    )
    quantity_or_budget = bool(slots.get("quantity") or _has_any(slots, ("budget", "budget_text", "budget_usd", "price_min", "price_max")))
    contact = has_contact or bool(slots.get("phone") or slots.get("email"))
    address = has_address or bool(slots.get("address") or slots.get("location") or slots.get("delivery_area"))
    selected = has_selected_product or bool(slots.get("selected_product_id") or slots.get("selected_product_name"))

    signals = {
        "explicit_buy_intent": explicit_buy,
        "selected_product": selected,
        "asked_shipping_payment": asked_shipping_payment,
        "quantity_or_budget": quantity_or_budget,
        "phone_provided": contact,
        "address_or_delivery_area": address,
    }
    score = 0.0
    if explicit_buy:
        score += 0.30
    if selected:
        score += 0.20
    if asked_shipping_payment:
        score += 0.15
    if quantity_or_budget:
        score += 0.10
    if contact:
        score += 0.20
    if address:
        score += 0.15
    score = min(1.0, round(score, 4))

    return PurchaseIntentScore(
        score=score,
        show_cta=score >= SHOW_CTA,
        create_lead=score >= CREATE_LEAD,
        handoff_ready=score >= HANDOFF_READY,
        signals=signals,
    )


def should_create_purchase_request_draft(slots: Dict[str, Any] | None, *, has_selected_product: bool, has_contact: bool) -> bool:
    scored = score_purchase_intent(slots, has_selected_product=has_selected_product, has_contact=has_contact)
    return bool(scored.create_lead and has_selected_product and has_contact)
