import json
import os
import time
import re
import threading
import gc
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .guardrails import rule_reply, want_similar
from .logger import log_event, log_feedback, log_retrieval_debug

# --- SALES FLOW imports ---
from .state import get_state, save_turn, set_stage, reset_state
from .sales_flow import extract_slots, next_stage, build_sales_prefix, detect_intent, has_sufficient_constraints
from .purchase_request import build_purchase_request_draft
from .purchase_intent_score import score_purchase_intent, should_create_purchase_request_draft
from .sales_handoff import InMemorySalesHandoffService, StoredSalesHandoffService, build_sales_handoff_service
from .sales_response_renderer import render_sales_response
from .sales_slots import extract_sales_slots
from .sales_state import (
    SalesConversationState,
    apply_message_to_state,
    known_consultation_slots,
    resolve_product_reference,
    state_to_dict,
    update_recommended_products,
)

from .claude_provider import call_claude_api as _call_claude_api
from .market_price_insight_provider import (
    BackendMarketPriceInsightProvider,
    build_market_price_insight_provider,
)
from .market_price_reply import (
    build_market_price_insight_reply as _market_price_insight_reply,
    build_market_price_reply as _market_price_reply,
    extract_price_values_from_context as _extract_price_values_from_context,
)
from .prompt import build_messages, DEFAULT_SYSTEM, is_vietnamese_text
from .response_guards import BAD_FACTS, apply_grounding_guard as _apply_grounding_guard
from .runtime_config import TRUE_VALUES, load_runtime_config
from .modes import ChatMode, mode_system_instruction, normalize_chat_mode
from .product_answer_renderer import render_product_answer
from .general_catalog_provider import (
    BackendGeneralCatalogProvider,
    build_backend_catalog_provider,
    format_backend_catalog_items,
)
from .general_compare_renderer import render_general_compare
from .product_filters import filter_by_category
from .market_data import (
    build_internal_catalog_provider,
    build_price_provider,
    format_catalog_candidates,
    format_price_references,
)
from .retrieval_service import (
    format_context,
    load_kb as load_retrieval_kb,
    normalize_retrieval_mode,
    search_hits,
    should_allow_retrieval,
    summarize_retrieval_debug,
    top_similar_items,
)


def _detect_and_track_preference_changes(existing_slots: Dict[str, Any], new_slots: Dict[str, Any]) -> None:
    """
    Track preference changes by storing previous values.
    For each preference key, if it exists in both and values differ, store old value as {key}_prev.
    Modifies existing_slots in-place.
    """
    PREFERENCE_KEYS = ["style", "color", "material", "budget_usd", "budget_text", "space", "product_type"]

    for key in PREFERENCE_KEYS:
        if key in existing_slots and key in new_slots:
            old_val = existing_slots[key]
            new_val = new_slots[key]
            # Compare values (handle both string and bool)
            if old_val != new_val:
                # Store previous value before overwriting
                existing_slots[f"{key}_prev"] = old_val
        elif key in new_slots:
            # New preference being set, clear any old _prev marker
            existing_slots.pop(f"{key}_prev", None)


def _handle_topic_change(existing_slots: Dict[str, Any], new_slots: Dict[str, Any], mode: str) -> None:
    """
    Detect topic change (product_type change) and reset relevant slots.
    When user switches to a different product type, clear slots that are product-specific
    while preserving general preferences (style, color, material, budget, space).
    """
    if "product_type" not in new_slots:
        return

    old_product = existing_slots.get("product_type")
    new_product = new_slots["product_type"]

    if old_product and new_product and old_product != new_product:
        # In tenant sales flow, product_type is the main product slot.
        # No other product-specific slots need reset currently.
        pass

_CONFIG = load_runtime_config()

LOCAL_MODEL_ENABLED = _CONFIG.local_model_enabled
BASE_MODEL_DEFAULT = _CONFIG.base_model_default
TOKENIZER_DEFAULT = _CONFIG.tokenizer_default
DISABLED_LOCAL_MODELS = _CONFIG.disabled_local_models

MAX_NEW_TOKENS_DEFAULT = _CONFIG.max_new_tokens_default
CLAUDE_MAX_NEW_TOKENS = _CONFIG.claude_max_new_tokens
LOCAL_FALLBACK_MAX_TOKENS = _CONFIG.local_fallback_max_tokens

TEMPERATURE_DEFAULT = _CONFIG.temperature_default
TOP_P_DEFAULT = _CONFIG.top_p_default
TOP_K_DEFAULT = _CONFIG.top_k_default
RETRIEVAL_MODE_DEFAULT = _CONFIG.retrieval_mode_default
RETRIEVAL_TOP_K_DEFAULT = _CONFIG.retrieval_top_k_default
PRODUCT_TEMPLATE_ANSWERS_DEFAULT = _CONFIG.product_template_answers_default

FALLBACK_TO_LOCAL_ENABLED = _CONFIG.fallback_to_local_enabled
LOCAL_FALLBACK_TIMEOUT_SECONDS = _CONFIG.local_fallback_timeout_seconds

LOCAL_PIPELINE_MAX_CACHE = _CONFIG.local_pipeline_max_cache
LOCAL_PIPELINE_IDLE_TTL_SECONDS = _CONFIG.local_pipeline_idle_ttl_seconds
LOCAL_PIPELINE_CLEANUP_INTERVAL_SECONDS = _CONFIG.local_pipeline_cleanup_interval_seconds

app = FastAPI(title="Multi-tenant Chatbot Model Server")

PipelineCacheKey = Tuple[str, Optional[str], Optional[str]]


@dataclass
class PipelineCacheEntry:
    pipe: Any
    last_used: float
    key: PipelineCacheKey
    base_model: str
    adapter: Optional[str]
    tokenizer_path: Optional[str]


PIPE_CACHE: Dict[PipelineCacheKey, PipelineCacheEntry] = {}
PIPE_CACHE_LOCK = threading.Lock()
CACHE_LOCK = PIPE_CACHE_LOCK
PIPE_CACHE_CLEANUP_STARTED = False
PIPE_CACHE_CLEANUP_START_LOCK = threading.Lock()

# ---- READY flags ----
READY = False
READY_ERR: Optional[str] = None
READY_LOCK = threading.Lock()

# KB: load theo env KB_DIR (mỗi process python 1 tenant)
KB_DIR = os.getenv("KB_DIR")
KB = None
KB_RETRIEVAL_MODE = normalize_retrieval_mode(RETRIEVAL_MODE_DEFAULT)
if KB_DIR:
    try:
        KB = load_retrieval_kb(KB_DIR, mode=KB_RETRIEVAL_MODE)
        print("[kb] loaded from", KB_DIR, "mode=", KB_RETRIEVAL_MODE)
    except Exception as e:
        print("[kb] load failed:", e)
        KB = None
KB_BY_MODE: Dict[str, Any] = {}
if KB is not None:
    KB_BY_MODE[KB_RETRIEVAL_MODE] = KB

INTERNAL_CATALOG_PROVIDER = build_internal_catalog_provider(KB_DIR)
BACKEND_CATALOG_PROVIDER = build_backend_catalog_provider()
BACKEND_MARKET_PRICE_PROVIDER = build_market_price_insight_provider()
PRICE_PROVIDER = build_price_provider()

SALES_MODES = {"off", "shadow", "active"}
SALES_STATE_STORE: Dict[Tuple[str, str], SalesConversationState] = {}
SALES_STATE_LOCK = threading.Lock()
SALES_STATE_TTL_SECONDS = int(os.getenv("SALES_STATE_TTL_SECONDS", "1800"))
SALES_HANDOFF_SERVICE = build_sales_handoff_service()


class GenerationConfig(BaseModel):
    base_model: Optional[str] = None
    adapter: Optional[str] = None
    tokenizer_path: Optional[str] = None
    system_prompt: Optional[str] = None
    max_new_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    stop: Optional[List[str]] = None
    provider: Optional[str] = None
    api_model: Optional[str] = None
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    mode: Optional[str] = None  # tenant_sales | general_compare | market_price
    retrieval_mode: Optional[str] = None
    retrieval_top_k: Optional[int] = None
    answer_mode: Optional[str] = None  # llm | template
    sales_mode: Optional[str] = None  # off | shadow | active


class ChatReq(BaseModel):
    message: str
    history: List[str] = Field(default_factory=list)
    gen: GenerationConfig = Field(default_factory=GenerationConfig)

    # metadata
    conversation_id: Optional[str] = None
    channel: Optional[str] = None      # web / messenger / telegram
    tenant_id: Optional[str] = None


class ChatResp(BaseModel):
    reply: str
    latency_ms: int
    model: str
    adapter: Optional[str]
    trigger_purchase_request: Optional[bool] = False
    captured_phone: Optional[str] = None
    captured_name: Optional[str] = None
    debug: Optional[Dict[str, Any]] = None


def _set_ready(value: bool, err: Optional[str] = None):
    global READY, READY_ERR
    with READY_LOCK:
        READY = value
        READY_ERR = err


def _is_test_mode() -> bool:
    return os.getenv("CHATBOT_TEST_MODE", "0").strip().lower() in TRUE_VALUES


def _force_non_sales_purchase_trigger() -> bool:
    return os.getenv("CHATBOT_TEST_FORCE_NON_SALES_TRIGGER", "0").strip().lower() in TRUE_VALUES


def _is_disabled_local_model(model_name: Optional[str]) -> bool:
    return (model_name or "").strip().lower() in DISABLED_LOCAL_MODELS


def _select_provider(cfg: GenerationConfig) -> str:
    if _is_test_mode():
        return "stub"
    if cfg.provider:
        provider = cfg.provider.strip().lower()
        if provider in {"anthropic", "claude"}:
            return "claude"
        if provider in {"huggingface", "local"}:
            return "local"
        return provider
    return "claude"


def _resolve_answer_mode(cfg: GenerationConfig) -> str:
    value = (cfg.answer_mode or "").strip().lower()
    if not value:
        return "template" if PRODUCT_TEMPLATE_ANSWERS_DEFAULT else "llm"
    if value in {"llm", "template"}:
        return value
    raise ValueError(f"Unsupported answer_mode: {cfg.answer_mode}")


def _resolve_sales_mode(cfg: GenerationConfig) -> str:
    request_value = cfg.sales_mode
    value = (request_value if request_value is not None else os.getenv("SALES_CONVERSATION_MODE", "off"))
    normalized = (value or "off").strip().lower()
    if normalized not in SALES_MODES:
        raise ValueError(f"Unsupported sales_mode: {value}")
    return normalized


def _sales_state_key(tenant_id: Optional[str], conversation_id: Optional[str]) -> Tuple[str, str]:
    return ((tenant_id or "default").strip() or "default", (conversation_id or "anon").strip() or "anon")


def _sales_state_is_persistent(conversation_id: Optional[str]) -> bool:
    return bool((conversation_id or "").strip())


def _cleanup_sales_states(now: Optional[float] = None) -> int:
    now = time.time() if now is None else now
    if SALES_STATE_TTL_SECONDS <= 0:
        return 0
    with SALES_STATE_LOCK:
        expired = [
            key for key, state in SALES_STATE_STORE.items()
            if now - getattr(state, "updated_at", now) > SALES_STATE_TTL_SECONDS
        ]
        for key in expired:
            SALES_STATE_STORE.pop(key, None)
    return len(expired)


def _load_sales_state(tenant_id: Optional[str], conversation_id: Optional[str]) -> SalesConversationState:
    if not _sales_state_is_persistent(conversation_id):
        return SalesConversationState(tenant_id=tenant_id, conversation_id=conversation_id)
    _cleanup_sales_states()
    key = _sales_state_key(tenant_id, conversation_id)
    with SALES_STATE_LOCK:
        state = SALES_STATE_STORE.get(key)
        if state is None:
            state = SalesConversationState(tenant_id=tenant_id, conversation_id=conversation_id)
            SALES_STATE_STORE[key] = state
        return state


def _save_sales_state(state: SalesConversationState) -> None:
    if not _sales_state_is_persistent(state.conversation_id):
        return
    state.updated_at = time.time()
    key = _sales_state_key(state.tenant_id, state.conversation_id)
    with SALES_STATE_LOCK:
        SALES_STATE_STORE[key] = state


def _clear_sales_state(tenant_id: Optional[str], conversation_id: Optional[str]) -> None:
    if not _sales_state_is_persistent(conversation_id):
        return
    key = _sales_state_key(tenant_id, conversation_id)
    with SALES_STATE_LOCK:
        SALES_STATE_STORE.pop(key, None)


def _purchase_request_status(state: Optional[SalesConversationState]) -> Optional[str]:
    if not state or not state.purchase_request:
        return None
    return state.purchase_request.get("status")


def _safe_sales_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    safe = []
    for product in products:
        safe.append({
            "pid": product.get("pid"),
            "sku": product.get("sku"),
            "product_name": product.get("product_name"),
            "source_url": product.get("source_url"),
            "price": product.get("price"),
        })
    return safe


def _sales_debug_payload(
    sales_mode: str,
    state: Optional[SalesConversationState],
    sales_result: Optional[Dict[str, Any]],
    action: str,
    persistent: bool = True,
    state_warning: Optional[str] = None,
) -> Dict[str, Any]:
    slots = (sales_result or {}).get("slots") or {}
    payload = {
        "sales_mode": sales_mode,
        "sales_intents": slots.get("intents", []),
        "nlu_intent": slots.get("nlu_intent") or getattr(state, "slots", {}).get("last_nlu_intent") if state else None,
        "lead_score": getattr(state, "lead_score", 0) if state else 0,
        "lead_status": getattr(state, "lead_status", "cold") if state else "cold",
        "purchase_intent_score": getattr(state, "slots", {}).get("purchase_intent_score", 0) if state else 0,
        "selected_products": _safe_sales_products(list(getattr(state, "selected_products", []) or [])) if state else [],
        "last_recommended_count": len(getattr(state, "last_recommended_products", []) or []) if state else 0,
        "purchase_request_status": _purchase_request_status(state),
        "confirmation_status": getattr(state, "confirmation_status", "none") if state else "none",
        "handoff_status": getattr(state, "handoff_status", "not_ready") if state else "not_ready",
        "handoff_id": getattr(state, "handoff_id", None) if state else None,
        "missing_fields": list(getattr(state, "missing_fields", []) or []) if state else [],
        "current_stage": getattr(state, "current_stage", None) if state else None,
        "known_slots": known_consultation_slots(state) if state else {},
        "missing_slots": list(getattr(state, "slots", {}).get("consultation_missing_slots", []) or []) if state else [],
        "next_best_action": getattr(state, "slots", {}).get("next_best_action") if state else None,
        "objection_type": (slots.get("objection_type") or getattr(state, "slots", {}).get("objection_type")) if state else None,
        "handoff_required": bool(getattr(state, "handoff_required", False)) if state else False,
        "sales_action_taken": action,
        "sales_state_persistent": persistent,
    }
    if state_warning:
        payload["sales_state_warning"] = state_warning
    if slots.get("is_product_reference_question"):
        payload["is_product_reference_question"] = True
    return payload


from .retrievers.text import fold_accents as _fold_sku


def _normalize_sku(sku: str) -> str:
    """Normalize SKU for comparison: strip separators, lowercase."""
    return sku.lower().replace("-", "").replace("_", "")


def _resolve_sku_to_selected_product(
    state: Any,
    retrieval_hits: List[Any],
    active_kb: Any,
    sku_ref: str,
    message: str,
    tenant_id: Optional[str],
    retrieval_mode: str,
) -> None:
    """Try to find a product matching sku_ref in retrieval_hits or KB, store in selected_products."""
    from .retrieval_service import search_hits as _sku_search
    sku_norm = _normalize_sku(sku_ref)

    def _find_in_hits(hits):
        for hit in hits:
            if isinstance(hit, dict):
                meta = hit.get("metadata") or {}
                hit_sku = meta.get("sku") or hit.get("sku") or ""
                hit_source = meta.get("source_url") or hit.get("source_url") or ""
                hit_name = meta.get("product_name") or hit.get("product_name") or ""
            else:
                meta = getattr(hit, "metadata", {}) or {}
                hit_sku = meta.get("sku") or getattr(hit, "sku", "") or ""
                hit_source = meta.get("source_url") or getattr(hit, "source_url", "") or ""
                hit_name = meta.get("product_name") or getattr(hit, "product_name", "") or ""
            if hit_sku and _normalize_sku(str(hit_sku)) == sku_norm:
                return hit
            # Also check if sku_ref appears in source_url or title
            if sku_ref.lower() in hit_source.lower() or sku_ref.lower() in str(getattr(hit, "title", "") or hit_name).lower():
                return hit
        return None

    matched = _find_in_hits(retrieval_hits)
    if matched is None and active_kb is not None:
        sku_search = _sku_search(active_kb, sku_ref, k=10, tenant_id=tenant_id)
        matched = _find_in_hits(sku_search)
    if matched is not None:
        from .sales_state import normalize_product as _norm_prod
        prod = _norm_prod(matched, 1)
        state.selected_products = [prod]
        state.slots["selected_product_id"] = _normalize_sku(sku_ref)
        state.slots["selected_product_name"] = (prod.get("product_name") or matched.get("title") or sku_ref)
        state.slots["selected_product_sku"] = sku_ref


def _sales_action_from_state(
    state: SalesConversationState,
    sales_result: Dict[str, Any],
    draft: Optional[Dict[str, Any]],
) -> str:
    slots = sales_result.get("slots") or {}
    current_intents = slots.get("intents") or []
    # Phase 6: fall back to preserved state intents when current message has no meaningful intent
    intents = current_intents if current_intents not in ([], ["unknown"]) else (state.slots.get("last_intents") or [])
    status = (draft or {}).get("status")
    if "cancel" in intents:
        return "cancelled"
    if not slots.get("is_product_reference_question") and not slots.get("has_product_reference") and (slots.get("objection_type") or state.slots.get("objection_type")):
        return "handle_objection"
    if "handoff_request" in intents:
        return "handoff"
    if state.current_stage == "discover" and state.slots.get("next_best_action") == "ask_discovery_question":
        # Phase 6: purchase_intent with product reference -> ask_product/ask_contact, not discovery
        if "purchase_intent" in intents:
            if state.selected_products:
                return "ask_contact"
            # Phase 7: only route to ask_product if user has a specific product reference (not just category)
            if slots.get("has_product_reference") or bool(slots.get("product_sku_ref")):
                return "ask_product"
        return "ask_discovery"
    # Phase 7: purchase_intent only routes to handoff if user selected a specific product
    if "purchase_intent" in intents:
        if state.selected_products:
            if not state.contact and not state.handoff_required:
                return "ask_contact"
            return "ask_confirmation"
        # No selected product but user mentioned a specific reference -> ask which product
        if slots.get("has_product_reference") or bool(slots.get("product_sku_ref")):
            return "ask_product"
        # Vague purchase intent without specific product -> check if consultation needed
        if state.slots.get("consultation_missing_slots"):
            return "ask_discovery"
        return "none"
    if status == "draft" and ("purchase_intent" in intents or "contact_provided" in intents):
        return "ask_confirmation"
    if status == "needs_contact" and "purchase_intent" in intents:
        return "ask_contact"
    if status == "needs_product" and ("purchase_intent" in intents or ("contact_provided" in intents and state.purchase_request)):
        return "ask_product"
    return "none"


def _has_sendable_pending_draft(state: SalesConversationState) -> bool:
    draft = state.purchase_request or {}
    return (
        state.confirmation_status == "pending"
        and state.handoff_status == "pending_confirmation"
        and draft.get("status") == "draft"
        and bool(draft.get("products"))
        and bool((draft.get("contact") or {}).get("phone") or (draft.get("contact") or {}).get("email"))
    )


def _has_retryable_failed_draft(state: SalesConversationState) -> bool:
    draft = state.purchase_request or {}
    return (
        state.confirmation_status == "confirmed"
        and state.handoff_status == "failed"
        and draft.get("status") == "draft"
        and bool(draft.get("products"))
        and bool((draft.get("contact") or {}).get("phone") or (draft.get("contact") or {}).get("email"))
    )


def _is_pending_draft_update(state: SalesConversationState, slots: Dict[str, Any]) -> bool:
    if state.confirmation_status != "pending" or state.handoff_status != "pending_confirmation":
        return False
    if slots.get("confirmation_intent") == "confirm":
        return False
    return bool(
        slots.get("phone")
        or slots.get("email")
        or slots.get("quantity")
        or slots.get("has_product_reference")
    )


def _apply_pending_draft_update(
    state: SalesConversationState,
    message: str,
    slots: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    if slots.get("phone"):
        state.contact["phone"] = slots["phone"]
    if slots.get("email"):
        state.contact["email"] = slots["email"]
    if slots.get("quantity"):
        state.slots["quantity"] = slots["quantity"]

    if slots.get("has_product_reference"):
        resolved = resolve_product_reference(message, state)
        if resolved.matched and resolved.product:
            state.selected_products = [resolved.product]

    draft = build_purchase_request_draft(state, "dat hang")
    _ensure_durable_pending_request(state, draft, event_type="draft_updated")
    state.updated_at = time.time()
    return _sales_action_from_state(state, {"slots": {"intents": ["purchase_intent"]}}, draft), draft


def _durable_handoff_service() -> Optional[StoredSalesHandoffService]:
    if isinstance(SALES_HANDOFF_SERVICE, StoredSalesHandoffService):
        return SALES_HANDOFF_SERVICE
    return None


def _ensure_durable_pending_request(
    state: SalesConversationState,
    draft: Optional[Dict[str, Any]],
    event_type: str | None = None,
) -> None:
    if not draft or draft.get("status") != "draft":
        return
    service = _durable_handoff_service()
    if service is None:
        return
    service.ensure_pending_request(draft, state, event_type=event_type)


def _append_durable_event(state: SalesConversationState, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    service = _durable_handoff_service()
    if service is not None:
        service.append_state_event(state, event_type, payload or {})


def _handle_pending_confirmation(
    state: SalesConversationState,
    confirmation_intent: Optional[str],
) -> Optional[Tuple[str, Dict[str, Any]]]:
    if confirmation_intent is None:
        return None
    if confirmation_intent == "reject" and state.handoff_status == "sent":
        _append_durable_event(state, "duplicate_confirm_ignored", {"reason": "cancel_after_sent"})
        return "handoff_already_sent", state.purchase_request or {}
    if confirmation_intent == "reject" and state.confirmation_status == "pending":
        state.confirmation_status = "cancelled"
        state.handoff_status = "cancelled"
        if state.purchase_request:
            state.purchase_request["status"] = "cancelled"
        service = _durable_handoff_service()
        if service is not None:
            service.cancel_pending_request(state, "user_cancelled_pending_confirmation")
        state.updated_at = time.time()
        return "confirmation_cancelled", state.purchase_request or {}
    if confirmation_intent != "confirm":
        return None
    if state.handoff_status == "sent":
        _append_durable_event(state, "duplicate_confirm_ignored", {"reason": "already_sent_state"})
        return "handoff_already_sent", state.purchase_request or {}
    if not _has_sendable_pending_draft(state) and not _has_retryable_failed_draft(state):
        _append_durable_event(state, "confirmation_without_pending_ignored", {
            "confirmation_status": state.confirmation_status,
            "handoff_status": state.handoff_status,
        })
        return "confirmation_without_pending", state.purchase_request or {}

    state.confirmation_status = "confirmed"
    state.confirmed_at = time.time()
    result = SALES_HANDOFF_SERVICE.send_purchase_request(state.purchase_request or {}, state)
    if result.success:
        state.handoff_status = "sent"
        state.handoff_id = result.handoff_id
        state.handoff_error = None
        state.sent_at = time.time()
        state.updated_at = time.time()
        if result.already_sent:
            return "handoff_already_sent", state.purchase_request or {}
        return "handoff_sent", state.purchase_request or {}
    state.handoff_status = "failed"
    state.handoff_error = result.error
    state.updated_at = time.time()
    return "handoff_failed", state.purchase_request or {}


def _is_tenant_sales_mode(mode: str) -> bool:
    return mode == ChatMode.TENANT_SALES.value


def _prefer_vietnamese_response(req: "ChatReq", mode: str) -> bool:
    channel = (req.channel or "").strip().lower()
    return is_vietnamese_text(req.message) or channel in {"messenger", "telegram", "web"}


def _mode_default_stage(mode: str) -> str:
    if mode == ChatMode.GENERAL_COMPARE.value:
        return "compare"
    if mode == ChatMode.MARKET_PRICE.value:
        return "price_reference"
    return "discover"


def _build_system_prompt(mode: str, sales_prefix: str, custom_system_prompt: Optional[str]) -> str:
    base_prompt = custom_system_prompt or DEFAULT_SYSTEM
    mode_prompt = mode_system_instruction(mode)
    parts = [mode_prompt]
    if sales_prefix:
        parts.append(sales_prefix)
    parts.append(base_prompt)
    return "\n".join(part.strip() for part in parts if part and part.strip())


def _build_debug_trace(
    *,
    mode: str,
    stage: Optional[str],
    slots: Optional[Dict[str, Any]],
    retrieved_docs: int = 0,
    context: str = "",
    retrieval_mode: str = "",
    data_provider: str = "none",
    internal_candidates: int = 0,
    external_price_refs: int = 0,
    price_provider: str = "none",
    used_mock_price_data: bool = False,
) -> Dict[str, Any]:
    return {
        "mode": mode,
        "stage": stage,
        "slots": dict(slots or {}),
        "retrieved_docs": retrieved_docs,
        "context_chars": len(context or ""),
        "retrieval_mode": retrieval_mode,
        "data_provider": data_provider,
        "internal_candidates": internal_candidates,
        "external_price_refs": external_price_refs,
        "price_provider": price_provider,
        "used_mock_price_data": used_mock_price_data,
    }


def _messages_to_plain_prompt(messages: List[Dict[str, Any]]) -> str:
    parts = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        parts.append(f"{role.upper()}:\n{content}")
    return "\n\n".join(parts)


def _extract_candidate_price_vnd(message: str) -> Optional[float]:
    text = (message or "").lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(trieu|triệu|m|million)", text)
    if match:
        return float(match.group(1)) * 1_000_000

    match = re.search(r"(\d{6,})", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _extract_price_values_from_context(context: str) -> List[float]:
    values: List[float] = []
    for match in re.finditer(r'"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)', context or ""):
        try:
            values.append(float(match.group(1)))
        except ValueError:
            continue
    return values


def _format_vnd_range(min_price: float, max_price: float) -> str:
    min_m = min_price / 1_000_000
    max_m = max_price / 1_000_000
    if min_price == max_price:
        return f"khoảng {min_m:.1f} triệu VND"
    return f"khoảng {min_m:.1f}-{max_m:.1f} triệu VND"


def _format_vnd_value(price: float) -> str:
    if price >= 1_000_000:
        return f"{price / 1_000_000:.1f} triệu VND"
    return f"{price:,.0f} VND"


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D")


def _market_price_subject(user_message: str, price_refs: List[Any]) -> str:
    message = user_message or ""
    code_match = re.search(r"\b[A-Z]{2,}[A-Z0-9-]*\d+[A-Z0-9-]*\b", message.upper())
    if code_match:
        return code_match.group(0)

    plain = _strip_accents(message).lower()
    if "sofa" in plain and "go soi" in plain:
        return "sofa gỗ sồi"
    if "sofa" in plain:
        return "sofa"
    if "ban an" in plain:
        return "bàn ăn"
    if "tu quan ao" in plain or "tu ao" in plain:
        return "tủ quần áo"
    if "giuong" in plain:
        return "giường"

    return next(
        (
            str(value)
            for ref in price_refs
            for value in (getattr(ref, "product_id", None), getattr(ref, "name", None))
            if value
        ),
        "sản phẩm",
    )


def _build_market_price_reply(
    user_message: str,
    price_refs: List[Any],
    debug_trace: Dict[str, Any],
) -> str:
    price_values = [
        float(getattr(ref, "price"))
        for ref in price_refs
        if getattr(ref, "price", None) is not None
    ]
    if not price_values:
        return (
            "Chưa có đủ dữ liệu giá có cấu trúc để ước lượng khoảng giá hoặc phát hiện bất thường. "
            "Bạn có thể gửi thêm tên sản phẩm, mã sản phẩm, vật liệu, kích thước hoặc một mức giá cụ thể "
            "để mình phân tích sát hơn."
        )

    min_price = min(price_values)
    max_price = max(price_values)
    candidate_price = _extract_candidate_price_vnd(user_message)
    product_label = _market_price_subject(user_message, price_refs)

    if candidate_price is None:
        judgement = (
            "Nếu chưa có mức giá cụ thể để đối chiếu, có thể dùng khoảng này làm mốc tham khảo ban đầu."
        )
    elif candidate_price < min_price:
        judgement = f"Mức {_format_vnd_value(candidate_price)} đang thấp hơn khoảng tham chiếu."
    elif candidate_price > max_price:
        judgement = f"Mức {_format_vnd_value(candidate_price)} đang cao hơn khoảng tham chiếu."
    else:
        judgement = f"Mức {_format_vnd_value(candidate_price)} đang nằm trong khoảng tham chiếu."

    return (
        f"## Tham khảo giá {product_label}\n"
        f"Khoảng giá tham khảo: {_format_vnd_range(min_price, max_price)}.\n"
        f"Dữ liệu đối chiếu: {len(price_values)} mẫu tham chiếu hiện có.\n"
        f"Nhận xét: {judgement}\n"
        "Lưu ý: Khoảng giá có thể thay đổi theo kích thước, chất liệu, độ mới, thương hiệu và chi phí vận chuyển/lắp đặt."
    )


def _stub_generate(messages: List[Dict[str, Any]], context: str, debug_trace: Dict[str, Any]) -> str:
    prompt_text = _messages_to_plain_prompt(messages)
    prompt_has_context = bool(context and context in prompt_text)
    context_preview = " ".join((context or "NO_CONTEXT").split())[:260]
    mode = debug_trace.get("mode")
    data_provider = debug_trace.get("data_provider") or "none"
    price_provider = debug_trace.get("price_provider") or "none"
    price_values = _extract_price_values_from_context(context)
    common = (
        f"mode={mode} "
        f"stage={debug_trace.get('stage')} "
        f"retrieved_docs={debug_trace.get('retrieved_docs')} "
        f"context_chars={debug_trace.get('context_chars')} "
        f"retrieval_mode={debug_trace.get('retrieval_mode')} "
        f"prompt_has_context={prompt_has_context} "
        f"context_preview={context_preview}"
    )

    if mode == ChatMode.GENERAL_COMPARE.value:
        options = [
            "1. SFG041 — giá: chưa có dữ liệu; chất liệu: gỗ sồi; dùng cho căn hộ nhỏ.",
            "2. SFG040 — giá: chưa có dữ liệu; chất liệu: chưa có dữ liệu; phong cách tối giản.",
            "3. SFG039 — giá: chưa có dữ liệu; chất liệu: gỗ tự nhiên; hợp không gian rộng.",
        ]
        return (
            "[stub][general_compare]\n"
            f"Nguồn dữ liệu: {data_provider}. No purchase request.\n"
            "Tiêu chí so sánh: giá, chất liệu, kích thước/phong cách/mục đích dùng.\n"
            "Các lựa chọn so sánh:\n"
            + "\n".join(options)
            + "\nKết luận trung lập: SFG041 hợp không gian nhỏ; SFG039 hợp không gian rộng; các thông số thiếu được ghi là 'chưa có dữ liệu'.\n"
            f"{common}"
        )

    if mode == ChatMode.MARKET_PRICE.value:
        candidate_price = _extract_candidate_price_vnd(messages[-1].get("content", "") if messages else "")
        if price_values:
            min_price = min(price_values)
            max_price = max(price_values)
            range_text = _format_vnd_range(min_price, max_price)
            if candidate_price is None:
                judgement = "chưa có giá người dùng cung cấp để nhận xét cao/thấp/bình thường."
            elif candidate_price < min_price:
                judgement = "mức giá người dùng đưa ra đang thấp hơn khoảng tham chiếu."
            elif candidate_price > max_price:
                judgement = "mức giá người dùng đưa ra đang cao hơn khoảng tham chiếu."
            else:
                judgement = "mức giá người dùng đưa ra đang trong khoảng tham chiếu."
        else:
            range_text = "chưa có dữ liệu do thiếu nguồn giá có cấu trúc."
            judgement = "chưa đủ dữ liệu để kết luận giá cao/thấp/bình thường."

        warnings = []
        if debug_trace.get("used_mock_price_data"):
            warnings.append("dữ liệu hiện tại là mock/demo, không phải giá thị trường xác nhận")
        if not debug_trace.get("external_price_refs"):
            warnings.append("chưa đủ nguồn giá để kết luận chắc chắn")
        if not warnings:
            warnings.append("không có cảnh báo bổ sung")

        return (
            "[stub][market_price]\n"
            f"Nguồn dữ liệu dùng: {data_provider} (price_provider={price_provider}).\n"
            f"Khoảng giá tham khảo: {range_text}\n"
            f"Nhận xét mức giá: {judgement}\n"
            f"Cảnh báo dữ liệu: {'; '.join(warnings)}.\n"
            "Không gợi ý mua sản phẩm cụ thể. No purchase request.\n"
            f"{common}"
        )

    return (
        "[stub][tenant_sales] "
        f"{common}"
    )


def get_kb_for_mode(retrieval_mode: str):
    if retrieval_mode == KB_RETRIEVAL_MODE:
        return KB
    if not KB_DIR:
        return KB
    if retrieval_mode not in KB_BY_MODE:
        KB_BY_MODE[retrieval_mode] = load_retrieval_kb(KB_DIR, mode=retrieval_mode)
    return KB_BY_MODE[retrieval_mode]


def _safe_empty_cuda_cache() -> None:
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as exc:
        print(f"[local_pipeline_cache] cuda_cleanup_skipped class={exc.__class__.__name__}")


def _unload_pipeline_entry(entry: PipelineCacheEntry) -> None:
    try:
        pipe = entry.pipe
        entry.pipe = None
        del pipe
    except Exception as exc:
        print(f"[local_pipeline_cache] pipeline_ref_cleanup_skipped class={exc.__class__.__name__}")
    gc.collect()
    _safe_empty_cuda_cache()


def _log_pipeline_unload(
    *,
    reason: str,
    idle_seconds: float,
    cache_size: int,
    unloaded: bool,
) -> None:
    print(
        "[local_pipeline_cache] "
        f"local_pipeline_evicted=true reason={reason} "
        f"local_pipeline_idle_seconds={idle_seconds:.3f} "
        f"local_pipeline_unloaded={str(unloaded).lower()} "
        f"local_pipeline_cache_size={cache_size}"
    )


def _evict_pipeline_entries(
    entries: List[Tuple[PipelineCacheEntry, float]],
    *,
    reason: str,
    cache_size: int,
) -> None:
    for entry, idle_seconds in entries:
        unloaded = False
        try:
            _unload_pipeline_entry(entry)
            unloaded = True
        finally:
            _log_pipeline_unload(
                reason=reason,
                idle_seconds=idle_seconds,
                cache_size=cache_size,
                unloaded=unloaded,
            )


def _evict_over_capacity_locked(now: float, protected_key: PipelineCacheKey) -> List[Tuple[PipelineCacheEntry, float]]:
    overflow = len(PIPE_CACHE) - LOCAL_PIPELINE_MAX_CACHE
    if overflow <= 0:
        return []

    candidates = [
        (key, entry)
        for key, entry in PIPE_CACHE.items()
        if key != protected_key
    ]
    candidates.sort(key=lambda item: item[1].last_used)

    evicted: List[Tuple[PipelineCacheEntry, float]] = []
    for key, entry in candidates[:overflow]:
        removed = PIPE_CACHE.pop(key, None)
        if removed is not None:
            evicted.append((removed, max(0.0, now - removed.last_used)))
    return evicted


def _cleanup_idle_pipelines_once(now: Optional[float] = None) -> int:
    now = time.monotonic() if now is None else now
    evicted: List[Tuple[PipelineCacheEntry, float]] = []
    with PIPE_CACHE_LOCK:
        for key, entry in list(PIPE_CACHE.items()):
            idle_seconds = max(0.0, now - entry.last_used)
            if idle_seconds > LOCAL_PIPELINE_IDLE_TTL_SECONDS:
                removed = PIPE_CACHE.pop(key, None)
                if removed is not None:
                    evicted.append((removed, idle_seconds))
        cache_size = len(PIPE_CACHE)

    _evict_pipeline_entries(evicted, reason="idle_ttl", cache_size=cache_size)
    return len(evicted)


def _start_pipeline_cleanup_thread() -> None:
    global PIPE_CACHE_CLEANUP_STARTED
    with PIPE_CACHE_CLEANUP_START_LOCK:
        if PIPE_CACHE_CLEANUP_STARTED:
            return
        PIPE_CACHE_CLEANUP_STARTED = True

    def run() -> None:
        while True:
            time.sleep(LOCAL_PIPELINE_CLEANUP_INTERVAL_SECONDS)
            try:
                _cleanup_idle_pipelines_once()
            except Exception as exc:
                print(f"[local_pipeline_cache] cleanup_failed class={exc.__class__.__name__}")

    threading.Thread(target=run, daemon=True, name="local-pipeline-cache-cleanup").start()
    with PIPE_CACHE_LOCK:
        cache_size = len(PIPE_CACHE)
    print(
        "[local_pipeline_cache] cleanup_started "
        f"local_pipeline_cache_size={cache_size} "
        f"local_pipeline_max_cache={LOCAL_PIPELINE_MAX_CACHE} "
        f"local_pipeline_idle_ttl_seconds={LOCAL_PIPELINE_IDLE_TTL_SECONDS} "
        f"local_pipeline_cleanup_interval_seconds={LOCAL_PIPELINE_CLEANUP_INTERVAL_SECONDS}"
    )


def get_or_create_pipe(base_model: str, adapter: Optional[str], tokenizer_path: Optional[str]):
    from .model_loader import get_pipeline

    key = (base_model, adapter, tokenizer_path)
    evicted: List[Tuple[PipelineCacheEntry, float]] = []
    with PIPE_CACHE_LOCK:
        now = time.monotonic()
        entry = PIPE_CACHE.get(key)
        if entry is None:
            pipe = get_pipeline(base=base_model, adapter=adapter, tokenizer_path=tokenizer_path)
            now = time.monotonic()
            entry = PipelineCacheEntry(
                pipe=pipe,
                last_used=now,
                key=key,
                base_model=base_model,
                adapter=adapter,
                tokenizer_path=tokenizer_path,
            )
            PIPE_CACHE[key] = entry
            evicted = _evict_over_capacity_locked(now, protected_key=key)
        else:
            entry.last_used = now
        pipe = entry.pipe
        cache_size = len(PIPE_CACHE)

    if evicted:
        _evict_pipeline_entries(evicted, reason="max_cache_lru", cache_size=cache_size)

    print(f"[local_pipeline_cache] local_pipeline_cache_size={cache_size}")
    return pipe


@app.on_event("startup")
def _warmup():
    _start_pipeline_cleanup_thread()

    if _is_test_mode():
        _set_ready(True, None)
        print("[warmup] test mode ready=True")
        return

    if not LOCAL_MODEL_ENABLED:
        _set_ready(True, None)
        print("[warmup] local model disabled; skipping local model warmup")
        return

    if not BASE_MODEL_DEFAULT:
        _set_ready(False, "LOCAL_MODEL_ENABLED=true but BASE_MODEL is not set")
        print("[warmup] local model enabled but BASE_MODEL is not set")
        return
    if _is_disabled_local_model(BASE_MODEL_DEFAULT):
        _set_ready(False, f"Local model is disabled: {BASE_MODEL_DEFAULT}")
        print(f"[warmup] local model disabled by policy: {BASE_MODEL_DEFAULT}")
        return

    # Warmup should build at least one local pipeline when local model mode is explicitly enabled.
    def run():
        try:
            get_or_create_pipe(BASE_MODEL_DEFAULT, None, TOKENIZER_DEFAULT)
            _set_ready(True, None)
            print("[warmup] ready=True")
        except Exception as e:
            _set_ready(False, str(e))
            print("[warmup] failed:", e)

    _set_ready(False, None)
    threading.Thread(target=run, daemon=True).start()


@app.get("/healthz")
def healthz():
    # IMPORTANT: backend should only treat healthy when ready=True
    with READY_LOCK:
        ready = READY
        err = READY_ERR
    with PIPE_CACHE_LOCK:
        cached_pipelines = len(PIPE_CACHE)
    return {
        "status": "ready" if ready else "loading",
        "ready": ready,
        "error": err,
        "cached_pipelines": cached_pipelines,
        "local_pipeline_max_cache": LOCAL_PIPELINE_MAX_CACHE,
        "local_pipeline_idle_ttl_seconds": LOCAL_PIPELINE_IDLE_TTL_SECONDS,
        "local_pipeline_cleanup_interval_seconds": LOCAL_PIPELINE_CLEANUP_INTERVAL_SECONDS,
        "local_model_enabled": LOCAL_MODEL_ENABLED,
        "base_model_configured": bool(BASE_MODEL_DEFAULT),
        "fallback_to_local_enabled": FALLBACK_TO_LOCAL_ENABLED,
        "kb_dir": KB_DIR,
        "kb_loaded": KB is not None,
        "retrieval_mode": KB_RETRIEVAL_MODE,
        "test_mode": _is_test_mode(),
    }


class FeedbackReq(BaseModel):
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = None
    channel: Optional[str] = None
    question: str
    answer: str
    is_correct: bool
    note: Optional[str] = ""


class StateResetReq(BaseModel):
    tenant_id: Optional[str] = None
    conversation_id: str


@app.post("/feedback")
def feedback(req: FeedbackReq):
    log_feedback(req.model_dump())
    return {"ok": True}


@app.post("/state/reset")
def reset_runtime_state(req: StateResetReq):
    reset_state(req.conversation_id)
    _clear_sales_state(req.tenant_id, req.conversation_id)
    return {"ok": True, "conversation_id": req.conversation_id}


@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq):
    cfg = req.gen

    base_model = cfg.base_model or BASE_MODEL_DEFAULT
    adapter = None
    tokenizer_path = cfg.tokenizer_path or TOKENIZER_DEFAULT
    provider = _select_provider(cfg)
    try:
        answer_mode = _resolve_answer_mode(cfg)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        sales_mode = _resolve_sales_mode(cfg)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        mode = normalize_chat_mode(cfg.mode, req.message)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        retrieval_mode = normalize_retrieval_mode(cfg.retrieval_mode or KB_RETRIEVAL_MODE)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Resolve max_tokens based on provider
    base_max_tokens = cfg.max_new_tokens or MAX_NEW_TOKENS_DEFAULT
    if provider == "claude":
        max_new_tokens = cfg.max_new_tokens or CLAUDE_MAX_NEW_TOKENS
    elif provider == "local":
        max_new_tokens = cfg.max_new_tokens or LOCAL_FALLBACK_MAX_TOKENS if not _is_test_mode() else base_max_tokens
    else:
        max_new_tokens = base_max_tokens
    temperature = cfg.temperature or TEMPERATURE_DEFAULT
    top_p = cfg.top_p or TOP_P_DEFAULT
    top_k = int(cfg.top_k) if cfg.top_k is not None else TOP_K_DEFAULT
    retrieval_top_k = int(cfg.retrieval_top_k) if cfg.retrieval_top_k is not None else RETRIEVAL_TOP_K_DEFAULT

    # Defense-in-depth: local model requests are opt-in only and must wait for warmup.
    # Claude API does not need local model ready.
    if provider == "local":
        if not LOCAL_MODEL_ENABLED:
            raise HTTPException(
                status_code=422,
                detail="Local model provider is disabled. Set LOCAL_MODEL_ENABLED=true and BASE_MODEL explicitly to use it.",
            )
        if not base_model:
            raise HTTPException(
                status_code=422,
                detail="Local model provider requires BASE_MODEL or gen.base_model.",
            )
        if _is_disabled_local_model(base_model):
            raise HTTPException(
                status_code=422,
                detail=f"Local model is disabled by policy: {base_model}",
            )
        with READY_LOCK:
            if not READY:
                raise HTTPException(status_code=503, detail="Model is still loading")

    # Debug log - write to stderr to ensure visibility
    import sys
    print(
        f"[SERVER DEBUG] generator_provider={provider}, mode={mode}, "
        f"base_model={base_model}, adapter={adapter or '-'}, api_model={cfg.api_model or '-'}",
        file=sys.stderr,
    )

    # Ensure conversation_id exists for stateful flow
    conv_id = req.conversation_id or "anon"
    sales_state: Optional[SalesConversationState] = None
    sales_result: Optional[Dict[str, Any]] = None
    sales_draft: Optional[Dict[str, Any]] = None
    sales_action_taken = "none"
    sales_enabled = sales_mode in {"shadow", "active"}
    sales_state_persistent = _sales_state_is_persistent(req.conversation_id)
    sales_state_warning = None if sales_state_persistent else "missing_conversation_id_ephemeral_state"

    # =========================================================
    # (NEW) RESET COMMAND: /reset | reset | new scenario
    # Put it BEFORE RULE layer so it always works.
    # =========================================================
    msg_norm = (req.message or "").strip().lower()
    if msg_norm in {"/reset", "reset", "/end", "end", "new scenario"}:
        if conv_id:
            try:
                reset_state(conv_id)
            except Exception:
                pass
        if sales_enabled:
            _clear_sales_state(req.tenant_id, req.conversation_id)

        debug_trace = _build_debug_trace(
            mode=mode,
            stage="reset",
            slots={},
            retrieval_mode=retrieval_mode,
        )
        if sales_enabled:
            debug_trace.update(_sales_debug_payload(
                sales_mode,
                None,
                None,
                "none",
                persistent=sales_state_persistent,
                state_warning=sales_state_warning,
            ))
        log_event({
            "event": "reset",
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "debug": debug_trace,
        })

        return ChatResp(
            reply="Mình đã làm mới cuộc trò chuyện. Bạn muốn mình tư vấn sản phẩm nào ạ?",
            latency_ms=0,
            model="system",
            adapter=adapter,
            debug=debug_trace,
        )

    if sales_enabled:
        previous_purchase_status = None
        sales_state = _load_sales_state(req.tenant_id, req.conversation_id)
        previous_purchase_status = _purchase_request_status(sales_state)
        sales_state.tenant_id = req.tenant_id
        sales_state.conversation_id = req.conversation_id
        confirmation_slots = extract_sales_slots(req.message)
        confirmation_result = None
        if sales_mode == "active":
            if _is_pending_draft_update(sales_state, confirmation_slots):
                confirmation_result = _apply_pending_draft_update(
                    sales_state,
                    req.message,
                    confirmation_slots,
                )
            else:
                confirmation_result = _handle_pending_confirmation(
                    sales_state,
                    confirmation_slots.get("confirmation_intent"),
                )
        if confirmation_result is not None:
            sales_action_taken, sales_draft = confirmation_result
            sales_result = {
                "slots": confirmation_slots,
                "resolved_product": None,
            }
            _save_sales_state(sales_state)
            if sales_mode == "active":
                debug_trace = _build_debug_trace(
                    mode=mode,
                    stage=_mode_default_stage(mode),
                    slots={},
                    retrieval_mode=retrieval_mode,
                )
                debug_trace.update(_sales_debug_payload(
                    sales_mode,
                    sales_state,
                    sales_result,
                    sales_action_taken,
                    persistent=sales_state_persistent,
                    state_warning=sales_state_warning,
                ))
                reply = render_sales_response(sales_action_taken, sales_draft, sales_state)
                try:
                    save_turn(conv_id, req.message, reply[:1200])
                except Exception:
                    pass
                return ChatResp(
                    reply=reply[:1200],
                    latency_ms=0,
                    model="sales-template",
                    adapter=None,
                    trigger_purchase_request=False,
                    debug=debug_trace,
                )
        sales_result = apply_message_to_state(sales_state, req.message)
        sales_slots_for_action = sales_result.get("slots") or {}
        sales_intents_for_action = sales_slots_for_action.get("intents") or []
        scored_purchase = score_purchase_intent(
            sales_slots_for_action,
            has_selected_product=bool(sales_state.selected_products),
            has_contact=bool(sales_state.contact),
            has_address=bool(sales_state.slots.get("address") or sales_state.slots.get("location") or sales_state.slots.get("delivery_area")),
        )
        sales_state.slots["purchase_intent_score"] = scored_purchase.score
        sales_state.slots["purchase_intent_signals"] = scored_purchase.signals
        can_create_scored_draft = should_create_purchase_request_draft(
            sales_slots_for_action,
            has_selected_product=bool(sales_state.selected_products),
            has_contact=bool(sales_state.contact),
        )
        should_build_sales_draft = (
            "cancel" in sales_intents_for_action
            or "handoff_request" in sales_intents_for_action
            or "purchase_intent" in sales_intents_for_action
            or can_create_scored_draft
            or (
                "contact_provided" in sales_intents_for_action
                and previous_purchase_status in {"needs_contact", "draft"}
            )
        )
        if should_build_sales_draft:
            sales_draft = build_purchase_request_draft(sales_state, req.message)
            if (sales_draft or {}).get("status") == "draft":
                event_type = "draft_created" if previous_purchase_status != "draft" else "draft_updated"
                _ensure_durable_pending_request(sales_state, sales_draft, event_type=event_type)
        # Phase 6C: resolve pending_sku_ref from KB BEFORE sales action decision
        pending_sku = sales_state.slots.get("pending_sku_ref")
        if pending_sku and not sales_state.selected_products:
            sku_resolved = False
            sku_kb = get_kb_for_mode(retrieval_mode)
            if sku_kb is not None:
                sku_hits = search_hits(sku_kb, pending_sku, k=5, tenant_id=req.tenant_id)
                if sku_hits:
                    _resolve_sku_to_selected_product(
                        sales_state, sku_hits, sku_kb,
                        pending_sku, req.message, req.tenant_id,
                        retrieval_mode,
                    )
                    if sales_state.selected_products:
                        sku_resolved = True
                        sales_state.slots.pop("pending_sku_ref", None)
            if sku_resolved:
                # Rebuild draft to reflect newly resolved selected_product
                sales_draft = build_purchase_request_draft(sales_state, req.message)
            # If not resolved: keep pending_sku_ref, do NOT create synthetic product.
            # _sales_action_from_state will see purchase_intent + category -> ask_product.
        sales_action_taken = _sales_action_from_state(sales_state, sales_result, sales_draft)
        _save_sales_state(sales_state)
        if sales_mode == "active" and sales_action_taken != "none":
            debug_trace = _build_debug_trace(
                mode=mode,
                stage=_mode_default_stage(mode),
                slots={},
                retrieval_mode=retrieval_mode,
            )
            debug_trace.update(_sales_debug_payload(
                sales_mode,
                sales_state,
                sales_result,
                sales_action_taken,
                persistent=sales_state_persistent,
                state_warning=sales_state_warning,
            ))
            reply = render_sales_response(sales_action_taken, sales_draft, sales_state)
            try:
                save_turn(conv_id, req.message, reply[:1200])
            except Exception:
                pass
            return ChatResp(
                reply=reply[:1200],
                latency_ms=0,
                model="sales-template",
                adapter=None,
                trigger_purchase_request=False,
                debug=debug_trace,
            )

    # ---- RULE layer (guardrails) ----
    rr = rule_reply(req.message)
    if rr:
        st_for_rule = get_state(conv_id)
        debug_trace = _build_debug_trace(
            mode=mode,
            stage=getattr(st_for_rule, "stage", None),
            slots=getattr(st_for_rule, "slots", {}),
            retrieval_mode=retrieval_mode,
        )
        if sales_enabled:
            debug_trace.update(_sales_debug_payload(
                sales_mode,
                sales_state,
                sales_result,
                sales_action_taken,
                persistent=sales_state_persistent,
                state_warning=sales_state_warning,
            ))
        log_event({
            "event": "rule_hit",
            "rule_type": rr["type"],
            "question": req.message,
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "debug": debug_trace,
        })
        # Save turn (optional but useful for audit)
        try:
            save_turn(conv_id, req.message, rr["reply"])
        except Exception:
            pass
        return ChatResp(reply=rr["reply"], latency_ms=0, model="rule", adapter=adapter, debug=debug_trace)

    # --- SALES FLOW: state/slots/stage (AFTER RULE layer) ---
    st = get_state(conv_id)

    # Default values for lead capture trigger (will be updated below)
    trigger_purchase_request = False
    captured_phone = None
    captured_name = None
    stage_for_debug = getattr(st, "stage", _mode_default_stage(mode))
    slots_for_debug: Dict[str, Any] = dict(getattr(st, "slots", {}) or {})

    # update slots from this user message
    try:
        # Capture current stage BEFORE transition (for intent context and trigger)
        old_stage = getattr(st, "stage", "discover")

        if not _is_tenant_sales_mode(mode):
            stage_for_debug = _mode_default_stage(mode)
            try:
                slots_for_debug = extract_slots(req.message)
            except Exception:
                slots_for_debug = {}
        else:
            # Original tenant sales flow
            new_slots = extract_slots(req.message)
            _detect_and_track_preference_changes(st.slots, new_slots)
            _handle_topic_change(st.slots, new_slots, mode)
            if new_slots:
                st.slots.update(new_slots)
            st.stage = next_stage(old_stage, st.slots, req.message)

        # ---- Intent detection for robust lead capture ----
        # Use old_stage for context (stage that was active when user sent this message)
        if _is_tenant_sales_mode(mode):
            user_intent = detect_intent(req.message, old_stage)
            trigger_purchase_request = (old_stage == "close" and user_intent == "confirm")
            # For sales flow, phone/name are not extracted here; they come from transcript in Java
            captured_phone = st.slots.get("captured_phone")
            captured_name = st.slots.get("captured_name")
            stage_for_debug = getattr(st, "stage", stage_for_debug)
            slots_for_debug = dict(getattr(st, "slots", {}) or {})
    except Exception:
        # Don't break chat if slot extractor fails
        pass

    pipe = get_or_create_pipe(base_model, adapter, tokenizer_path) if provider == "local" and answer_mode != "template" else None

    # ---- RAG context from KB + optional structured providers ----
    retrieval_hits = []
    allow_rag = False
    try:
        allow_rag = True if not _is_tenant_sales_mode(mode) else should_allow_retrieval(
            req.message,
            stage_for_debug,
            slots_for_debug,
        )
    except Exception:
        allow_rag = False

    active_kb = get_kb_for_mode(retrieval_mode)
    # Phase 8: build accumulated search query from sales state for tenant_sales retrieval
    _tenant_sales_requested_cat = None
    _tenant_sales_search_query = req.message
    if sales_enabled and _is_tenant_sales_mode(mode) and sales_state and sales_state.slots:
        state_slots = sales_state.slots
        cat = state_slots.get("product_category") or state_slots.get("product_type") or ""
        room = state_slots.get("room") or ""
        budget = state_slots.get("budget_text") or state_slots.get("budget_usd") or ""
        if cat:
            raw = cat
            _tenant_sales_requested_cat = cat
        if cat or room or budget:
            parts = [cat, room, budget]
            accumulated = " ".join(p for p in parts if p).strip()
            if accumulated:
                _tenant_sales_search_query = accumulated
    if active_kb is not None and allow_rag:
        retrieval_hits = search_hits(
            active_kb,
            _tenant_sales_search_query,
            k=max(1, retrieval_top_k),
            tenant_id=req.tenant_id,
        )

    if _tenant_sales_requested_cat and retrieval_hits:
        filtered_count = len(retrieval_hits)
        retrieval_hits = filter_by_category(retrieval_hits, _tenant_sales_requested_cat)
        filtered_count -= len(retrieval_hits)
        if filtered_count:
            retrieval_hits = search_hits(
                active_kb, req.message,
                k=max(len(retrieval_hits) + filtered_count + 5, 20),
                tenant_id=req.tenant_id,
            )
            retrieval_hits = filter_by_category(retrieval_hits, _tenant_sales_requested_cat)

    # Phase 6C: resolve pending_sku from KB hits -> real selected_product
    if sales_state and _is_tenant_sales_mode(mode) and retrieval_hits:
        pending_sku = sales_state.slots.get("pending_sku_ref") or (
            (sales_result.get("slots") or {}).get("product_sku_ref") if sales_result else None)
        if pending_sku:
            need_real = not sales_state.selected_products
            if not need_real:
                need_real = all(p.get("pid") == "SKU" for p in sales_state.selected_products)
            if need_real:
                _resolve_sku_to_selected_product(
                    sales_state, retrieval_hits, active_kb,
                    pending_sku, req.message, req.tenant_id,
                    retrieval_mode,
                )
                # KB resolve succeeded -> clear pending_sku
                if any(p.get("pid") != "SKU" for p in sales_state.selected_products):
                    sales_state.slots.pop("pending_sku_ref", None)
        # KB resolve failed -> keep pending_sku, never create synthetic selected_product
        # The early path (line 1339) already handled fallback; this block is a no-op.
        pass

    internal_candidates = []
    price_refs = []
    provider_context_parts = []
    data_provider = "retrieval" if retrieval_hits else "none"
    price_provider_name = getattr(PRICE_PROVIDER, "provider_name", "none")
    used_mock_price_data = False

    if mode == ChatMode.GENERAL_COMPARE.value:
        # 1. Call backend general products search
        backend_items = []
        try:
            backend_items = BACKEND_CATALOG_PROVIDER.search_candidates(
                req.message,
                limit=max(1, retrieval_top_k),
            )
        except Exception as e:
            _logger.warning("BackendGeneralCatalogProvider failed: %s", e)

        if backend_items:
            data_provider = "backend_general_catalog"
            provider_context_parts.append(
                "BACKEND GENERAL CATALOG RESULTS "
                "(ranked by relevance across all public sources):\n"
                + format_backend_catalog_items(backend_items)
            )
        else:
            # 2. Fallback: use internal catalog provider (file-based)
            try:
                internal_candidates = INTERNAL_CATALOG_PROVIDER.search_candidates(
                    req.message,
                    limit=max(1, retrieval_top_k),
                )
            except Exception:
                internal_candidates = []
            if internal_candidates:
                data_provider = getattr(INTERNAL_CATALOG_PROVIDER, "provider_name", "internal_catalog")
                provider_context_parts.append(
                    "STRUCTURED INTERNAL CATALOG CANDIDATES "
                    "(fields may be null; use only provided values):\n"
                    + format_catalog_candidates(internal_candidates)
                )

    market_price_insight = None
    if mode == ChatMode.MARKET_PRICE.value:
        try:
            market_price_insight = BACKEND_MARKET_PRICE_PROVIDER.get_insight(req.message)
        except Exception as e:
            _logger.warning("BackendMarketPriceInsightProvider failed: %s", e)
            market_price_insight = None

        if market_price_insight is not None:
            data_provider = "backend_market_price_insight"
            provider_context_parts.append(
                "MARKET PRICE INSIGHT FROM BACKEND (general_products aggregate):\n"
                + json.dumps(market_price_insight.stats, ensure_ascii=False)
            )
        else:
            # Fallback: old price provider
            try:
                price_refs = PRICE_PROVIDER.get_price_references(
                    req.message,
                    limit=max(1, retrieval_top_k),
                )
            except Exception:
                price_refs = []
            used_mock_price_data = any(getattr(ref, "is_mock", False) for ref in price_refs)
            if price_refs:
                data_provider = price_provider_name
                provider_context_parts.append(
                    "PRICE REFERENCES FROM EXPLICIT PRICE PROVIDER "
                    "(mock/demo rows are not real market catalog data):\n"
                    + format_price_references(price_refs)
                )

    retrieval_context = format_context(retrieval_hits)
    if provider_context_parts and retrieval_context:
        context = "\n\n".join(provider_context_parts + ["RETRIEVED KB CONTEXT:\n" + retrieval_context])
    elif provider_context_parts:
        context = "\n\n".join(provider_context_parts)
    else:
        context = retrieval_context

    if sales_enabled and sales_state is not None and retrieval_hits:
        update_recommended_products(sales_state, retrieval_hits)
        _save_sales_state(sales_state)

    debug_trace = _build_debug_trace(
        mode=mode,
        stage=stage_for_debug,
        slots=slots_for_debug,
        retrieved_docs=len(retrieval_hits),
        context=context,
        retrieval_mode=retrieval_mode,
        data_provider=data_provider,
        internal_candidates=len(internal_candidates),
        external_price_refs=len(price_refs),
        price_provider=price_provider_name,
        used_mock_price_data=used_mock_price_data,
    )
    debug_trace.update({
        "answer_mode": answer_mode,
        "template_renderer": answer_mode == "template",
        "retrieval_count": len(retrieval_hits),
    })
    if sales_enabled:
        debug_trace.update(_sales_debug_payload(
            sales_mode,
            sales_state,
            sales_result,
            sales_action_taken,
            persistent=sales_state_persistent,
            state_warning=sales_state_warning,
        ))
    log_retrieval_debug({
        **debug_trace,
        **summarize_retrieval_debug(retrieval_hits, context),
        "question": req.message,
        "channel": req.channel,
        "conversation_id": conv_id,
        "tenant_id": req.tenant_id,
        "allow_rag": allow_rag,
    })

    if answer_mode == "template":
        t0 = time.time()
        if mode == ChatMode.GENERAL_COMPARE.value and backend_items:
            resp = render_general_compare(req.message, backend_items)
        else:
            resp = render_product_answer(req.message, context)
        latency_ms = int((time.time() - t0) * 1000)
        debug_trace.update({
            "answer_mode": "template",
            "template_renderer": True,
            "retrieval_count": len(retrieval_hits),
        })
        if sales_enabled:
            debug_trace.update(_sales_debug_payload(
                sales_mode,
                sales_state,
                sales_result,
                sales_action_taken,
                persistent=sales_state_persistent,
                state_warning=sales_state_warning,
            ))
        log_event({
            "event": "chat",
            "question": req.message,
            "answer": resp[:1200],
            "latency_ms": latency_ms,
            "model": "product-template",
            "adapter": None,
            "provider": provider,
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "context_length": len(context),
            "kb_loaded": active_kb is not None,
            "sales_stage": stage_for_debug,
            "sales_slots": slots_for_debug,
            "debug": debug_trace,
        })
        try:
            save_turn(conv_id, req.message, resp)
        except Exception:
            pass
        if sales_enabled and sales_state is not None:
            _save_sales_state(sales_state)
        response_trigger_purchase_request = False if sales_enabled else (trigger_purchase_request if _is_tenant_sales_mode(mode) else False)
        return ChatResp(
            reply=resp[:1200],
            latency_ms=latency_ms,
            model="product-template",
            adapter=None,
            trigger_purchase_request=response_trigger_purchase_request,
            captured_phone=captured_phone if _is_tenant_sales_mode(mode) else None,
            captured_name=captured_name if _is_tenant_sales_mode(mode) else None,
            debug=debug_trace,
        )

    # ---- SIMILAR SUGGESTION (use KB hits) ----
    if _is_tenant_sales_mode(mode) and active_kb is not None and allow_rag and want_similar(req.message):
        similar_hits = retrieval_hits
        if len(similar_hits) < 8:
            similar_hits = search_hits(active_kb, req.message, k=8, tenant_id=req.tenant_id)
        if _tenant_sales_requested_cat:
            similar_hits = filter_by_category(similar_hits, _tenant_sales_requested_cat)
        items = top_similar_items(similar_hits, limit=3)

        if items:
            reply = (
                "Mình gợi ý một vài sản phẩm tương tự trong dữ liệu hiện có:\n" +
                "\n".join([f"- {t} ({u})" if u else f"- {t}" for t, u in items])
            )
        else:
            reply = "Mình chưa tìm thấy sản phẩm cùng loại phù hợp trong dữ liệu hiện có. Bạn có muốn nới điều kiện hoặc chọn nhóm sản phẩm khác không?"

        log_event({
            "event": "similar_suggestion",
            "question": req.message,
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "items": [{"title": t, "url": u} for t, u in items] if items else [],
            "debug": debug_trace,
        })

        # Save turn for stateful flow continuity
        try:
            save_turn(conv_id, req.message, reply[:1200])
        except Exception:
            pass
        if sales_enabled and sales_state is not None:
            _save_sales_state(sales_state)

        return ChatResp(
            reply=reply[:1200],
            latency_ms=0,
            model=base_model or "stub",
            adapter=adapter,
            debug=debug_trace,
        )

    # ---- SALES flow prefix inside system prompt ----
    sales_prefix = ""
    try:
        if _is_tenant_sales_mode(mode):
            sales_prefix = build_sales_prefix(stage_for_debug, slots_for_debug)
    except Exception:
        sales_prefix = ""

    sys_prompt = _build_system_prompt(mode, sales_prefix, cfg.system_prompt)
    if _prefer_vietnamese_response(req, mode):
        sys_prompt += (
            "\n\nLANGUAGE PREFERENCE:\n"
            "- Reply in Vietnamese by default for this tenant sales chat.\n"
            "- If the user writes a short greeting like 'hi' or 'hello', answer in Vietnamese and ask what furniture item they need.\n"
            "- Only switch to English if the user explicitly asks to use English."
        )

    t0 = time.time()
    messages = build_messages(
        req.message,
        req.history,
        sys_prompt,
        grounding_context=context if context else None,
    )

    if mode == ChatMode.MARKET_PRICE.value:
        if market_price_insight is not None:
            out = _market_price_insight_reply(req.message, market_price_insight)
        else:
            out = _market_price_reply(req.message, price_refs)
        response_model = "structured_price"
        response_adapter = None
    elif provider == "stub":
        out = _stub_generate(messages, context, debug_trace)
        response_model = "stub"
        response_adapter = None
    elif provider == "claude":
        # Claude is system-level provider: resolve from env only
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        api_model = os.getenv("CLAUDE_MODEL") or 'claude-sonnet-4-6'
        api_base_url = os.getenv("CLAUDE_API_BASE_URL") or 'https://api.anthropic.com'

        # Missing key is a safe error; do not fallback to request-level or hardcoded values
        if not api_key:
            out, claude_error_code, claude_error_preview = "", "missing_api_key", "System env ANTHROPIC_API_KEY or CLAUDE_API_KEY not set"
        else:
            out, claude_error_code, claude_error_preview = _call_claude_api(
                _messages_to_plain_prompt(messages),
                api_key,
                api_model,
                api_base_url,
                max_new_tokens,
                temperature,
                top_p,
            )

        if claude_error_code:
            debug_trace["claude_error"] = {
                "type": claude_error_code,
                "preview": claude_error_preview,
                "model": api_model,
                "base_url": api_base_url,
            }
        response_model = api_model
        response_adapter = None
    elif provider == "local":
        if pipe is None:
            pipe = get_or_create_pipe(base_model, adapter, tokenizer_path)
        prompt_text = pipe.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        out = pipe(
            prompt_text,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            no_repeat_ngram_size=3,
            repetition_penalty=1.15,
            pad_token_id=pipe.tokenizer.eos_token_id,
            eos_token_id=pipe.tokenizer.eos_token_id,
            return_full_text=False,
        )[0]["generated_text"]
        response_model = base_model
        response_adapter = adapter
    else:
        raise HTTPException(status_code=422, detail=f"Unsupported provider: {provider}")

    resp = out.strip() if out else ""
    if not resp and provider == "claude" and context:
        resp = render_product_answer(req.message, context)
        debug_trace["fallback_answer_mode"] = "product-template"
    if not resp:
        resp = "Xin lỗi, hệ thống đang gặp sự cố khi xử lý yêu cầu. Bạn thử lại giúp mình nhé."

    # Keep answers concise, but not too short for consultative flow
    if response_model != "structured_price":
        sentences = re.split(r'(?<=[.!?])\s+', resp)
        resp = " ".join(sentences[:6]).strip()

    NOT_FOUND = "I couldn’t find that in this store’s data."

    if provider != "stub":
        if _is_tenant_sales_mode(mode) and _prefer_vietnamese_response(req, mode) and ((not context) or (NOT_FOUND.lower() in resp.lower())):
            resp = (
                "Mình chưa có đủ dữ liệu từ kho tri thức của cửa hàng để trả lời thật chính xác. "
                "Bạn gửi giúp mình tên sản phẩm, mã sản phẩm hoặc nhu cầu cụ thể hơn nhé; "
                "mình cũng có thể chuyển cho nhân viên tư vấn nếu bạn muốn."
            )
        elif _is_tenant_sales_mode(mode) and ((not context) or (NOT_FOUND.lower() in resp.lower())):
            resp = (
                "Mình chưa đủ thông tin để tư vấn chính xác. Bạn cho mình biết thêm nhu cầu, ngân sách hoặc không gian sử dụng nhé."
            )
        elif mode == ChatMode.GENERAL_COMPARE.value and not context:
            resp = (
                "I do not have enough retrieved product data to compare at least three options reliably. "
                "Please share product names, links, or a tenant KB with comparable items; I will compare price, material, size/use, and style without guessing."
            )
    # --- SALES FLOW: close stage hard CTA (CONFIRM / CANCEL / no payment) ---
    if _is_tenant_sales_mode(mode) and getattr(st, "stage", None) == "close":
        resp = resp.strip()
        resp += (
            "\n\nNếu muốn gửi yêu cầu cho cửa hàng, bạn trả lời CONFIRM. "
            "Nếu muốn dừng, bạn trả lời CANCEL. "
            "Mình chưa xử lý thanh toán trực tiếp trong chat."
        )


    resp = _apply_grounding_guard(req.message, context, resp)

    # --- Output guardrail: if model slips into unverified facts, replace with safe fallback ---
    if BAD_FACTS.search(resp):
        resp = (
            "Mình chưa tìm thấy thông tin đủ chắc chắn trong dữ liệu hiện có. Bạn có thể mô tả cụ thể hơn nhu cầu được không?"
        )

    latency_ms = int((time.time() - t0) * 1000)
    if sales_enabled:
        debug_trace.update(_sales_debug_payload(
            sales_mode,
            sales_state,
            sales_result,
            sales_action_taken,
            persistent=sales_state_persistent,
            state_warning=sales_state_warning,
        ))

    log_event({
        "event": "chat",
        "question": req.message,
        "answer": resp[:1200],
        "latency_ms": latency_ms,
        "model": response_model,
        "adapter": response_adapter,
        "provider": provider,
        "channel": req.channel,
        "conversation_id": conv_id,
        "tenant_id": req.tenant_id,
        "context_length": len(context),
        "kb_loaded": active_kb is not None,
        "sales_stage": stage_for_debug,
        "sales_slots": slots_for_debug,
        "debug": debug_trace,
    })

    # --- SALES FLOW: save conversation turn ---
    try:
        save_turn(conv_id, req.message, resp)
    except Exception:
        pass
    if sales_enabled and sales_state is not None:
        _save_sales_state(sales_state)

    response_trigger_purchase_request = False if sales_enabled else (trigger_purchase_request if _is_tenant_sales_mode(mode) else False)
    if _is_test_mode() and _force_non_sales_purchase_trigger() and not _is_tenant_sales_mode(mode):
        response_trigger_purchase_request = True

    return ChatResp(
        reply=resp[:1200],
        latency_ms=latency_ms,
        model=response_model,
        adapter=response_adapter,
        trigger_purchase_request=response_trigger_purchase_request,
        captured_phone=captured_phone if _is_tenant_sales_mode(mode) else None,
        captured_name=captured_name if _is_tenant_sales_mode(mode) else None,
        debug=debug_trace,
    )

@app.get("/state")
def read_state(conversation_id: str):
    st = get_state(conversation_id)
    return {
        "stage": st.stage,
        "slots": st.slots,
        "updated_at": st.updated_at,
        "last_question": st.last_question,
        "last_answer": st.last_answer,
    }
