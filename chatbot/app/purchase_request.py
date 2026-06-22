from typing import Any, Dict

try:
    from .sales_slots import extract_sales_slots
    from .sales_state import SalesConversationState
except ImportError:  # pragma: no cover - direct script imports
    from app.sales_slots import extract_sales_slots
    from app.sales_state import SalesConversationState


def _draft_product(product: Dict[str, Any], quantity: int | None) -> Dict[str, Any]:
    return {
        "sku": product.get("sku") or "",
        "product_name": product.get("product_name") or product.get("name") or "",
        "source_url": product.get("source_url") or product.get("url") or "",
        "price": product.get("price"),
        "quantity": quantity or product.get("quantity") or 1,
    }


def build_purchase_request_draft(state: SalesConversationState, message: str) -> Dict[str, Any]:
    slots = extract_sales_slots(message)
    intents = slots.get("intents", [])
    quantity = slots.get("quantity") or state.slots.get("quantity") or 1

    contact = dict(state.contact or {})
    if slots.get("phone"):
        contact["phone"] = slots["phone"]
    if slots.get("email"):
        contact["email"] = slots["email"]

    handoff_required = state.handoff_required or "handoff_request" in intents
    location = slots.get("location") or slots.get("delivery_area") or state.slots.get("location") or state.slots.get("delivery_area")
    address = slots.get("address") or state.slots.get("address")

    if "cancel" in intents:
        status = "cancelled"
    elif not state.selected_products:
        status = "needs_product"
    elif not contact and not handoff_required:
        status = "needs_contact"
    else:
        status = "draft"

    draft = {
        "tenant_id": state.tenant_id,
        "conversation_id": state.conversation_id,
        "products": [_draft_product(product, quantity) for product in state.selected_products],
        "contact": {
            "phone": contact.get("phone", ""),
            "email": contact.get("email", ""),
        },
        "location": location or "",
        "address": address or "",
        "notes": "Purchase request draft only. Not an order confirmation; stock, delivery and final price must be confirmed by staff.",
        "status": status,
        "handoff_required": bool(handoff_required),
    }
    state.purchase_request = draft
    state.last_purchase_draft = draft
    state.contact.update(contact)
    if location:
        state.slots["location"] = location
    if address:
        state.slots["address"] = address
    if quantity:
        state.slots["quantity"] = quantity
    if status == "draft":
        state.confirmation_status = "pending"
        state.handoff_status = "pending_confirmation"
        state.handoff_error = None
    elif status in {"needs_contact", "needs_product"}:
        state.confirmation_status = "none"
        state.handoff_status = "not_ready"
    elif status == "cancelled":
        state.confirmation_status = "cancelled"
        state.handoff_status = "cancelled"
    return draft
