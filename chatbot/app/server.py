import json
import os
import time
import re
import threading
import gc
import unicodedata
from dataclasses import dataclass
from pathlib import Path
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
    consultation_stage_for,
    known_consultation_slots,
    next_best_action,
    resolve_product_reference,
    state_to_dict,
    update_recommended_products,
)

from .claude_provider import call_claude_api as _call_claude_api
from .conversation_orchestrator import (
    ConversationOrchestrator,
    OrchestratorContext,
    OrchestratorRequest,
)
from .llm_client import ClaudeLLMClient
# Phase 11C: module-level import for interpreter so tests can patch at app.server.*
from . import sales_state_interpreter as _sales_state_interpreter
# Re-export names for direct patch('app.server.*') convenience
call_state_interpreter = _sales_state_interpreter.call_state_interpreter
apply_interpreter_to_state = _sales_state_interpreter.apply_interpreter_to_state
_call_consultation_llm = _sales_state_interpreter.call_consultation_llm
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
from .tenant_sales_agent import (
    BRIEF_SLOT as TENANT_SALES_BRIEF_SLOT,
    build_search_query as _agent_build_search_query,
    compose_advice as _agent_compose_advice,
    compose_listing as _agent_compose_listing,
    decide_next_response as _agent_decide_next_response,
    update_customer_brief as _agent_update_customer_brief,
)


def _load_project_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and not os.getenv(key):
                os.environ[key] = value
    except Exception:
        pass


_load_project_dotenv()


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

# KB: load theo env KB_DIR (mÃƒÂ¡Ã‚Â»Ã¢â‚¬â€i process python 1 tenant)
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


def _mask_contact_in_value(v: Any) -> Any:
    """Mask phone/email in debug values. Recursively handles dict/list."""
    if isinstance(v, str):
        # Mask phone patterns (7+ digits) and email patterns
        import re
        v = re.sub(r'\d[\d\s\.\-]{6,}\d', '***masked***', v)
        v = re.sub(r'[\w\.-]+@[\w\.-]+', '***masked***', v)
        return v
    if isinstance(v, dict):
        return {k: _mask_contact_in_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_mask_contact_in_value(item) for item in v]
    return v


def _is_pytest_blocking_real_claude() -> bool:
    if os.getenv("RUN_REAL_CLAUDE_TESTS", "0").strip().lower() in TRUE_VALUES:
        return False
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _conversation_orchestrator_enabled() -> bool:
    return os.getenv("CONVERSATION_ORCHESTRATOR_ENABLED", "0").strip().lower() in TRUE_VALUES


def _orchestrator_debug_disabled(reason: str = "") -> Dict[str, Any]:
    return {
        "planner_attempted": False,
        "planner_called": False,
        "planner_skip_reason": reason,
        "planner_error_type": "",
        "planner_intent": "",
        "planner_need_retrieval": False,
        "finalizer_attempted": False,
        "finalizer_called": False,
        "finalizer_skip_reason": reason,
        "finalizer_error_type": "",
        "orchestrator_enabled": False,
        "orchestrator_fallback_reason": "",
    }


def _build_tenant_sales_consult_prompt(user_message: str, slots: Dict[str, Any], missing: List[str]) -> str:
    snap = {k: slots.get(k) for k in ("product_category", "product_type", "room", "budget_text", "budget", "style", "material", "color") if slots.get(k)}
    return (
        "BÃƒÂ¡Ã‚ÂºÃ‚Â¡n lÃƒÆ’Ã‚Â  nhÃƒÆ’Ã‚Â¢n viÃƒÆ’Ã‚Âªn tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n nÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢i thÃƒÂ¡Ã‚ÂºÃ‚Â¥t chuyÃƒÆ’Ã‚Âªn nghiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡p. TrÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi khÃƒÆ’Ã‚Â¡ch hÃƒÆ’Ã‚Â ng bÃƒÂ¡Ã‚ÂºÃ‚Â±ng tiÃƒÂ¡Ã‚ÂºÃ‚Â¿ng ViÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡t tÃƒÂ¡Ã‚Â»Ã‚Â± nhiÃƒÆ’Ã‚Âªn, ngÃƒÂ¡Ã‚ÂºÃ‚Â¯n gÃƒÂ¡Ã‚Â»Ã‚Ân (2-3 cÃƒÆ’Ã‚Â¢u).\n\n"
        "QUY TÃƒÂ¡Ã‚ÂºÃ‚Â®C:\n"
        "- Ãƒâ€žÃ‚ÂÃƒâ€ Ã‚Â°a 1 cÃƒÆ’Ã‚Â¢u tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n hÃƒÂ¡Ã‚Â»Ã‚Â¯u ÃƒÆ’Ã‚Â­ch trÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºc khi hÃƒÂ¡Ã‚Â»Ã‚Âi.\n"
        "- HÃƒÂ¡Ã‚Â»Ã‚Âi Ãƒâ€žÃ¢â‚¬ËœÃƒÆ’Ã‚Âºng 1 cÃƒÆ’Ã‚Â¢u tiÃƒÂ¡Ã‚ÂºÃ‚Â¿p theo.\n"
        "- KHÃƒÆ’Ã¢â‚¬ÂNG liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡t kÃƒÆ’Ã‚Âª sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m, SKU, giÃƒÆ’Ã‚Â¡, link nÃƒÂ¡Ã‚ÂºÃ‚Â¿u chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ evidence tÃƒÂ¡Ã‚Â»Ã‚Â« tÃƒÆ’Ã‚Â¬m kiÃƒÂ¡Ã‚ÂºÃ‚Â¿m.\n"
        "- KHÃƒÆ’Ã¢â‚¬ÂNG nÃƒÆ’Ã‚Â³i \"mÃƒÆ’Ã‚Â¬nh tÃƒÆ’Ã‚Â¬m thÃƒÂ¡Ã‚ÂºÃ‚Â¥y\" nÃƒÂ¡Ã‚ÂºÃ‚Â¿u chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ kÃƒÂ¡Ã‚ÂºÃ‚Â¿t quÃƒÂ¡Ã‚ÂºÃ‚Â£ tÃƒÆ’Ã‚Â¬m kiÃƒÂ¡Ã‚ÂºÃ‚Â¿m.\n\n"
        f"TrÃƒÂ¡Ã‚ÂºÃ‚Â¡ng thÃƒÆ’Ã‚Â¡i: {json.dumps(snap, ensure_ascii=False)}\n"
        f"ThiÃƒÂ¡Ã‚ÂºÃ‚Â¿u: {', '.join(missing) if missing else 'khÃƒÆ’Ã‚Â´ng rÃƒÆ’Ã‚Âµ'}\n"
        f"Tin nhÃƒÂ¡Ã‚ÂºÃ‚Â¯n: {user_message}\n\n"
        "TrÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi:"
    )


def _build_tenant_sales_listing_prompt(user_message: str, evidence: List[Dict[str, Any]], slots: Dict[str, Any]) -> str:
    ev_lines = []
    for e in evidence:
        pstr = f", giÃƒÆ’Ã‚Â¡ ~{e.get('price')}" if e.get("price") else ""
        cstr = f", danh mÃƒÂ¡Ã‚Â»Ã‚Â¥c {e.get('category')}" if e.get("category") else ""
        ev_lines.append(f"- {e.get('name','')} (SKU {e.get('sku','')}{pstr}{cstr}, link {e.get('url','')})")
    ev = "\n".join(ev_lines)
    cat = slots.get("product_category") or slots.get("product_type") or ""
    room = slots.get("room") or ""
    budget = slots.get("budget_text") or slots.get("budget") or ""
    return (
        "BÃƒÂ¡Ã‚ÂºÃ‚Â¡n lÃƒÆ’Ã‚Â  nhÃƒÆ’Ã‚Â¢n viÃƒÆ’Ã‚Âªn tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n nÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢i thÃƒÂ¡Ã‚ÂºÃ‚Â¥t. ViÃƒÂ¡Ã‚ÂºÃ‚Â¿t cÃƒÆ’Ã‚Â¢u trÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi tÃƒÂ¡Ã‚Â»Ã‚Â± nhiÃƒÆ’Ã‚Âªn bÃƒÂ¡Ã‚ÂºÃ‚Â±ng tiÃƒÂ¡Ã‚ÂºÃ‚Â¿ng ViÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡t.\n\n"
        "CHÃƒÂ¡Ã‚Â»Ã‹â€  DÃƒÆ’Ã¢â€žÂ¢NG EVIDENCE. KHÃƒÆ’Ã¢â‚¬ÂNG BÃƒÂ¡Ã‚Â»Ã…Â A sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m, giÃƒÆ’Ã‚Â¡, link, tÃƒÆ’Ã‚Â­nh nÃƒâ€žÃ†â€™ng, khuyÃƒÂ¡Ã‚ÂºÃ‚Â¿n mÃƒÆ’Ã‚Â£i.\n"
        "KHÃƒÆ’Ã¢â‚¬ÂNG BÃƒÂ¡Ã‚Â»Ã…Â A SKU. KHÃƒÆ’Ã¢â‚¬ÂNG BÃƒÂ¡Ã‚Â»Ã…Â A tÃƒÆ’Ã‚Â¬nh trÃƒÂ¡Ã‚ÂºÃ‚Â¡ng kho / availability.\n"
        "ChÃƒÂ¡Ã‚Â»Ã¢â‚¬Â° nhÃƒÂ¡Ã‚ÂºÃ‚Â¯c SKU hoÃƒÂ¡Ã‚ÂºÃ‚Â·c tÃƒÆ’Ã‚Â¬nh trÃƒÂ¡Ã‚ÂºÃ‚Â¡ng kho nÃƒÂ¡Ã‚ÂºÃ‚Â¿u cÃƒÆ’Ã‚Â³ trong Evidence.\n\n"
        f"Evidence:\n{ev}\n\n"
        f"Nhu cÃƒÂ¡Ã‚ÂºÃ‚Â§u: category={cat}, phÃƒÆ’Ã‚Â²ng={room}, ngÃƒÆ’Ã‚Â¢n sÃƒÆ’Ã‚Â¡ch={budget}\n"
        f"Tin nhÃƒÂ¡Ã‚ÂºÃ‚Â¯n: {user_message}\n\n"
        "ViÃƒÂ¡Ã‚ÂºÃ‚Â¿t cÃƒÆ’Ã‚Â¢u trÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi:"
    )


def _build_tenant_sales_advice_prompt(user_message: str, brief: Dict[str, Any], slots: Dict[str, Any]) -> str:
    safe_slots = {
        k: slots.get(k)
        for k in (
            "product_category",
            "product_type",
            "product_subtype",
            "room",
            "budget",
            "budget_text",
            "style",
            "material",
            "color",
            "constraints",
            "health_need",
        )
        if slots.get(k) not in (None, "", [])
    }
    return (
        "BÃƒÂ¡Ã‚ÂºÃ‚Â¡n lÃƒÆ’Ã‚Â  nhÃƒÆ’Ã‚Â¢n viÃƒÆ’Ã‚Âªn tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n nÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢i thÃƒÂ¡Ã‚ÂºÃ‚Â¥t Ãƒâ€žÃ¢â‚¬Ëœang chat 1-1 vÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi khÃƒÆ’Ã‚Â¡ch. "
        "ViÃƒÂ¡Ã‚ÂºÃ‚Â¿t tiÃƒÂ¡Ã‚ÂºÃ‚Â¿ng ViÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡t tÃƒÂ¡Ã‚Â»Ã‚Â± nhiÃƒÆ’Ã‚Âªn, thÃƒÆ’Ã‚Â¢n thiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n, cÃƒÆ’Ã‚Â³ cÃƒÂ¡Ã‚ÂºÃ‚Â£m giÃƒÆ’Ã‚Â¡c Ãƒâ€žÃ¢â‚¬Ëœang tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n thÃƒÂ¡Ã‚ÂºÃ‚Â­t chÃƒÂ¡Ã‚Â»Ã‚Â© khÃƒÆ’Ã‚Â´ng Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã‚Âc form.\n\n"
        "MÃƒÂ¡Ã‚Â»Ã‚Â¤C TIÃƒÆ’Ã…Â U:\n"
        "- TrÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi trÃƒÂ¡Ã‚Â»Ã‚Â±c tiÃƒÂ¡Ã‚ÂºÃ‚Â¿p tin nhÃƒÂ¡Ã‚ÂºÃ‚Â¯n mÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi nhÃƒÂ¡Ã‚ÂºÃ‚Â¥t cÃƒÂ¡Ã‚Â»Ã‚Â§a khÃƒÆ’Ã‚Â¡ch.\n"
        "- DÃƒÂ¡Ã‚Â»Ã‚Â±a trÃƒÆ’Ã‚Âªn customer_brief Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ nhÃƒÂ¡Ã‚Â»Ã¢â‚¬Âº ngÃƒÂ¡Ã‚Â»Ã‚Â¯ cÃƒÂ¡Ã‚ÂºÃ‚Â£nh, trÃƒÆ’Ã‚Â¡nh hÃƒÂ¡Ã‚Â»Ã‚Âi lÃƒÂ¡Ã‚ÂºÃ‚Â¡i Ãƒâ€žÃ¢â‚¬ËœiÃƒÂ¡Ã‚Â»Ã‚Âu khÃƒÆ’Ã‚Â¡ch Ãƒâ€žÃ¢â‚¬ËœÃƒÆ’Ã‚Â£ nÃƒÆ’Ã‚Â³i.\n"
        "- NÃƒÂ¡Ã‚ÂºÃ‚Â¿u chÃƒâ€ Ã‚Â°a cÃƒÂ¡Ã‚ÂºÃ‚Â§n liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡t kÃƒÆ’Ã‚Âª sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m, hÃƒÆ’Ã‚Â£y tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¹nh hÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºng/chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u/phong cÃƒÆ’Ã‚Â¡ch/cÃƒÆ’Ã‚Â¡ch chÃƒÂ¡Ã‚Â»Ã‚Ân.\n"
        "- HÃƒÂ¡Ã‚Â»Ã‚Âi tÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœi Ãƒâ€žÃ¢â‚¬Ëœa 1 cÃƒÆ’Ã‚Â¢u tiÃƒÂ¡Ã‚ÂºÃ‚Â¿p theo, chÃƒÂ¡Ã‚Â»Ã¢â‚¬Â° hÃƒÂ¡Ã‚Â»Ã‚Âi Ãƒâ€žÃ¢â‚¬ËœiÃƒÂ¡Ã‚Â»Ã‚Âu thÃƒÂ¡Ã‚ÂºÃ‚Â­t sÃƒÂ¡Ã‚Â»Ã‚Â± giÃƒÆ’Ã‚Âºp lÃƒÂ¡Ã‚Â»Ã‚Âc tÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœt hÃƒâ€ Ã‚Â¡n.\n\n"
        "GIÃƒÂ¡Ã‚Â»Ã…Â¡I HÃƒÂ¡Ã‚ÂºÃ‚Â N AN TOÃƒÆ’Ã¢â€šÂ¬N:\n"
        "- Không bịa sản phẩm, SKU, giá, link, khuyến mãi hoặc tình trạng còn hàng.\n"
        "- KhÃƒÆ’Ã‚Â´ng nÃƒÆ’Ã‚Â³i 'mÃƒÆ’Ã‚Â¬nh tÃƒÆ’Ã‚Â¬m thÃƒÂ¡Ã‚ÂºÃ‚Â¥y' nÃƒÂ¡Ã‚ÂºÃ‚Â¿u chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ evidence sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m.\n"
        "- KhÃƒÆ’Ã‚Â´ng lÃƒÂ¡Ã‚ÂºÃ‚Â·p lÃƒÂ¡Ã‚ÂºÃ‚Â¡i cÃƒÆ’Ã‚Â¢u hÃƒÂ¡Ã‚Â»Ã‚Âi dÃƒÂ¡Ã‚ÂºÃ‚Â¡ng form nhÃƒâ€ Ã‚Â° 'BÃƒÂ¡Ã‚ÂºÃ‚Â¡n muÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœn lÃƒÂ¡Ã‚Â»Ã‚Âc theo ngÃƒÆ’Ã‚Â¢n sÃƒÆ’Ã‚Â¡ch hay chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u/phong cÃƒÆ’Ã‚Â¡ch trÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºc?'.\n"
        "- KhÃƒÆ’Ã‚Â´ng tÃƒÂ¡Ã‚Â»Ã‚Â± nhÃƒÂ¡Ã‚ÂºÃ‚Â­n Ãƒâ€žÃ¢â‚¬ËœÃƒÆ’Ã‚Â£ gÃƒÂ¡Ã‚Â»Ã‚Âi cÃƒÂ¡Ã‚Â»Ã‚Â­a hÃƒÆ’Ã‚Â ng, kiÃƒÂ¡Ã‚Â»Ã†â€™m kho hoÃƒÂ¡Ã‚ÂºÃ‚Â·c xÃƒÆ’Ã‚Â¡c nhÃƒÂ¡Ã‚ÂºÃ‚Â­n tÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“n kho.\n\n"
        f"customer_brief={json.dumps(brief or {}, ensure_ascii=False)}\n"
        f"slots={json.dumps(safe_slots, ensure_ascii=False)}\n"
        f"tin_nhan_moi_nhat={user_message}\n\n"
        "TrÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi 2-4 cÃƒÆ’Ã‚Â¢u:"
    )


def _build_claude_advisor_prompt(
    *,
    mode: str,
    user_message: str,
    context: str,
    customer_brief: Optional[Dict[str, Any]] = None,
    slots: Optional[Dict[str, Any]] = None,
) -> str:
    evidence = (context or "").strip()
    brief = customer_brief or {}
    safe_slots = _mask_contact_in_value(dict(slots or {}))
    if mode == ChatMode.GENERAL_COMPARE.value:
        role = (
            "BÃƒÂ¡Ã‚ÂºÃ‚Â¡n lÃƒÆ’Ã‚Â  cÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœ vÃƒÂ¡Ã‚ÂºÃ‚Â¥n so sÃƒÆ’Ã‚Â¡nh sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m trung lÃƒÂ¡Ã‚ÂºÃ‚Â­p. GiÃƒÆ’Ã‚Âºp khÃƒÆ’Ã‚Â¡ch hiÃƒÂ¡Ã‚Â»Ã†â€™u khÃƒÆ’Ã‚Â¡c biÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡t, Ãƒâ€žÃ¢â‚¬ËœiÃƒÂ¡Ã‚Â»Ã†â€™m hÃƒÂ¡Ã‚Â»Ã‚Â£p/khÃƒÆ’Ã‚Â´ng hÃƒÂ¡Ã‚Â»Ã‚Â£p theo nhu cÃƒÂ¡Ã‚ÂºÃ‚Â§u, "
            "khÃƒÆ’Ã‚Â´ng chÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœt Ãƒâ€žÃ¢â‚¬ËœÃƒâ€ Ã‚Â¡n vÃƒÆ’Ã‚Â  khÃƒÆ’Ã‚Â´ng Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â©y mua."
        )
        mode_rules = (
            "- So sÃƒÆ’Ã‚Â¡nh theo cÃƒÆ’Ã‚Â¡c tiÃƒÆ’Ã‚Âªu chÃƒÆ’Ã‚Â­ cÃƒÆ’Ã‚Â³ ÃƒÆ’Ã‚Â­ch nhÃƒâ€ Ã‚Â° cÃƒÆ’Ã‚Â´ng nÃƒâ€žÃ†â€™ng, chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u, kÃƒÆ’Ã‚Â­ch thÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºc, phong cÃƒÆ’Ã‚Â¡ch, giÃƒÆ’Ã‚Â¡ nÃƒÂ¡Ã‚ÂºÃ‚Â¿u cÃƒÆ’Ã‚Â³.\n"
            "- NÃƒÂ¡Ã‚ÂºÃ‚Â¿u dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u thiÃƒÂ¡Ã‚ÂºÃ‚Â¿u, nÃƒÆ’Ã‚Â³i mÃƒÂ¡Ã‚Â»Ã‚Âm theo hÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºng cÃƒÂ¡Ã‚ÂºÃ‚Â§n thÃƒÆ’Ã‚Âªm thÃƒÆ’Ã‚Â´ng tin Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ so kÃƒÂ¡Ã‚Â»Ã‚Â¹ hÃƒâ€ Ã‚Â¡n; khÃƒÆ’Ã‚Â´ng dÃƒÆ’Ã‚Â¹ng cÃƒÆ’Ã‚Â¢u phÃƒÂ¡Ã‚Â»Ã‚Â§ Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¹nh cÃƒÂ¡Ã‚Â»Ã‚Â©ng.\n"
            "- KhÃƒÆ’Ã‚Â´ng bÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¹a thÃƒÆ’Ã‚Â´ng sÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœ, giÃƒÆ’Ã‚Â¡, SKU, link hoÃƒÂ¡Ã‚ÂºÃ‚Â·c nguÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“n dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u."
        )
    elif mode == ChatMode.MARKET_PRICE.value:
        role = (
            "BÃƒÂ¡Ã‚ÂºÃ‚Â¡n lÃƒÆ’Ã‚Â  cÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœ vÃƒÂ¡Ã‚ÂºÃ‚Â¥n tham chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u giÃƒÆ’Ã‚Â¡. GiÃƒÂ¡Ã‚ÂºÃ‚Â£i thÃƒÆ’Ã‚Â­ch khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng giÃƒÆ’Ã‚Â¡ vÃƒÆ’Ã‚Â  mÃƒÂ¡Ã‚Â»Ã‚Â©c hÃƒÂ¡Ã‚Â»Ã‚Â£p lÃƒÆ’Ã‚Â½ bÃƒÂ¡Ã‚ÂºÃ‚Â±ng ngÃƒÆ’Ã‚Â´n ngÃƒÂ¡Ã‚Â»Ã‚Â¯ dÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¦ hiÃƒÂ¡Ã‚Â»Ã†â€™u, "
            "khÃƒÆ’Ã‚Â´ng thÃƒÆ’Ã‚Âºc Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â©y mua sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m cÃƒÂ¡Ã‚Â»Ã‚Â¥ thÃƒÂ¡Ã‚Â»Ã†â€™."
        )
        mode_rules = (
            "- ChÃƒÂ¡Ã‚Â»Ã¢â‚¬Â° nhÃƒÂ¡Ã‚ÂºÃ‚Â­n xÃƒÆ’Ã‚Â©t giÃƒÆ’Ã‚Â¡ dÃƒÂ¡Ã‚Â»Ã‚Â±a trÃƒÆ’Ã‚Âªn evidence/provider context.\n"
            "- NÃƒÆ’Ã‚Âªu yÃƒÂ¡Ã‚ÂºÃ‚Â¿u tÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœ lÃƒÆ’Ã‚Â m giÃƒÆ’Ã‚Â¡ thay Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¢i nhÃƒâ€ Ã‚Â° chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u, kÃƒÆ’Ã‚Â­ch thÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºc, tÃƒÆ’Ã‚Â¬nh trÃƒÂ¡Ã‚ÂºÃ‚Â¡ng, vÃƒÂ¡Ã‚ÂºÃ‚Â­n chuyÃƒÂ¡Ã‚Â»Ã†â€™n/lÃƒÂ¡Ã‚ÂºÃ‚Â¯p Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â·t nÃƒÂ¡Ã‚ÂºÃ‚Â¿u phÃƒÆ’Ã‚Â¹ hÃƒÂ¡Ã‚Â»Ã‚Â£p.\n"
            "- KhÃƒÆ’Ã‚Â´ng bÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¹a giÃƒÆ’Ã‚Â¡ thÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¹ trÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âng, nguÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“n tham chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u, SKU, link hoÃƒÂ¡Ã‚ÂºÃ‚Â·c tÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“n kho."
        )
    else:
        role = (
            "BÃƒÂ¡Ã‚ÂºÃ‚Â¡n lÃƒÆ’Ã‚Â  nhÃƒÆ’Ã‚Â¢n viÃƒÆ’Ã‚Âªn tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n nÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢i thÃƒÂ¡Ã‚ÂºÃ‚Â¥t Ãƒâ€žÃ¢â‚¬Ëœang chat 1-1 vÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi khÃƒÆ’Ã‚Â¡ch. HÃƒÆ’Ã‚Â£y tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n nhÃƒâ€ Ã‚Â° ngÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âi thÃƒÂ¡Ã‚ÂºÃ‚Â­t: nhÃƒÂ¡Ã‚Â»Ã¢â‚¬Âº ngÃƒÂ¡Ã‚Â»Ã‚Â¯ cÃƒÂ¡Ã‚ÂºÃ‚Â£nh, "
            "thÃƒÆ’Ã‚Âªm insight nhÃƒÂ¡Ã‚Â»Ã‚Â, gÃƒÂ¡Ã‚Â»Ã‚Â£i ÃƒÆ’Ã‚Â½ hÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºng chÃƒÂ¡Ã‚Â»Ã‚Ân hÃƒÂ¡Ã‚Â»Ã‚Â£p lÃƒÆ’Ã‚Â½ rÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“i mÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi hÃƒÂ¡Ã‚Â»Ã‚Âi tiÃƒÂ¡Ã‚ÂºÃ‚Â¿p nÃƒÂ¡Ã‚ÂºÃ‚Â¿u cÃƒÂ¡Ã‚ÂºÃ‚Â§n."
        )
        mode_rules = (
            "- NÃƒÂ¡Ã‚ÂºÃ‚Â¿u cÃƒÆ’Ã‚Â³ evidence sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m, chÃƒÂ¡Ã‚Â»Ã¢â‚¬Â° dÃƒÆ’Ã‚Â¹ng sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m/giÃƒÆ’Ã‚Â¡/SKU/link trong evidence.\n"
            "- NÃƒÂ¡Ã‚ÂºÃ‚Â¿u chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ evidence sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m, tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¹nh hÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºng theo nhu cÃƒÂ¡Ã‚ÂºÃ‚Â§u; khÃƒÆ’Ã‚Â´ng nÃƒÆ’Ã‚Â³i 'mÃƒÆ’Ã‚Â¬nh tÃƒÆ’Ã‚Â¬m thÃƒÂ¡Ã‚ÂºÃ‚Â¥y'.\n"
            "- Không bịa sản phẩm, SKU, giá, link, khuyến mãi hoặc tình trạng tồn kho."
        )
    return (
        f"{role}\n\n"
        "GIÃƒÂ¡Ã‚Â»Ã…â€™NG Ãƒâ€žÃ‚ÂIÃƒÂ¡Ã‚Â»Ã¢â‚¬Â U:\n"
        "- TiÃƒÂ¡Ã‚ÂºÃ‚Â¿ng ViÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡t tÃƒÂ¡Ã‚Â»Ã‚Â± nhiÃƒÆ’Ã‚Âªn, thÃƒÆ’Ã‚Â¢n thiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n, khÃƒÆ’Ã‚Â´ng Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã‚Âc form.\n"
        "- KhÃƒÆ’Ã‚Â´ng mÃƒÂ¡Ã‚Â»Ã…Â¸ Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â§u bÃƒÂ¡Ã‚ÂºÃ‚Â±ng cÃƒÆ’Ã‚Â¡c cÃƒÆ’Ã‚Â¢u phÃƒÂ¡Ã‚Â»Ã‚Â§ Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¹nh/cÃƒÂ¡Ã‚Â»Ã‚Â©ng nhÃƒâ€ Ã‚Â° 'mÃƒÆ’Ã‚Â¬nh khÃƒÆ’Ã‚Â´ng...', 'mÃƒÆ’Ã‚Â¬nh chÃƒâ€ Ã‚Â°a...', 'tÃƒÆ’Ã‚Â´i khÃƒÆ’Ã‚Â´ng cÃƒÆ’Ã‚Â³...'.\n"
        "- KhÃƒÆ’Ã‚Â´ng lÃƒÂ¡Ã‚ÂºÃ‚Â·p lÃƒÂ¡Ã‚ÂºÃ‚Â¡i cÃƒÆ’Ã‚Â¢u kiÃƒÂ¡Ã‚Â»Ã†â€™u 'MÃƒÆ’Ã‚Â¬nh Ãƒâ€žÃ¢â‚¬ËœÃƒÆ’Ã‚Â£ hiÃƒÂ¡Ã‚Â»Ã†â€™u hÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºng chÃƒÆ’Ã‚Â­nh lÃƒÆ’Ã‚Â ...' hoÃƒÂ¡Ã‚ÂºÃ‚Â·c 'BÃƒÂ¡Ã‚ÂºÃ‚Â¡n muÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœn mÃƒÆ’Ã‚Â¬nh lÃƒÂ¡Ã‚Â»Ã‚Âc theo ngÃƒÆ’Ã‚Â¢n sÃƒÆ’Ã‚Â¡ch hay chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u/phong cÃƒÆ’Ã‚Â¡ch trÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºc?'.\n"
        "- TrÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi trÃƒÂ¡Ã‚Â»Ã‚Â±c tiÃƒÂ¡Ã‚ÂºÃ‚Â¿p tin nhÃƒÂ¡Ã‚ÂºÃ‚Â¯n mÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi nhÃƒÂ¡Ã‚ÂºÃ‚Â¥t; nÃƒÂ¡Ã‚ÂºÃ‚Â¿u hÃƒÂ¡Ã‚Â»Ã‚Âi tiÃƒÂ¡Ã‚ÂºÃ‚Â¿p thÃƒÆ’Ã‚Â¬ hÃƒÂ¡Ã‚Â»Ã‚Âi tÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœi Ãƒâ€žÃ¢â‚¬Ëœa 1 cÃƒÆ’Ã‚Â¢u thÃƒÂ¡Ã‚ÂºÃ‚Â­t sÃƒÂ¡Ã‚Â»Ã‚Â± cÃƒÂ¡Ã‚ÂºÃ‚Â§n.\n\n"
        "QUY TÃƒÂ¡Ã‚ÂºÃ‚Â®C AN TOÃƒÆ’Ã¢â€šÂ¬N:\n"
        f"{mode_rules}\n\n"
        f"mode={mode}\n"
        f"customer_brief={json.dumps(brief, ensure_ascii=False)}\n"
        f"slots={json.dumps(safe_slots, ensure_ascii=False)}\n"
        f"evidence_or_provider_context:\n{evidence if evidence else '(khÃƒÆ’Ã‚Â´ng cÃƒÆ’Ã‚Â³ evidence sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m cÃƒÂ¡Ã‚Â»Ã‚Â¥ thÃƒÂ¡Ã‚Â»Ã†â€™)'}\n\n"
        f"tin_nhan_moi_nhat={user_message}\n\n"
        "ViÃƒÂ¡Ã‚ÂºÃ‚Â¿t cÃƒÆ’Ã‚Â¢u trÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi cuÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœi cÃƒÆ’Ã‚Â¹ng 2-5 cÃƒÆ’Ã‚Â¢u:"
    )


def _try_claude_advisor_response(
    *,
    mode: str,
    user_message: str,
    context: str,
    customer_brief: Optional[Dict[str, Any]],
    slots: Optional[Dict[str, Any]],
    debug_trace: Dict[str, Any],
    max_tokens: int = 800,
    temperature: float = 0.72,
) -> Optional[str]:
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    debug_trace.setdefault("real_claude_response_attempted", False)
    debug_trace.setdefault("real_claude_response_called", False)
    debug_trace.setdefault("real_claude_response_mode", "not_applicable")
    debug_trace.setdefault("real_claude_skip_reason", "not_applicable")
    debug_trace.setdefault("real_claude_error_type", None)
    if not api_key:
        debug_trace["real_claude_skip_reason"] = "missing_api_key"
        return None
    if _is_pytest_blocking_real_claude():
        debug_trace["real_claude_skip_reason"] = "pytest_real_llm_disabled"
        debug_trace["llm_skip_reason"] = "pytest_real_llm_disabled"
        return None

    prompt = _build_claude_advisor_prompt(
        mode=mode,
        user_message=user_message,
        context=context,
        customer_brief=customer_brief,
        slots=slots,
    )
    debug_trace["real_claude_response_attempted"] = True
    debug_trace["real_claude_response_mode"] = f"{mode}_advisor"
    debug_trace["llm_enabled"] = True
    debug_trace["llm_provider"] = "claude"
    debug_trace["llm_call_attempted"] = True
    try:
        started = time.time()
        out, err, preview = _call_claude_api(
            prompt,
            api_key,
            os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6",
            os.getenv("CLAUDE_API_BASE_URL") or "https://api.anthropic.com",
            max_tokens,
            temperature,
            1.0,
            30,
        )
        if out and not err:
            debug_trace.update({
                "answer_mode": "claude_advisor",
                "template_renderer": False,
                "llm_called": True,
                "llm_skip_reason": "",
                "real_claude_response_called": True,
                "real_claude_skip_reason": "",
                "real_claude_error_type": None,
            })
            try:
                log_event({
                    "event": "claude_advisor_response",
                    "mode": mode,
                    "latency_ms": int((time.time() - started) * 1000),
                })
            except Exception:
                pass
            print(f"[LLM] claude_advisor success mode={mode} latency_ms={int((time.time()-started)*1000)}")
            return out.strip()
        debug_trace.update({
            "real_claude_response_called": False,
            "real_claude_skip_reason": "claude_error_or_empty",
            "real_claude_error_type": err or "empty",
            "llm_skip_reason": "claude_error_or_empty",
        })
        print(f"[LLM] claude_advisor failed mode={mode} error_type={debug_trace.get('real_claude_error_type')}")
    except Exception as exc:
        debug_trace.update({
            "real_claude_response_called": False,
            "real_claude_skip_reason": "exception",
            "real_claude_error_type": exc.__class__.__name__,
            "llm_skip_reason": "fallback_after_error",
        })
        print(f"[LLM] claude_advisor failed mode={mode} error_type={exc.__class__.__name__}")
    return None


def _tenant_sales_style_question(message: str) -> bool:
    text = _fold_sku(message or "")
    return bool(
        re.search(r"\b(phong cach|style|kieu|kieu dang|loai|nhung phong cach)\b", text)
        and re.search(r"\b(co|ban|cua hang|shop|ben)\b", text)
    )


def _tenant_sales_soft_preference(message: str) -> bool:
    text = _fold_sku(message or "")
    return bool(re.search(r"\b(mem|em|em ai|ngoi lau|thu gian|boc nem|boc vai|boc da)\b", text))


def _tenant_sales_style_consult_reply(slots: Dict[str, Any], message: str) -> str:
    category = slots.get("product_category") or slots.get("product_type") or "sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m"
    room = slots.get("room") or "khÃƒÆ’Ã‚Â´ng gian cÃƒÂ¡Ã‚Â»Ã‚Â§a bÃƒÂ¡Ã‚ÂºÃ‚Â¡n"
    if _fold_sku(str(category)) == "ghe":
        lead = (
            f"NÃƒÂ¡Ã‚ÂºÃ‚Â¿u bÃƒÂ¡Ã‚ÂºÃ‚Â¡n Ãƒâ€žÃ¢â‚¬Ëœang nghiÃƒÆ’Ã‚Âªng vÃƒÂ¡Ã‚Â»Ã‚Â ghÃƒÂ¡Ã‚ÂºÃ‚Â¿ cho {room}, mÃƒÆ’Ã‚Â¬nh sÃƒÂ¡Ã‚ÂºÃ‚Â½ Ãƒâ€ Ã‚Â°u tiÃƒÆ’Ã‚Âªn cÃƒÆ’Ã‚Â¡c mÃƒÂ¡Ã‚ÂºÃ‚Â«u cÃƒÆ’Ã‚Â³ nÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡m, bÃƒÂ¡Ã‚Â»Ã‚Âc vÃƒÂ¡Ã‚ÂºÃ‚Â£i/da "
            "hoÃƒÂ¡Ã‚ÂºÃ‚Â·c dÃƒÆ’Ã‚Â¡ng thÃƒâ€ Ã‚Â° giÃƒÆ’Ã‚Â£n thay vÃƒÆ’Ã‚Â¬ ghÃƒÂ¡Ã‚ÂºÃ‚Â¿ vÃƒâ€žÃ†â€™n phÃƒÆ’Ã‚Â²ng/lÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi khÃƒÆ’Ã‚Â´ cÃƒÂ¡Ã‚Â»Ã‚Â©ng."
        )
        styles = (
            "BÃƒÆ’Ã‚Âªn mÃƒÆ’Ã‚Â¬nh thÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âng cÃƒÆ’Ã‚Â³ vÃƒÆ’Ã‚Â i hÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºng dÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¦ chÃƒÂ¡Ã‚Â»Ã‚Ân: hiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â¡i gÃƒÂ¡Ã‚Â»Ã‚Ân, tÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœi giÃƒÂ¡Ã‚ÂºÃ‚Â£n, BÃƒÂ¡Ã‚ÂºÃ‚Â¯c ÃƒÆ’Ã¢â‚¬Å¡u sÃƒÆ’Ã‚Â¡ng mÃƒÆ’Ã‚Â u, "
            "cafe/lounge mÃƒÂ¡Ã‚Â»Ã‚Âm mÃƒÂ¡Ã‚ÂºÃ‚Â¡i vÃƒÆ’Ã‚Â  mÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢t sÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœ mÃƒÂ¡Ã‚ÂºÃ‚Â«u cÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¢ Ãƒâ€žÃ¢â‚¬ËœiÃƒÂ¡Ã‚Â»Ã†â€™n nhÃƒÂ¡Ã‚ÂºÃ‚Â¹."
        )
        return f"{lead} {styles} BÃƒÂ¡Ã‚ÂºÃ‚Â¡n muÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœn mÃƒÆ’Ã‚Â¬nh lÃƒÂ¡Ã‚Â»Ã‚Âc ghÃƒÂ¡Ã‚ÂºÃ‚Â¿ Ãƒâ€žÃ¢â‚¬ËœÃƒâ€ Ã‚Â¡n ÃƒÆ’Ã‚Âªm hay bÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢ ghÃƒÂ¡Ã‚ÂºÃ‚Â¿/sofa nhÃƒÂ¡Ã‚Â»Ã‚Â cho phÃƒÆ’Ã‚Â²ng khÃƒÆ’Ã‚Â¡ch?"
    return (
        f"VÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi {category} cho {room}, mÃƒÆ’Ã‚Â¬nh cÃƒÆ’Ã‚Â³ thÃƒÂ¡Ã‚Â»Ã†â€™ lÃƒÂ¡Ã‚Â»Ã‚Âc theo cÃƒÆ’Ã‚Â¡c hÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºng hiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â¡i, tÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœi giÃƒÂ¡Ã‚ÂºÃ‚Â£n, BÃƒÂ¡Ã‚ÂºÃ‚Â¯c ÃƒÆ’Ã¢â‚¬Å¡u, "
        "cÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¢ Ãƒâ€žÃ¢â‚¬ËœiÃƒÂ¡Ã‚Â»Ã†â€™n nhÃƒÂ¡Ã‚ÂºÃ‚Â¹ hoÃƒÂ¡Ã‚ÂºÃ‚Â·c kiÃƒÂ¡Ã‚Â»Ã†â€™u ÃƒÂ¡Ã‚ÂºÃ‚Â¥m cÃƒÆ’Ã‚Âºng tÃƒÂ¡Ã‚Â»Ã‚Â± nhiÃƒÆ’Ã‚Âªn. BÃƒÂ¡Ã‚ÂºÃ‚Â¡n thÃƒÆ’Ã‚Â­ch cÃƒÂ¡Ã‚ÂºÃ‚Â£m giÃƒÆ’Ã‚Â¡c gÃƒÂ¡Ã‚Â»Ã‚Ân sÃƒÆ’Ã‚Â¡ng hay mÃƒÂ¡Ã‚Â»Ã‚Âm ÃƒÂ¡Ã‚ÂºÃ‚Â¥m hÃƒâ€ Ã‚Â¡n?"
    )


def _tenant_sales_hit_meta(hit: Any) -> Dict[str, Any]:
    metadata = getattr(hit, "metadata", {}) if hasattr(hit, "metadata") else {}
    return metadata if isinstance(metadata, dict) else {}


def _tenant_sales_hit_name(hit: Any) -> str:
    meta = _tenant_sales_hit_meta(hit)
    return str(meta.get("product_name") or getattr(hit, "title", "") or "").strip()


def _tenant_sales_hit_sku(hit: Any) -> str:
    meta = _tenant_sales_hit_meta(hit)
    return str(meta.get("sku") or getattr(hit, "sku", "") or "").strip()


def _tenant_sales_hit_price(hit: Any) -> Any:
    return _tenant_sales_hit_meta(hit).get("price")


def _tenant_sales_soft_listing_reply(message: str, hits: List[Any], slots: Dict[str, Any]) -> str:
    category = slots.get("product_category") or slots.get("product_type") or "sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m"
    room = slots.get("room") or "khÃƒÆ’Ã‚Â´ng gian cÃƒÂ¡Ã‚Â»Ã‚Â§a bÃƒÂ¡Ã‚ÂºÃ‚Â¡n"
    intro = f"MÃƒÆ’Ã‚Â¬nh lÃƒÂ¡Ã‚Â»Ã‚Âc Ãƒâ€žÃ¢â‚¬ËœÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Â£c vÃƒÆ’Ã‚Â i mÃƒÂ¡Ã‚ÂºÃ‚Â«u {str(category).lower()} hÃƒÂ¡Ã‚Â»Ã‚Â£p vÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi {room}"
    if _tenant_sales_soft_preference(message) or slots.get("constraints"):
        intro += ", Ãƒâ€ Ã‚Â°u tiÃƒÆ’Ã‚Âªn cÃƒÂ¡Ã‚ÂºÃ‚Â£m giÃƒÆ’Ã‚Â¡c mÃƒÂ¡Ã‚Â»Ã‚Âm vÃƒÆ’Ã‚Â  dÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¦ ngÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“i"
    intro += ":"
    lines = [intro]
    for idx, hit in enumerate((hits or [])[:3], start=1):
        name = _tenant_sales_hit_name(hit) or f"MÃƒÂ¡Ã‚ÂºÃ‚Â«u {idx}"
        sku = _tenant_sales_hit_sku(hit)
        price = _tenant_sales_hit_price(hit)
        bits = []
        if sku:
            bits.append(sku)
        if price not in (None, ""):
            try:
                bits.append(f"{int(float(price)):,} VND".replace(",", "."))
            except (TypeError, ValueError):
                bits.append(str(price))
        suffix = f" ({' - '.join(bits)})" if bits else ""
        lines.append(f"{idx}. {name}{suffix}")
    lines.append("BÃƒÂ¡Ã‚ÂºÃ‚Â¡n muÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœn mÃƒÆ’Ã‚Â¬nh nghiÃƒÆ’Ã‚Âªng vÃƒÂ¡Ã‚Â»Ã‚Â mÃƒÂ¡Ã‚ÂºÃ‚Â«u ÃƒÆ’Ã‚Âªm thÃƒâ€ Ã‚Â° giÃƒÆ’Ã‚Â£n, gÃƒÂ¡Ã‚Â»Ã‚Ân hiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â¡i hay mÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢t bÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢ ghÃƒÂ¡Ã‚ÂºÃ‚Â¿ tiÃƒÂ¡Ã‚ÂºÃ‚Â¿p khÃƒÆ’Ã‚Â¡ch Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â§y Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã‚Â§ hÃƒâ€ Ã‚Â¡n?")
    return "\n".join(lines)


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
    # Phase 10F: LLM/trace debug fields ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â hardcoded defaults (overridden in callers)
    llm_enabled: bool = False,
    llm_provider: str = "none",
    llm_model: str = "",
    llm_call_attempted: bool = False,
    llm_called: bool = False,
    llm_skip_reason: str = "",
    llm_error_type: str = "",
    answer_mode: str = "",
    template_reason: str = "",
    retrieval_query: str = "",
    requested_category: str = "",
    slots_snapshot: Optional[Dict[str, Any]] = None,
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
        # Phase 10F: LLM/trace debug fields
        "llm_enabled": llm_enabled,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_call_attempted": llm_call_attempted,
        "llm_called": llm_called,
        "llm_skip_reason": llm_skip_reason,
        "llm_error_type": llm_error_type,
        "answer_mode": answer_mode,
        "template_reason": template_reason,
        "retrieval_query": retrieval_query,
        "requested_category": requested_category,
        "slots_snapshot": dict(slots_snapshot or {}),
        "planner_attempted": False,
        "planner_called": False,
        "planner_skip_reason": "",
        "planner_error_type": "",
        "planner_intent": "",
        "planner_need_retrieval": False,
        "finalizer_attempted": False,
        "finalizer_called": False,
        "finalizer_skip_reason": "",
        "finalizer_error_type": "",
        "orchestrator_enabled": False,
        "orchestrator_fallback_reason": "",
    }


def _collect_debug_skus(value: Any, limit: int = 8) -> List[str]:
    skus: List[str] = []

    def visit(item: Any) -> None:
        if len(skus) >= limit:
            return
        if isinstance(item, dict):
            sku = item.get("sku") or item.get("SKU")
            if sku:
                sku_text = str(sku)
                if sku_text not in skus:
                    skus.append(sku_text)
            for key in ("metadata", "product", "items", "products", "evidence", "selected_products"):
                if key in item:
                    visit(item[key])
        elif isinstance(item, list):
            for child in item:
                visit(child)
                if len(skus) >= limit:
                    break

    visit(value)
    return skus


def _first_debug_reason(debug_trace: Dict[str, Any]) -> str:
    for key in (
        "planner_skip_reason",
        "finalizer_skip_reason",
        "real_claude_skip_reason",
        "consultation_llm_skip_reason",
        "state_interpreter_skip_reason",
        "llm_skip_reason",
        "orchestrator_fallback_reason",
        "fallback_reason",
        "template_reason",
    ):
        value = debug_trace.get(key)
        if value not in (None, "", "not_applicable", "not_yet"):
            return str(value)
    return ""


def _with_production_debug_panel(debug_trace: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if debug_trace is None:
        return None
    retrieval_count = int(debug_trace.get("retrieval_count") or debug_trace.get("retrieved_docs") or 0)
    sales_action = debug_trace.get("sales_action_taken") or debug_trace.get("sales_action") or "none"
    purchase_status = debug_trace.get("purchase_request_status")
    lead_created = bool(
        debug_trace.get("lead_created")
        or debug_trace.get("handoff_id")
        or purchase_status == "draft"
        or sales_action in {"handoff", "handoff_sent", "handoff_already_sent"}
    )
    retrieved_skus = _collect_debug_skus({
        "evidence": debug_trace.get("evidence"),
        "selected_products": debug_trace.get("selected_products"),
        "product_evidence": debug_trace.get("product_evidence"),
    })
    panel = {
        "phase": "E",
        "mode": debug_trace.get("mode", ""),
        "route": debug_trace.get("template_reason") or debug_trace.get("answer_mode") or "",
        "answer_mode": debug_trace.get("answer_mode", ""),
        "planner_intent": debug_trace.get("planner_intent", ""),
        "need_retrieval": bool(debug_trace.get("planner_need_retrieval") or retrieval_count > 0),
        "retrieval_count": retrieval_count,
        "retrieved_skus": retrieved_skus,
        "finalizer_called": bool(debug_trace.get("finalizer_called")),
        "skip_reason": _first_debug_reason(debug_trace),
        "sales_action": sales_action,
        "lead_created": lead_created,
        "purchase_request_status": purchase_status,
        "llm_called": bool(debug_trace.get("llm_called")),
        "real_claude_response_called": bool(debug_trace.get("real_claude_response_called")),
    }
    debug_trace["production_debug_panel"] = panel
    debug_trace["phase_e_debug_panel"] = panel
    return debug_trace


def _messages_to_plain_prompt(messages: List[Dict[str, Any]]) -> str:
    parts = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        parts.append(f"{role.upper()}:\n{content}")
    return "\n\n".join(parts)


def _extract_candidate_price_vnd(message: str) -> Optional[float]:
    text = (message or "").lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(trieu|triÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u|m|million)", text)
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
        return f"khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng {min_m:.1f} triÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u VND"
    return f"khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng {min_m:.1f}-{max_m:.1f} triÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u VND"


def _format_vnd_value(price: float) -> str:
    if price >= 1_000_000:
        return f"{price / 1_000_000:.1f} triÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u VND"
    return f"{price:,.0f} VND"


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("Ãƒâ€žÃ¢â‚¬Ëœ", "d").replace("Ãƒâ€žÃ‚Â", "D")


def _market_price_subject(user_message: str, price_refs: List[Any]) -> str:
    message = user_message or ""
    code_match = re.search(r"\b[A-Z]{2,}[A-Z0-9-]*\d+[A-Z0-9-]*\b", message.upper())
    if code_match:
        return code_match.group(0)

    plain = _strip_accents(message).lower()
    if "sofa" in plain and "go soi" in plain:
        return "sofa gÃƒÂ¡Ã‚Â»Ã¢â‚¬â€ sÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“i"
    if "sofa" in plain:
        return "sofa"
    if "ban an" in plain:
        return "bÃƒÆ’Ã‚Â n Ãƒâ€žÃ†â€™n"
    if "tu quan ao" in plain or "tu ao" in plain:
        return "tÃƒÂ¡Ã‚Â»Ã‚Â§ quÃƒÂ¡Ã‚ÂºÃ‚Â§n ÃƒÆ’Ã‚Â¡o"
    if "giuong" in plain:
        return "giÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âng"

    return next(
        (
            str(value)
            for ref in price_refs
            for value in (getattr(ref, "product_id", None), getattr(ref, "name", None))
            if value
        ),
        "sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m",
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
            "ChÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã‚Â§ dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u giÃƒÆ’Ã‚Â¡ cÃƒÆ’Ã‚Â³ cÃƒÂ¡Ã‚ÂºÃ‚Â¥u trÃƒÆ’Ã‚Âºc Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ Ãƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºc lÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Â£ng khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng giÃƒÆ’Ã‚Â¡ hoÃƒÂ¡Ã‚ÂºÃ‚Â·c phÃƒÆ’Ã‚Â¡t hiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n bÃƒÂ¡Ã‚ÂºÃ‚Â¥t thÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âng. "
            "BÃƒÂ¡Ã‚ÂºÃ‚Â¡n cÃƒÆ’Ã‚Â³ thÃƒÂ¡Ã‚Â»Ã†â€™ gÃƒÂ¡Ã‚Â»Ã‚Â­i thÃƒÆ’Ã‚Âªm tÃƒÆ’Ã‚Âªn sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m, mÃƒÆ’Ã‚Â£ sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m, vÃƒÂ¡Ã‚ÂºÃ‚Â­t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u, kÃƒÆ’Ã‚Â­ch thÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºc hoÃƒÂ¡Ã‚ÂºÃ‚Â·c mÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢t mÃƒÂ¡Ã‚Â»Ã‚Â©c giÃƒÆ’Ã‚Â¡ cÃƒÂ¡Ã‚Â»Ã‚Â¥ thÃƒÂ¡Ã‚Â»Ã†â€™ "
            "Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ mÃƒÆ’Ã‚Â¬nh phÃƒÆ’Ã‚Â¢n tÃƒÆ’Ã‚Â­ch sÃƒÆ’Ã‚Â¡t hÃƒâ€ Ã‚Â¡n."
        )

    min_price = min(price_values)
    max_price = max(price_values)
    candidate_price = _extract_candidate_price_vnd(user_message)
    product_label = _market_price_subject(user_message, price_refs)

    if candidate_price is None:
        judgement = (
            "NÃƒÂ¡Ã‚ÂºÃ‚Â¿u chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ mÃƒÂ¡Ã‚Â»Ã‚Â©c giÃƒÆ’Ã‚Â¡ cÃƒÂ¡Ã‚Â»Ã‚Â¥ thÃƒÂ¡Ã‚Â»Ã†â€™ Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœi chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u, cÃƒÆ’Ã‚Â³ thÃƒÂ¡Ã‚Â»Ã†â€™ dÃƒÆ’Ã‚Â¹ng khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng nÃƒÆ’Ã‚Â y lÃƒÆ’Ã‚Â m mÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœc tham khÃƒÂ¡Ã‚ÂºÃ‚Â£o ban Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â§u."
        )
    elif candidate_price < min_price:
        judgement = f"MÃƒÂ¡Ã‚Â»Ã‚Â©c {_format_vnd_value(candidate_price)} Ãƒâ€žÃ¢â‚¬Ëœang thÃƒÂ¡Ã‚ÂºÃ‚Â¥p hÃƒâ€ Ã‚Â¡n khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng tham chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u."
    elif candidate_price > max_price:
        judgement = f"MÃƒÂ¡Ã‚Â»Ã‚Â©c {_format_vnd_value(candidate_price)} Ãƒâ€žÃ¢â‚¬Ëœang cao hÃƒâ€ Ã‚Â¡n khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng tham chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u."
    else:
        judgement = f"MÃƒÂ¡Ã‚Â»Ã‚Â©c {_format_vnd_value(candidate_price)} Ãƒâ€žÃ¢â‚¬Ëœang nÃƒÂ¡Ã‚ÂºÃ‚Â±m trong khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng tham chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u."

    return (
        f"## Tham khÃƒÂ¡Ã‚ÂºÃ‚Â£o giÃƒÆ’Ã‚Â¡ {product_label}\n"
        f"KhoÃƒÂ¡Ã‚ÂºÃ‚Â£ng giÃƒÆ’Ã‚Â¡ tham khÃƒÂ¡Ã‚ÂºÃ‚Â£o: {_format_vnd_range(min_price, max_price)}.\n"
        f"DÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœi chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u: {len(price_values)} mÃƒÂ¡Ã‚ÂºÃ‚Â«u tham chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u hiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n cÃƒÆ’Ã‚Â³.\n"
        f"NhÃƒÂ¡Ã‚ÂºÃ‚Â­n xÃƒÆ’Ã‚Â©t: {judgement}\n"
        "LÃƒâ€ Ã‚Â°u ÃƒÆ’Ã‚Â½: KhoÃƒÂ¡Ã‚ÂºÃ‚Â£ng giÃƒÆ’Ã‚Â¡ cÃƒÆ’Ã‚Â³ thÃƒÂ¡Ã‚Â»Ã†â€™ thay Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¢i theo kÃƒÆ’Ã‚Â­ch thÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºc, chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u, Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢ mÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi, thÃƒâ€ Ã‚Â°Ãƒâ€ Ã‚Â¡ng hiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u vÃƒÆ’Ã‚Â  chi phÃƒÆ’Ã‚Â­ vÃƒÂ¡Ã‚ÂºÃ‚Â­n chuyÃƒÂ¡Ã‚Â»Ã†â€™n/lÃƒÂ¡Ã‚ÂºÃ‚Â¯p Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚ÂºÃ‚Â·t."
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
            "1. SFG041 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â giÃƒÆ’Ã‚Â¡: chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u; chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u: gÃƒÂ¡Ã‚Â»Ã¢â‚¬â€ sÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“i; dÃƒÆ’Ã‚Â¹ng cho cÃƒâ€žÃ†â€™n hÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢ nhÃƒÂ¡Ã‚Â»Ã‚Â.",
            "2. SFG040 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â giÃƒÆ’Ã‚Â¡: chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u; chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u: chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u; phong cÃƒÆ’Ã‚Â¡ch tÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœi giÃƒÂ¡Ã‚ÂºÃ‚Â£n.",
            "3. SFG039 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â giÃƒÆ’Ã‚Â¡: chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u; chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u: gÃƒÂ¡Ã‚Â»Ã¢â‚¬â€ tÃƒÂ¡Ã‚Â»Ã‚Â± nhiÃƒÆ’Ã‚Âªn; hÃƒÂ¡Ã‚Â»Ã‚Â£p khÃƒÆ’Ã‚Â´ng gian rÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢ng.",
        ]
        return (
            "[stub][general_compare]\n"
            f"NguÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“n dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u: {data_provider}. No purchase request.\n"
            "TiÃƒÆ’Ã‚Âªu chÃƒÆ’Ã‚Â­ so sÃƒÆ’Ã‚Â¡nh: giÃƒÆ’Ã‚Â¡, chÃƒÂ¡Ã‚ÂºÃ‚Â¥t liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u, kÃƒÆ’Ã‚Â­ch thÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºc/phong cÃƒÆ’Ã‚Â¡ch/mÃƒÂ¡Ã‚Â»Ã‚Â¥c Ãƒâ€žÃ¢â‚¬ËœÃƒÆ’Ã‚Â­ch dÃƒÆ’Ã‚Â¹ng.\n"
            "CÃƒÆ’Ã‚Â¡c lÃƒÂ¡Ã‚Â»Ã‚Â±a chÃƒÂ¡Ã‚Â»Ã‚Ân so sÃƒÆ’Ã‚Â¡nh:\n"
            + "\n".join(options)
            + "\nKÃƒÂ¡Ã‚ÂºÃ‚Â¿t luÃƒÂ¡Ã‚ÂºÃ‚Â­n trung lÃƒÂ¡Ã‚ÂºÃ‚Â­p: SFG041 hÃƒÂ¡Ã‚Â»Ã‚Â£p khÃƒÆ’Ã‚Â´ng gian nhÃƒÂ¡Ã‚Â»Ã‚Â; SFG039 hÃƒÂ¡Ã‚Â»Ã‚Â£p khÃƒÆ’Ã‚Â´ng gian rÃƒÂ¡Ã‚Â»Ã¢â€žÂ¢ng; cÃƒÆ’Ã‚Â¡c thÃƒÆ’Ã‚Â´ng sÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœ thiÃƒÂ¡Ã‚ÂºÃ‚Â¿u Ãƒâ€žÃ¢â‚¬ËœÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Â£c ghi lÃƒÆ’Ã‚Â  'chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u'.\n"
            f"{common}"
        )

    if mode == ChatMode.MARKET_PRICE.value:
        candidate_price = _extract_candidate_price_vnd(messages[-1].get("content", "") if messages else "")
        if price_values:
            min_price = min(price_values)
            max_price = max(price_values)
            range_text = _format_vnd_range(min_price, max_price)
            if candidate_price is None:
                judgement = "chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ giÃƒÆ’Ã‚Â¡ ngÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âi dÃƒÆ’Ã‚Â¹ng cung cÃƒÂ¡Ã‚ÂºÃ‚Â¥p Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ nhÃƒÂ¡Ã‚ÂºÃ‚Â­n xÃƒÆ’Ã‚Â©t cao/thÃƒÂ¡Ã‚ÂºÃ‚Â¥p/bÃƒÆ’Ã‚Â¬nh thÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âng."
            elif candidate_price < min_price:
                judgement = "mÃƒÂ¡Ã‚Â»Ã‚Â©c giÃƒÆ’Ã‚Â¡ ngÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âi dÃƒÆ’Ã‚Â¹ng Ãƒâ€žÃ¢â‚¬ËœÃƒâ€ Ã‚Â°a ra Ãƒâ€žÃ¢â‚¬Ëœang thÃƒÂ¡Ã‚ÂºÃ‚Â¥p hÃƒâ€ Ã‚Â¡n khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng tham chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u."
            elif candidate_price > max_price:
                judgement = "mÃƒÂ¡Ã‚Â»Ã‚Â©c giÃƒÆ’Ã‚Â¡ ngÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âi dÃƒÆ’Ã‚Â¹ng Ãƒâ€žÃ¢â‚¬ËœÃƒâ€ Ã‚Â°a ra Ãƒâ€žÃ¢â‚¬Ëœang cao hÃƒâ€ Ã‚Â¡n khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng tham chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u."
            else:
                judgement = "mÃƒÂ¡Ã‚Â»Ã‚Â©c giÃƒÆ’Ã‚Â¡ ngÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âi dÃƒÆ’Ã‚Â¹ng Ãƒâ€žÃ¢â‚¬ËœÃƒâ€ Ã‚Â°a ra Ãƒâ€žÃ¢â‚¬Ëœang trong khoÃƒÂ¡Ã‚ÂºÃ‚Â£ng tham chiÃƒÂ¡Ã‚ÂºÃ‚Â¿u."
        else:
            range_text = "chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u do thiÃƒÂ¡Ã‚ÂºÃ‚Â¿u nguÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“n giÃƒÆ’Ã‚Â¡ cÃƒÆ’Ã‚Â³ cÃƒÂ¡Ã‚ÂºÃ‚Â¥u trÃƒÆ’Ã‚Âºc."
            judgement = "chÃƒâ€ Ã‚Â°a Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã‚Â§ dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ kÃƒÂ¡Ã‚ÂºÃ‚Â¿t luÃƒÂ¡Ã‚ÂºÃ‚Â­n giÃƒÆ’Ã‚Â¡ cao/thÃƒÂ¡Ã‚ÂºÃ‚Â¥p/bÃƒÆ’Ã‚Â¬nh thÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âng."

        warnings = []
        if debug_trace.get("used_mock_price_data"):
            warnings.append("dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u hiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n tÃƒÂ¡Ã‚ÂºÃ‚Â¡i lÃƒÆ’Ã‚Â  mock/demo, khÃƒÆ’Ã‚Â´ng phÃƒÂ¡Ã‚ÂºÃ‚Â£i giÃƒÆ’Ã‚Â¡ thÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¹ trÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Âng xÃƒÆ’Ã‚Â¡c nhÃƒÂ¡Ã‚ÂºÃ‚Â­n")
        if not debug_trace.get("external_price_refs"):
            warnings.append("chÃƒâ€ Ã‚Â°a Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã‚Â§ nguÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“n giÃƒÆ’Ã‚Â¡ Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ kÃƒÂ¡Ã‚ÂºÃ‚Â¿t luÃƒÂ¡Ã‚ÂºÃ‚Â­n chÃƒÂ¡Ã‚ÂºÃ‚Â¯c chÃƒÂ¡Ã‚ÂºÃ‚Â¯n")
        if not warnings:
            warnings.append("khÃƒÆ’Ã‚Â´ng cÃƒÆ’Ã‚Â³ cÃƒÂ¡Ã‚ÂºÃ‚Â£nh bÃƒÆ’Ã‚Â¡o bÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¢ sung")

        return (
            "[stub][market_price]\n"
            f"NguÃƒÂ¡Ã‚Â»Ã¢â‚¬Å“n dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u dÃƒÆ’Ã‚Â¹ng: {data_provider} (price_provider={price_provider}).\n"
            f"KhoÃƒÂ¡Ã‚ÂºÃ‚Â£ng giÃƒÆ’Ã‚Â¡ tham khÃƒÂ¡Ã‚ÂºÃ‚Â£o: {range_text}\n"
            f"NhÃƒÂ¡Ã‚ÂºÃ‚Â­n xÃƒÆ’Ã‚Â©t mÃƒÂ¡Ã‚Â»Ã‚Â©c giÃƒÆ’Ã‚Â¡: {judgement}\n"
            f"CÃƒÂ¡Ã‚ÂºÃ‚Â£nh bÃƒÆ’Ã‚Â¡o dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u: {'; '.join(warnings)}.\n"
            "KhÃƒÆ’Ã‚Â´ng gÃƒÂ¡Ã‚Â»Ã‚Â£i ÃƒÆ’Ã‚Â½ mua sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m cÃƒÂ¡Ã‚Â»Ã‚Â¥ thÃƒÂ¡Ã‚Â»Ã†â€™. No purchase request.\n"
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
    if msg_norm in {"/reset", "reset", "/new", "new", "/end", "end", "new scenario"}:
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
            "debug": _with_production_debug_panel(debug_trace),
        })

        return ChatResp(
            reply="Xong.",
            latency_ms=0,
            model="system",
            adapter=adapter,
            debug=_with_production_debug_panel(debug_trace),
        )

    # Phase 11C: initialize interpreter + consultation vars early (used in debug_trace for all paths)
    _interpreter_result = None
    _interpreter_used = False
    _interpreter_attempted = False
    _interpreter_called = False
    _interpreter_skip_reason = ""
    _interpreter_error_type = ""
    _interpreter_intent = None
    _slots_after_interpreter = None
    _deterministic_slots = {}  # Phase 11C: always define for debug trace
    # Phase 11C: consultation debug vars
    _consultation_attempted = False
    _consultation_called = False
    _consultation_skip_reason = ""
    _consultation_error_type = ""
    _tenant_sales_agent_brief: Dict[str, Any] = {}
    _tenant_sales_agent_decision = None
    _tenant_sales_agent_force_retrieve = False
    _memory_product_focus_changed = False
    _memory_product_focus_before = ""
    _memory_product_focus_after = ""
    if mode in {ChatMode.GENERAL_COMPARE.value, ChatMode.MARKET_PRICE.value} and _conversation_orchestrator_enabled():
        def _non_sales_orchestrator_retrieve(query: str, filters: Dict[str, Any]) -> List[Any]:
            kb = get_kb_for_mode(retrieval_mode)
            if kb is None:
                return []
            hits = search_hits(
                kb,
                query or req.message,
                k=max(1, retrieval_top_k),
                tenant_id=req.tenant_id,
            )
            requested = (
                (filters or {}).get("product_category")
                or (filters or {}).get("product_type")
                or (filters or {}).get("product_focus")
            )
            if requested:
                hits = filter_by_category(hits, requested)
            return hits

        st = get_state(conv_id)
        orch_memory = _mask_contact_in_value(dict(st.slots or {}))
        orchestrator = ConversationOrchestrator(ClaudeLLMClient())
        orch_result = orchestrator.run(
            OrchestratorRequest(
                message=req.message,
                mode=mode,
                channel=req.channel,
                tenant_id=req.tenant_id,
                conversation_id=req.conversation_id,
            ),
            OrchestratorContext(
                memory=dict(orch_memory),
                retrieval_tool=_non_sales_orchestrator_retrieve,
            ),
        )
        for _k, _v in (orch_result.updated_memory or {}).items():
            if _k not in {"phone", "email"} and _v not in (None, "", [], {}):
                st.slots[_k] = _v
        st.stage = mode
        try:
            save_turn(conv_id, req.message, orch_result.reply[:1200])
        except Exception:
            pass

        _planner_decision = orch_result.debug.get("planner_decision") or {}
        _planner_filters = _planner_decision.get("filters") or {}
        debug_trace = _build_debug_trace(
            mode=mode,
            stage=mode,
            slots=_mask_contact_in_value(dict(st.slots or {})),
            retrieved_docs=len(orch_result.retrieval_hits),
            retrieval_mode=retrieval_mode,
            answer_mode=orch_result.answer_mode,
            template_reason="conversation_orchestrator",
            llm_enabled=bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")),
            llm_provider="claude",
            llm_model=os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6",
            llm_call_attempted=bool(orch_result.debug.get("planner_attempted") or orch_result.debug.get("finalizer_attempted")),
            llm_called=bool(orch_result.debug.get("planner_called") or orch_result.debug.get("finalizer_called")),
            llm_skip_reason=orch_result.debug.get("planner_skip_reason") or orch_result.debug.get("finalizer_skip_reason") or "",
            llm_error_type=orch_result.debug.get("planner_error_type") or orch_result.debug.get("finalizer_error_type") or "",
            retrieval_query=_planner_decision.get("search_query", req.message),
            requested_category=_planner_filters.get("product_category") or _planner_filters.get("product_type") or "",
            slots_snapshot=_mask_contact_in_value(dict(st.slots or {})),
        )
        debug_trace.update({
            **orch_result.debug,
            "orchestrator_enabled": True,
            "retrieval_count": len(orch_result.retrieval_hits),
            "sales_mode": "off",
            "sales_boundary": "non_sales_no_lead",
            "trigger_purchase_request": False,
            "real_claude_response_attempted": False,
            "real_claude_response_called": False,
            "real_claude_response_mode": "not_applicable",
            "real_claude_skip_reason": orch_result.debug.get("planner_skip_reason") or orch_result.debug.get("finalizer_skip_reason") or "",
            "real_claude_error_type": orch_result.debug.get("planner_error_type") or orch_result.debug.get("finalizer_error_type") or None,
        })
        log_event({
            "event": "chat",
            "question": req.message,
            "answer": orch_result.reply[:1200],
            "latency_ms": 0,
            "model": "conversation-orchestrator",
            "adapter": None,
            "provider": "claude",
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "context_length": 0,
            "kb_loaded": get_kb_for_mode(retrieval_mode) is not None,
            "sales_stage": None,
            "sales_slots": {},
            "debug": _with_production_debug_panel(debug_trace),
        })
        return ChatResp(
            reply=orch_result.reply[:1200],
            latency_ms=0,
            model="conversation-orchestrator",
            adapter=None,
            trigger_purchase_request=False,
            captured_phone=None,
            captured_name=None,
            debug=_with_production_debug_panel(debug_trace),
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
                    answer_mode="sales-template",
                    template_reason="pending_confirmation",
                    llm_enabled=False,
                    llm_provider="none",
                    llm_call_attempted=False,
                    llm_called=False,
                    llm_skip_reason="template_route",
                    retrieval_query="",
                    requested_category="",
                    slots_snapshot=dict(sales_state.slots if sales_state else {}),
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
                    debug=_with_production_debug_panel(debug_trace),
                )
        # Phase 11C: deterministic extract + Claude state interpreter BEFORE action selection
        _deterministic_slots = extract_sales_slots(req.message)
        if _is_tenant_sales_mode(mode) and sales_enabled:
            _interpreter_attempted = True
            _api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
            # Phase 11C: enable interpreter when Claude configured OR in test mode (monkeypatch)
            _claude_configured = bool(_api_key) or _is_test_mode()
            _use_interpreter_flag = os.getenv("SALES_USE_LLM_STATE_INTERPRETER", "true").lower() in ("1", "true", "yes", "on")
            if _claude_configured and _use_interpreter_flag:
                try:
                    _interpreter_result = call_state_interpreter(
                        req.message, sales_state.slots,
                        api_key=_api_key,
                        api_model=os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6",
                        api_base_url=os.getenv("CLAUDE_API_BASE_URL") or "https://api.anthropic.com",
                    )
                    if _interpreter_result is not None:
                        _interpreter_called = True
                        _interpreter_intent = _interpreter_result.get("intent", "unknown")
                        apply_interpreter_to_state(sales_state, _interpreter_result, _deterministic_slots)
                        _interpreter_used = True
                        # Phase 11C: snapshot after interpreter (for debug)
                        _slots_after_interpreter = dict(sales_state.slots)
                    else:
                        _interpreter_skip_reason = "null_response_or_invalid_json"
                except Exception as _iexc:
                    _interpreter_error_type = _iexc.__class__.__name__
                    _interpreter_skip_reason = "fallback_after_error"
            else:
                if not _use_interpreter_flag:
                    _interpreter_skip_reason = "feature_flag_disabled"
                elif not _api_key and not _is_test_mode():
                    _interpreter_skip_reason = "missing_api_key"
                else:
                    _interpreter_skip_reason = "llm_not_configured"
        # Phase 11C: Always apply deterministic on top of interpreter result (or as base)
        # Build sales_result safely from state (never raw interpreter slot_updates)
        if not _interpreter_used:
            sales_result = apply_message_to_state(sales_state, req.message)
        else:
            # Phase 11C: Build from final safe state + deterministic (no raw LLM leakage)
            sales_result = {"slots": {}, "resolved_product": None}
            # Start from current state slots (already safely updated by apply_interpreter_to_state)
            for _k, _v in (sales_state.slots or {}).items():
                if _v is not None and _v not in ("", [], {}):
                    sales_result["slots"][_k] = _v
            # Overlay deterministic (authoritative)
            for _k, _v in (_deterministic_slots or {}).items():
                if _v is not None and _v not in ("", [], {}):
                    sales_result["slots"][_k] = _v
                else:
                    sales_result["slots"].pop(_k, None)
            _ii = _interpreter_intent or "consultation"
            sales_result["slots"]["intents"] = [_ii] if _ii else ["unknown"]
            sales_result["slots"]["intent"] = _ii
        if _is_tenant_sales_mode(mode) and sales_state is not None:
            _memory_product_focus_before = (
                sales_state.slots.get("product_category_prev")
                or sales_state.slots.get("product_type_prev")
                or sales_state.slots.get("product_category")
                or sales_state.slots.get("product_type")
                or ""
            )
            _tenant_sales_agent_brief = _agent_update_customer_brief(
                sales_state,
                req.message,
                sales_result.get("slots") or {},
            )
            _memory_product_focus_after = _tenant_sales_agent_brief.get("product_focus") or ""
            _memory_product_focus_changed = bool(
                _memory_product_focus_after
                and _memory_product_focus_before
                and _fold_sku(str(_memory_product_focus_after)) != _fold_sku(str(_memory_product_focus_before))
            )
            if _memory_product_focus_changed:
                sales_state.selected_products = []
                sales_state.last_recommended_products = []
                sales_state.purchase_request = None
                sales_state.confirmation_status = "none"
                sales_state.handoff_required = False
                sales_state.handoff_status = "not_ready"
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
        if _is_tenant_sales_mode(mode) and sales_state is not None:
            if (_interpreter_result or {}).get("response_mode") == "consultation_llm":
                _tenant_sales_agent_decision = None
            else:
                _tenant_sales_agent_decision = _agent_decide_next_response(
                    req.message,
                    _tenant_sales_agent_brief or (sales_state.slots.get(TENANT_SALES_BRIEF_SLOT) or {}),
                    sales_action_taken,
                    sales_result.get("slots") or {},
                )
            if getattr(_tenant_sales_agent_decision, "action", "") == "retrieve":
                sales_action_taken = "none"
                _tenant_sales_agent_force_retrieve = True
        _save_sales_state(sales_state)
        # Phase 11D: compute force flag early so we enter early-return block for interpreter-driven consultation
        _force_consult_from_interpreter = (_interpreter_result or {}).get("should_ask") or (_interpreter_result or {}).get("response_mode") == "consultation_llm"
        _orchestrator_enabled = _conversation_orchestrator_enabled()
        _transactional_actions = {
            "ask_contact",
            "ask_confirmation",
            "handoff",
            "handoff_sent",
            "handoff_failed",
            "handoff_already_sent",
            "confirmation_cancelled",
            "confirmation_without_pending",
            "ask_product",
            "cancelled",
        }
        _orchestrator_tenant_turn = (
            _is_tenant_sales_mode(mode)
            and sales_mode == "active"
            and _orchestrator_enabled
            and sales_action_taken not in _transactional_actions
        )
        if _orchestrator_tenant_turn and sales_state is not None:
            def _orchestrator_retrieve(query: str, filters: Dict[str, Any]) -> List[Any]:
                kb = get_kb_for_mode(retrieval_mode)
                if kb is None:
                    return []
                hits = search_hits(
                    kb,
                    query or req.message,
                    k=max(1, retrieval_top_k),
                    tenant_id=req.tenant_id,
                )
                requested = (
                    (filters or {}).get("product_category")
                    or (filters or {}).get("product_type")
                    or (filters or {}).get("product_focus")
                )
                if requested:
                    hits = filter_by_category(hits, requested)
                return hits

            orchestrator = ConversationOrchestrator(ClaudeLLMClient())
            _orch_memory = _mask_contact_in_value(dict(sales_state.slots or {}))
            _orch_result = orchestrator.run(
                OrchestratorRequest(
                    message=req.message,
                    mode=mode,
                    channel=req.channel,
                    tenant_id=req.tenant_id,
                    conversation_id=req.conversation_id,
                ),
                OrchestratorContext(
                    memory=dict(_orch_memory),
                    retrieval_tool=_orchestrator_retrieve,
                ),
            )
            _old_product_focus = _memory_product_focus_before or (
                sales_state.slots.get("product_category")
                or sales_state.slots.get("product_type")
                or ""
            )
            _new_product_focus = (
                (_orch_result.updated_memory or {}).get("product_focus")
                or _memory_product_focus_after
                or ""
            )
            _product_focus_changed = _memory_product_focus_changed or bool(
                _new_product_focus
                and _old_product_focus
                and _fold_sku(str(_new_product_focus)) != _fold_sku(str(_old_product_focus))
            )
            if _product_focus_changed:
                sales_state.selected_products = []
                sales_state.last_recommended_products = []
                sales_state.purchase_request = None
                sales_state.confirmation_status = "none"
                sales_state.handoff_required = False
                sales_state.handoff_status = "not_ready"
            for _k, _v in (_orch_result.updated_memory or {}).items():
                if _k not in {"phone", "email"} and _v not in (None, "", [], {}):
                    sales_state.slots[_k] = _v
            if (_orch_result.updated_memory or {}).get("product_focus"):
                sales_state.slots["product_category"] = _orch_result.updated_memory["product_focus"]
                sales_state.slots["product_type"] = _orch_result.updated_memory["product_focus"]
            if _orch_result.retrieval_hits:
                update_recommended_products(sales_state, _orch_result.retrieval_hits)
            _save_sales_state(sales_state)

            debug_trace = _build_debug_trace(
                mode=mode,
                stage=_mode_default_stage(mode),
                slots={},
                retrieved_docs=len(_orch_result.retrieval_hits),
                retrieval_mode=retrieval_mode,
                answer_mode=_orch_result.answer_mode,
                template_reason="conversation_orchestrator",
                llm_enabled=bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")),
                llm_provider="claude",
                llm_call_attempted=bool(_orch_result.debug.get("planner_attempted") or _orch_result.debug.get("finalizer_attempted")),
                llm_called=bool(_orch_result.debug.get("planner_called") or _orch_result.debug.get("finalizer_called")),
                llm_skip_reason=_orch_result.debug.get("planner_skip_reason") or _orch_result.debug.get("finalizer_skip_reason") or "",
                llm_error_type=_orch_result.debug.get("planner_error_type") or _orch_result.debug.get("finalizer_error_type") or "",
                retrieval_query=(_orch_result.debug.get("planner_decision") or {}).get("search_query", req.message),
                requested_category=(
                    ((_orch_result.debug.get("planner_decision") or {}).get("filters") or {}).get("product_category")
                    or ((_orch_result.debug.get("planner_decision") or {}).get("filters") or {}).get("product_type")
                    or ""
                ),
                slots_snapshot=_mask_contact_in_value(dict(sales_state.slots or {})),
            )
            debug_trace.update(_sales_debug_payload(
                sales_mode,
                sales_state,
                sales_result,
                sales_action_taken,
                persistent=sales_state_persistent,
                state_warning=sales_state_warning,
            ))
            debug_trace.update({
                **_orch_result.debug,
                "orchestrator_enabled": True,
                "retrieval_count": len(_orch_result.retrieval_hits),
                "state_interpreter_llm_attempted": _interpreter_attempted,
                "state_interpreter_llm_called": _interpreter_called,
                "state_interpreter_skip_reason": _interpreter_skip_reason,
                "state_interpreter_error_type": _interpreter_error_type,
                "state_interpreter_intent": _interpreter_intent or "",
                "deterministic_slots": _mask_contact_in_value(dict(_deterministic_slots or {})),
                "slots_snapshot_after_interpreter": _mask_contact_in_value(dict(_slots_after_interpreter or (sales_state.slots if sales_state else {}))),
                "consultation_llm_attempted": False,
                "consultation_llm_called": False,
                "consultation_llm_skip_reason": "orchestrator_route",
                "consultation_llm_error_type": "",
                "tenant_sales_agent_enabled": True,
                "tenant_sales_agent_action": getattr(_tenant_sales_agent_decision, "action", "") if _tenant_sales_agent_decision else "",
                "tenant_sales_agent_reason": getattr(_tenant_sales_agent_decision, "reason", "") if _tenant_sales_agent_decision else "",
                "customer_brief": _mask_contact_in_value(_orch_result.updated_memory or _tenant_sales_agent_brief),
                "memory_product_focus_changed": _product_focus_changed,
                "memory_product_focus_before": _old_product_focus,
                "memory_product_focus_after": _new_product_focus,
                "real_claude_response_attempted": False,
                "real_claude_response_called": False,
                "real_claude_response_mode": "not_applicable",
                "real_claude_skip_reason": _orch_result.debug.get("planner_skip_reason") or _orch_result.debug.get("finalizer_skip_reason") or "not_applicable",
                "real_claude_error_type": _orch_result.debug.get("planner_error_type") or _orch_result.debug.get("finalizer_error_type") or None,
            })
            try:
                save_turn(conv_id, req.message, _orch_result.reply[:1200])
            except Exception:
                pass
            return ChatResp(
                reply=_orch_result.reply[:1200],
                latency_ms=0,
                model="conversation-orchestrator",
                adapter=None,
                trigger_purchase_request=False,
                debug=_with_production_debug_panel(debug_trace),
            )
        if getattr(_tenant_sales_agent_decision, "action", "") == "advice" and sales_mode == "active":
            _claude_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
            debug_trace = _build_debug_trace(
                mode=mode,
                stage=_mode_default_stage(mode),
                slots={},
                retrieval_mode=retrieval_mode,
                answer_mode="tenant_sales_agent",
                template_reason="agent_advice",
                llm_enabled=bool(_claude_key),
                llm_provider="claude" if _claude_key else "none",
                llm_call_attempted=False,
                llm_called=False,
                llm_skip_reason="not_yet" if _claude_key else "missing_api_key",
                retrieval_query=req.message,
                requested_category=(sales_state.slots.get("product_category") if sales_state else "") or "",
                slots_snapshot=_mask_contact_in_value(dict(sales_state.slots if sales_state else {})),
            )
            debug_trace.update(_sales_debug_payload(
                sales_mode,
                sales_state,
                sales_result,
                sales_action_taken,
                persistent=sales_state_persistent,
                state_warning=sales_state_warning,
            ))
            debug_trace.update({
                "tenant_sales_agent_enabled": True,
                "tenant_sales_agent_action": "advice",
                "tenant_sales_agent_reason": getattr(_tenant_sales_agent_decision, "reason", ""),
                "customer_brief": _mask_contact_in_value(_tenant_sales_agent_brief),
                "state_interpreter_llm_attempted": _interpreter_attempted,
                "state_interpreter_llm_called": _interpreter_called,
                "state_interpreter_skip_reason": _interpreter_skip_reason,
                "state_interpreter_error_type": _interpreter_error_type,
                "state_interpreter_intent": _interpreter_intent or "",
                "state_interpreter_confidence": float(_interpreter_result.get("confidence", 0.0)) if _interpreter_result else 0.0,
                "deterministic_slots": _mask_contact_in_value(dict(_deterministic_slots or {})),
                "slots_snapshot_after_interpreter": _mask_contact_in_value(dict(_slots_after_interpreter or (sales_state.slots if sales_state else {}))),
                "consultation_llm_attempted": _consultation_attempted,
                "consultation_llm_called": _consultation_called,
                "consultation_llm_skip_reason": _consultation_skip_reason,
                "consultation_llm_error_type": _consultation_error_type,
                "real_claude_response_attempted": False,
                "real_claude_response_called": False,
                "real_claude_response_mode": "not_applicable",
                "real_claude_skip_reason": "not_applicable",
                "real_claude_error_type": None,
            })
            reply = None
            fallback_reply = _agent_compose_advice(req.message, _tenant_sales_agent_brief)
            if _claude_key and not _is_pytest_blocking_real_claude():
                debug_trace["real_claude_response_attempted"] = True
                debug_trace["llm_call_attempted"] = True
                try:
                    _prompt = _build_tenant_sales_advice_prompt(
                        req.message,
                        _tenant_sales_agent_brief,
                        sales_state.slots if sales_state else {},
                    )
                    _t0c = time.time()
                    _cout, _cerr, _cprev = _call_claude_api(
                        _prompt,
                        _claude_key,
                        os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6",
                        os.getenv("CLAUDE_API_BASE_URL") or "https://api.anthropic.com",
                        700,
                        0.75,
                        1.0,
                        30,
                    )
                    if _cout and not _cerr:
                        reply = _cout.strip()
                        debug_trace.update({
                            "answer_mode": "claude_tenant_sales",
                            "template_reason": "claude_advice",
                            "llm_called": True,
                            "llm_skip_reason": "",
                            "real_claude_response_called": True,
                            "real_claude_response_mode": "advice",
                            "real_claude_skip_reason": "",
                            "real_claude_error_type": None,
                        })
                        try:
                            log_event({
                                "event": "tenant_sales_claude_advice",
                                "conversation_id": conv_id,
                                "latency_ms": int((time.time() - _t0c) * 1000),
                            })
                        except Exception:
                            pass
                        print(f"[LLM] tenant_sales_response success mode=advice latency_ms={int((time.time()-_t0c)*1000)}")
                    else:
                        debug_trace.update({
                            "real_claude_response_called": False,
                            "real_claude_response_mode": "advice",
                            "real_claude_skip_reason": "claude_error_or_empty",
                            "real_claude_error_type": _cerr or "empty",
                            "llm_skip_reason": "claude_error_or_empty",
                        })
                        print(f"[LLM] tenant_sales_response failed mode=advice error_type={debug_trace.get('real_claude_error_type')}")
                except Exception as _aexc:
                    debug_trace.update({
                        "real_claude_response_called": False,
                        "real_claude_response_mode": "advice",
                        "real_claude_skip_reason": "exception",
                        "real_claude_error_type": _aexc.__class__.__name__,
                        "llm_skip_reason": "fallback_after_error",
                    })
                    print(f"[LLM] tenant_sales_response failed mode=advice error_type={_aexc.__class__.__name__}")
            else:
                if _is_pytest_blocking_real_claude():
                    debug_trace["real_claude_skip_reason"] = "pytest_real_llm_disabled"
                    debug_trace["llm_skip_reason"] = "pytest_real_llm_disabled"
                else:
                    debug_trace["real_claude_skip_reason"] = "missing_api_key"
                    debug_trace["llm_skip_reason"] = "missing_api_key"
                print(f"[LLM] tenant_sales_response skipped mode=advice reason={debug_trace.get('real_claude_skip_reason')}")
            if not reply:
                reply = fallback_reply
            try:
                save_turn(conv_id, req.message, reply[:1200])
            except Exception:
                pass
            _save_sales_state(sales_state)
            return ChatResp(
                reply=reply[:1200],
                latency_ms=0,
                model="claude-tenant-sales" if debug_trace.get("real_claude_response_called") else "tenant-sales-agent",
                adapter=None,
                trigger_purchase_request=False,
                debug=_with_production_debug_panel(debug_trace),
            )
        if sales_mode == "active" and (sales_action_taken != "none" or bool(_force_consult_from_interpreter) or sales_action_taken == "ask_discovery"):
            debug_trace = _build_debug_trace(
                mode=mode,
                stage=_mode_default_stage(mode),
                slots={},
                retrieval_mode=retrieval_mode,
                answer_mode="sales-template",
                template_reason="sales_action",
                llm_enabled=False,
                llm_provider="none",
                llm_call_attempted=False,
                llm_called=False,
                llm_skip_reason="template_route",
                retrieval_query=(lambda q: re.sub(r'[\w\.-]+@[\w\.-]+', '***', re.sub(r'\d[\d\s\.\-]{7,}\d', '***', q or '')))(locals().get("_tenant_sales_search_query") or req.message),
                requested_category=(locals().get("_tenant_sales_requested_cat") or ""),
                slots_snapshot=(lambda s: {k: ("***" if k in ("phone", "email") else v) for k, v in (s or {}).items()})(sales_state.slots if sales_state else {}),
            )
            debug_trace.update(_sales_debug_payload(
                sales_mode,
                sales_state,
                sales_result,
                sales_action_taken,
                persistent=sales_state_persistent,
                state_warning=sales_state_warning,
            ))
            # Phase 10G: fill debug for ask_discovery early return
            debug_trace.setdefault("answer_mode", "sales-template")
            debug_trace.setdefault("template_reason", "ask_discovery")
            debug_trace.setdefault("llm_enabled", False)
            debug_trace.setdefault("llm_provider", "none")
            debug_trace.setdefault("llm_call_attempted", False)
            debug_trace.setdefault("llm_called", False)
            debug_trace.setdefault("llm_skip_reason", "template_route")
            debug_trace.setdefault("retrieval_query", (locals().get("_tenant_sales_search_query") or req.message))
            debug_trace.setdefault("requested_category", (locals().get("_tenant_sales_requested_cat") or ""))
            # Phase 10G: snapshot slots but mask contact details for privacy
            _snap = dict(sales_state.slots if sales_state else {})
            for _k in ("phone", "email"):
                if _k in _snap:
                    _snap[_k] = "***"
            debug_trace.setdefault("slots_snapshot", _snap)
            # Phase 11C: ensure interpreter debug fields are present even in early return paths
            debug_trace.setdefault("state_interpreter_llm_attempted", _interpreter_attempted)
            debug_trace.setdefault("state_interpreter_llm_called", _interpreter_called)
            debug_trace.setdefault("state_interpreter_skip_reason", _interpreter_skip_reason)
            debug_trace.setdefault("state_interpreter_error_type", _interpreter_error_type)
            debug_trace.setdefault("state_interpreter_intent", _interpreter_intent or "")
            debug_trace.setdefault("state_interpreter_confidence", float(_interpreter_result.get("confidence", 0.0)) if _interpreter_result else 0.0)
            debug_trace.setdefault("deterministic_slots", _mask_contact_in_value(dict(_deterministic_slots or {})))
            debug_trace.setdefault("slots_snapshot_after_interpreter", _mask_contact_in_value(dict(_slots_after_interpreter or (sales_state.slots if sales_state else {}))))
            # Phase 11C: consultation LLM after interpreter/action decision
            # Only for response wording when action is ask/consultation
            # Must not decide product list, must not mutate state, must not invent products
            _llm_reply = None
            _llm_consultation_used = False
            _consultation_attempted = False
            _consultation_called = False
            _consultation_skip_reason = ""
            _consultation_error_type = ""
            # Phase 11C: consultation LLM for ask_discovery OR when interpreter explicitly requests it
            _force_consult_from_interpreter = (_interpreter_result or {}).get("should_ask") or (_interpreter_result or {}).get("response_mode") == "consultation_llm"
            if (sales_action_taken in ("ask_discovery",) or _force_consult_from_interpreter) and sales_state:
                _consultation_attempted = True
                _api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
                if _api_key or _is_test_mode():
                    try:
                        _consult_text = _call_consultation_llm(
                            req.message,
                            sales_state.slots,
                            list(sales_state.slots.get("consultation_missing_slots", [])),
                            api_key=_api_key,
                            api_model=os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6",
                            api_base_url=os.getenv("CLAUDE_API_BASE_URL") or "https://api.anthropic.com",
                        )
                        if _consult_text:
                            _llm_reply = _consult_text
                            _llm_consultation_used = True
                            _consultation_called = True
                        else:
                            _consultation_skip_reason = "null_response"
                    except Exception as _cexc:
                        _consultation_error_type = _cexc.__class__.__name__
                        _consultation_skip_reason = "fallback_after_error"
                else:
                    _consultation_skip_reason = "missing_api_key"
            # Phase 11D: Prefer real Claude for tenant_sales consultation if configured.
            _real_claude_consult_attempted = False
            _real_claude_consult_called = False
            _real_claude_consult_skip = ""
            _real_claude_consult_err = ""
            _api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
            _force_consult_from_interpreter = (_interpreter_result or {}).get("should_ask") or (_interpreter_result or {}).get("response_mode") == "consultation_llm"
            if (sales_action_taken in ("ask_discovery",) or _force_consult_from_interpreter) and sales_state:
                if _api_key and not _is_pytest_blocking_real_claude():
                    try:
                        _real_claude_consult_attempted = True
                        _c_prompt = _build_tenant_sales_consult_prompt(
                            req.message, sales_state.slots,
                            list(sales_state.slots.get("consultation_missing_slots", []))
                        )
                        _cout, _cerr, _cprev = _call_claude_api(
                            _c_prompt, _api_key,
                            os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6",
                            os.getenv("CLAUDE_API_BASE_URL") or "https://api.anthropic.com",
                            512, 0.7, 1.0, 30
                        )
                        if _cout and not _cerr:
                            reply = _cout.strip()
                            _real_claude_consult_called = True
                            debug_trace["real_claude_response_attempted"] = True
                            debug_trace["real_claude_response_called"] = True
                            debug_trace["real_claude_response_mode"] = "consultation"
                            debug_trace["answer_mode"] = "claude_tenant_sales"
                            try:
                                log_event({"event": "tenant_sales_claude_consult", "conversation_id": conv_id})
                            except Exception:
                                pass
                            print(f"[LLM] tenant_sales_response success mode=consultation")
                        else:
                            _real_claude_consult_skip = "claude_error_or_empty"
                            _real_claude_consult_err = _cerr or "empty"
                            debug_trace["real_claude_response_attempted"] = True
                            debug_trace["real_claude_response_called"] = False
                            debug_trace["real_claude_skip_reason"] = _real_claude_consult_skip
                            debug_trace["real_claude_error_type"] = _real_claude_consult_err
                            print(f"[LLM] tenant_sales_response failed error_type={_real_claude_consult_err}")
                    except Exception as _eex:
                        _real_claude_consult_skip = "exception"
                        _real_claude_consult_err = _eex.__class__.__name__
                        debug_trace["real_claude_response_attempted"] = True
                        debug_trace["real_claude_response_called"] = False
                        debug_trace["real_claude_skip_reason"] = _real_claude_consult_skip
                        debug_trace["real_claude_error_type"] = _real_claude_consult_err
                        print(f"[LLM] tenant_sales_response failed error_type={_real_claude_consult_err}")
                else:
                    if _is_pytest_blocking_real_claude():
                        debug_trace.setdefault("real_claude_response_attempted", False)
                        debug_trace["real_claude_skip_reason"] = "pytest_real_llm_disabled"
                    else:
                        debug_trace.setdefault("real_claude_response_attempted", False)
                        debug_trace["real_claude_skip_reason"] = "missing_api_key"
                    print(f"[LLM] tenant_sales_response skipped reason={debug_trace.get('real_claude_skip_reason')}")
            if not _real_claude_consult_called:
                # Fallback to previous interpreter LLM or template
                if (sales_action_taken in ("ask_discovery",) or _force_consult_from_interpreter) and sales_state:
                    _consultation_attempted = True
                    if _api_key or _is_test_mode():
                        try:
                            _consult_text = _call_consultation_llm(
                                req.message,
                                sales_state.slots,
                                list(sales_state.slots.get("consultation_missing_slots", [])),
                                api_key=_api_key,
                                api_model=os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6",
                                api_base_url=os.getenv("CLAUDE_API_BASE_URL") or "https://api.anthropic.com",
                            )
                            if _consult_text:
                                _llm_reply = _consult_text
                                _llm_consultation_used = True
                                _consultation_called = True
                            else:
                                _consultation_skip_reason = "null_response"
                        except Exception as _cexc:
                            _consultation_error_type = _cexc.__class__.__name__
                            _consultation_skip_reason = "fallback_after_error"
                    else:
                        _consultation_skip_reason = "missing_api_key"
                if _llm_consultation_used:
                    reply = _llm_reply
                    debug_trace["consultation_llm_attempted"] = True
                    debug_trace["consultation_llm_called"] = True
                    debug_trace["consultation_llm_skip_reason"] = ""
                    debug_trace["consultation_llm_error_type"] = ""
                    debug_trace["llm_called"] = True
                    debug_trace["llm_skip_reason"] = ""
                    debug_trace["answer_mode"] = "consultation_llm"
                else:
                    reply = render_sales_response(sales_action_taken, sales_draft, sales_state)
                    if _consultation_attempted:
                        debug_trace["consultation_llm_attempted"] = True
                        debug_trace["consultation_llm_called"] = _consultation_called
                        debug_trace["consultation_llm_skip_reason"] = _consultation_skip_reason
                        debug_trace["consultation_llm_error_type"] = _consultation_error_type
                if _real_claude_consult_attempted and not _real_claude_consult_called:
                    debug_trace.setdefault("real_claude_response_attempted", True)
                    debug_trace.setdefault("real_claude_response_called", False)
                    debug_trace.setdefault("real_claude_skip_reason", _real_claude_consult_skip or "fallback_after_error")
                    debug_trace.setdefault("real_claude_error_type", _real_claude_consult_err or "")
            try:
                save_turn(conv_id, req.message, reply[:1200])
            except Exception:
                pass
            _final_model = "claude-tenant-sales" if _real_claude_consult_called else ("consultation-llm" if _llm_consultation_used else "sales-template")
            return ChatResp(
                reply=reply[:1200],
                latency_ms=0,
                model=_final_model,
                adapter=None,
                trigger_purchase_request=False,
                debug=_with_production_debug_panel(debug_trace),
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
        # Phase 10G: fill debug for rule early return
        debug_trace.setdefault("answer_mode", "rule")
        debug_trace.setdefault("llm_enabled", False)
        debug_trace.setdefault("llm_provider", "none")
        debug_trace.setdefault("llm_call_attempted", False)
        debug_trace.setdefault("llm_called", False)
        debug_trace.setdefault("llm_skip_reason", "rule_route")
        debug_trace.setdefault("template_reason", "")
        debug_trace.setdefault("retrieval_query", req.message)
        debug_trace.setdefault("requested_category", "")
        debug_trace.setdefault("slots_snapshot", dict(slots_for_debug if 'slots_for_debug' in dir() else {}))
        log_event({
            "event": "rule_hit",
            "rule_type": rr["type"],
            "question": req.message,
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "debug": _with_production_debug_panel(debug_trace),
        })
        # Save turn (optional but useful for audit)
        try:
            save_turn(conv_id, req.message, rr["reply"])
        except Exception:
            pass
        return ChatResp(reply=rr["reply"], latency_ms=0, model="rule", adapter=adapter, debug=_with_production_debug_panel(debug_trace))

    # --- SALES FLOW: state/slots/stage (AFTER RULE layer) ---
    st = get_state(conv_id)

    # Default values for lead capture trigger (will be updated below)
    trigger_purchase_request = False
    captured_phone = None
    captured_name = None
    stage_for_debug = getattr(st, "stage", _mode_default_stage(mode))
    slots_for_debug: Dict[str, Any] = dict(getattr(st, "slots", {}) or {})

    # Phase 10G: initialize tenant_sales query vars early so debug traces can reference them
    _tenant_sales_requested_cat = None
    _tenant_sales_search_query = req.message
    _tenant_sales_claude_rewritten = None
    _tenant_sales_listing_claude_attempted = False
    _tenant_sales_listing_claude_called = False
    _tenant_sales_listing_claude_mode = ""
    _tenant_sales_listing_claude_skip_reason = ""
    _tenant_sales_listing_claude_error_type = None
    _tenant_sales_style_question_requested = _is_tenant_sales_mode(mode) and _tenant_sales_style_question(req.message)

    # Phase 11F: initialize debug_trace early (before any listing rewrite) with real_claude defaults
    debug_trace = _build_debug_trace(
        mode=mode,
        stage=stage_for_debug if 'stage_for_debug' in dir() else _mode_default_stage(mode),
        slots=slots_for_debug if 'slots_for_debug' in dir() else {},
        retrieval_mode=retrieval_mode,
        answer_mode="template",
        template_reason="early_init",
        llm_enabled=False,
        llm_provider="none",
        llm_call_attempted=False,
        llm_called=False,
        llm_skip_reason="not_yet",
        retrieval_query=req.message,
        requested_category="",
        slots_snapshot={},
    )
    # Phase 11F: initialize real_claude debug defaults
    debug_trace.setdefault("real_claude_response_attempted", False)
    debug_trace.setdefault("real_claude_response_called", False)
    debug_trace.setdefault("real_claude_response_mode", "not_applicable")
    debug_trace.setdefault("real_claude_skip_reason", "not_applicable")
    debug_trace.setdefault("real_claude_error_type", None)

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
        # Phase 9C: use sales_state for retrieval decision when available
        _rag_stage = (sales_state.current_stage if sales_state and _is_tenant_sales_mode(mode)
                      else stage_for_debug)
        _rag_slots = (dict(sales_state.slots) if sales_state and _is_tenant_sales_mode(mode)
                      else slots_for_debug)
        allow_rag = True if not _is_tenant_sales_mode(mode) else should_allow_retrieval(
            req.message,
            _rag_stage,
            _rag_slots,
        )
        if _tenant_sales_agent_force_retrieve:
            allow_rag = True
    except Exception:
        allow_rag = bool(_tenant_sales_agent_force_retrieve)

    active_kb = get_kb_for_mode(retrieval_mode)
    # Phase 8: build accumulated search query from sales state for tenant_sales retrieval
    _tenant_sales_requested_cat = None
    _tenant_sales_search_query = req.message
    if sales_enabled and _is_tenant_sales_mode(mode) and sales_state and sales_state.slots:
        state_slots = sales_state.slots
        cat = state_slots.get("product_category") or state_slots.get("product_type") or ""
        room = state_slots.get("room") or ""
        budget = state_slots.get("budget_text") or state_slots.get("budget_usd") or ""
        style = state_slots.get("style") or ""
        budget_min = state_slots.get("budget_min") or ""
        if cat:
            raw = cat
            _tenant_sales_requested_cat = cat
        if cat or room or budget or style or budget_min:
            # Phase 10G: format budget_min as lower-bound phrase so parse_price_constraint picks it up as min_price
            parts = [cat, room, budget]
            # Phase 10H: include both canonical style and Vietnamese label for KB matching (e.g., "classic" + "cÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¢ Ãƒâ€žÃ¢â‚¬ËœiÃƒÂ¡Ã‚Â»Ã†â€™n")
            if style:
                parts.append(style)
                try:
                    from .sales_flow import STYLE_TO_VI
                    vi_label = STYLE_TO_VI.get(style)
                    if vi_label:
                        parts.append(vi_label)
                except Exception:
                    pass
            if budget_min:
                parts.append(f"trÃƒÆ’Ã‚Âªn {budget_min}")
            accumulated = " ".join(p for p in parts if p).strip()
            if accumulated:
                _tenant_sales_search_query = accumulated
        if _tenant_sales_agent_brief:
            _tenant_sales_search_query = _agent_build_search_query(
                _tenant_sales_agent_brief,
                _tenant_sales_search_query or req.message,
            )
            if _tenant_sales_agent_brief.get("product_focus"):
                _tenant_sales_requested_cat = _tenant_sales_agent_brief.get("product_focus")
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
                active_kb, _tenant_sales_search_query,
                k=max(len(retrieval_hits) + filtered_count + 5, 20),
                tenant_id=req.tenant_id,
            )
            retrieval_hits = filter_by_category(retrieval_hits, _tenant_sales_requested_cat)

    # Phase 10I: hard price filter from accumulated sales_state (hard min/max, not apply_price_constraint which returns all on no-match)
    if retrieval_hits and sales_state and _is_tenant_sales_mode(mode) and sales_state.slots:
        _ss = sales_state.slots
        _budget_min_str = _ss.get("budget_min") or ""
        _budget_str = _ss.get("budget") or ""
        _budget_text = _ss.get("budget_text") or ""
        _min_price_vnd = None
        _max_price_vnd = None
        if _budget_min_str:
            _pm = __import__("re").search(r"(\d+(?:[.,]\d+)?)\s*(tri\u1ec7u|tr|trieu|ngh\u00ecn|nghin)", _budget_min_str, __import__("re").I)
            if _pm:
                _val = float(_pm.group(1).replace(",", "."))
                _mult = 1_000_000 if _pm.group(2) in ("tri\u1ec7u", "tr", "trieu") else 1_000
                _min_price_vnd = int(_val * _mult)
        # Phase 10J: only use budget/budget_text for max_price when there is NO budget_min
        # (budget_min and budget share the same underlying text for lower-bound expressions)
        if not _budget_min_str:
            _upper_text = _budget_str or _budget_text
            if _upper_text:
                _pm2 = __import__("re").search(r"(\d+(?:[.,]\d+)?)\s*(tri\u1ec7u|tr|trieu|ngh\u00ecn|nghin)", _upper_text, __import__("re").I)
                if _pm2:
                    _val2 = float(_pm2.group(1).replace(",", "."))
                    _mult2 = 1_000_000 if _pm2.group(2) in ("tri\u1ec7u", "tr", "trieu") else 1_000
                    _max_price_vnd = int(_val2 * _mult2)
        if _min_price_vnd is not None or _max_price_vnd is not None:
            _pre_count = len(retrieval_hits)
            _filtered = []
            for _hit in retrieval_hits:
                _meta = getattr(_hit, "metadata", {}) if hasattr(_hit, "metadata") else {}
                _price_raw = None
                if isinstance(_meta, dict):
                    _price_raw = _meta.get("price")
                if _price_raw is None:
                    _price_raw = getattr(_hit, "price", None) or (getattr(getattr(_hit, "metadata", None) or {}, "get", lambda k: None)("price") if hasattr(_hit, "metadata") else None)
                if _price_raw is None:
                    _filtered.append(_hit)
                    continue
                try:
                    _pv = float(_price_raw)
                except (TypeError, ValueError):
                    _filtered.append(_hit)
                    continue
                if _min_price_vnd is not None and _pv < _min_price_vnd:
                    continue
                if _max_price_vnd is not None and _pv > _max_price_vnd:
                    continue
                _filtered.append(_hit)
            retrieval_hits = _filtered
            _post_count = len(retrieval_hits)
            if 'debug_trace' in dir() and debug_trace:
                debug_trace["price_filter_before"] = _pre_count
                debug_trace["price_filter_after"] = _post_count
                debug_trace["price_filter_min"] = _min_price_vnd
                debug_trace["price_filter_max"] = _max_price_vnd

    # Phase 11D: if Claude configured for tenant_sales and we have filtered hits, generate natural response using ONLY evidence
    if _is_tenant_sales_mode(mode) and retrieval_hits:
        _claude_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        if _claude_key and not _is_pytest_blocking_real_claude():
            _tenant_sales_listing_claude_attempted = True
            _ev = []
            for _h in retrieval_hits[:5]:
                _m = getattr(_h, "metadata", {}) if hasattr(_h, "metadata") else {}
                if not isinstance(_m, dict):
                    _m = {}
                _ev.append({
                    "name": _m.get("product_name") or getattr(_h, "title", "") or "",
                    "sku": _m.get("sku") or getattr(_h, "sku", "") or "",
                    "price": _m.get("price"),
                    "category": _m.get("category") or getattr(_h, "category", "") or "",
                    "url": _m.get("source_url") or getattr(_h, "source", "") or getattr(_h, "source_url", ""),
                })
            _prompt = _build_tenant_sales_listing_prompt(_tenant_sales_search_query or req.message, _ev, (sales_state.slots if sales_state else slots_for_debug))
            _t0c = time.time()
            _cout, _cerr, _cprev = _call_claude_api(
                _prompt, _claude_key,
                os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6",
                os.getenv("CLAUDE_API_BASE_URL") or "https://api.anthropic.com",
                800, 0.6, 1.0, 30
            )
            if _cout and not _cerr:
                _tenant_sales_claude_rewritten = _cout.strip()
                _tenant_sales_listing_claude_called = True
                _tenant_sales_listing_claude_mode = "product_listing"
                _tenant_sales_listing_claude_error_type = None
                try:
                    log_event({
                        "event": "tenant_sales_claude_listing",
                        "conversation_id": conv_id,
                        "latency_ms": int((time.time() - _t0c) * 1000),
                    })
                except Exception:
                    pass
                print(f"[LLM] tenant_sales_response success mode=product_listing latency_ms={int((time.time()-_t0c)*1000)}")
            else:
                _tenant_sales_listing_claude_called = False
                _tenant_sales_listing_claude_skip_reason = "claude_error_or_empty"
                _tenant_sales_listing_claude_error_type = _cerr or "empty"
                print(f"[LLM] tenant_sales_response failed error_type={_tenant_sales_listing_claude_error_type}")
        else:
            _tenant_sales_listing_claude_attempted = False
            _tenant_sales_listing_claude_called = False
            if _is_pytest_blocking_real_claude():
                _tenant_sales_listing_claude_skip_reason = "pytest_real_llm_disabled"
            else:
                _tenant_sales_listing_claude_skip_reason = "missing_api_key"
            print(f"[LLM] tenant_sales_response skipped reason={_tenant_sales_listing_claude_skip_reason}")

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

    # Phase 10F: determine LLM call status for debug
    llm_enabled = (provider == "claude") or (provider == "local" and answer_mode != "template")
    llm_provider = provider if llm_enabled else "none"
    llm_model = (os.getenv("CLAUDE_MODEL") or 'claude-sonnet-4-6') if provider == "claude" else (base_model or "")
    llm_call_attempted = llm_enabled and answer_mode != "template"
    llm_called = False  # will be set True after successful call below
    llm_skip_reason = ""
    if not llm_enabled:
        llm_skip_reason = "llm_disabled"
    elif answer_mode == "template":
        llm_skip_reason = "template_route"
    elif provider == "claude" and not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")):
        llm_skip_reason = "missing_api_key"

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
        llm_enabled=llm_enabled,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_call_attempted=llm_call_attempted,
        llm_called=llm_called,
        llm_skip_reason=llm_skip_reason,
        answer_mode=answer_mode,
        template_reason="template" if answer_mode == "template" else "",
        retrieval_query=_tenant_sales_search_query if sales_enabled else req.message,
        requested_category=_tenant_sales_requested_cat or "",
        slots_snapshot=dict(sales_state.slots if sales_state else slots_for_debug),
    )
    debug_trace.update({
        "answer_mode": answer_mode,
        "template_renderer": answer_mode == "template",
        "retrieval_count": len(retrieval_hits),
        # Phase 11C: state interpreter debug - exact field names required
        "state_interpreter_llm_attempted": _interpreter_attempted,
        "state_interpreter_llm_called": _interpreter_called,
        "state_interpreter_skip_reason": _interpreter_skip_reason,
        "state_interpreter_error_type": _interpreter_error_type,
        "state_interpreter_intent": _interpreter_intent or "",
        "state_interpreter_confidence": float(_interpreter_result.get("confidence", 0.0)) if _interpreter_result else 0.0,
        "deterministic_slots": _mask_contact_in_value(dict(_deterministic_slots or {})),
        "slots_snapshot_after_interpreter": _mask_contact_in_value(dict(_slots_after_interpreter or (sales_state.slots if sales_state else {}))),
        # Legacy aliases for backward compat
        "state_interpreter_attempted": _interpreter_attempted,
        "state_interpreter_called": _interpreter_called,
        "state_interpreter_used": _interpreter_used,
        # Phase 11C: consultation LLM debug
        "consultation_llm_attempted": _consultation_attempted,
        "consultation_llm_called": _consultation_called,
        "consultation_llm_skip_reason": _consultation_skip_reason,
        "consultation_llm_error_type": _consultation_error_type,
        "tenant_sales_agent_enabled": bool(_tenant_sales_agent_brief),
        "tenant_sales_agent_action": getattr(_tenant_sales_agent_decision, "action", "") if _tenant_sales_agent_decision else "",
        "tenant_sales_agent_reason": getattr(_tenant_sales_agent_decision, "reason", "") if _tenant_sales_agent_decision else "",
        "customer_brief": _mask_contact_in_value(_tenant_sales_agent_brief),
    })
    if _is_tenant_sales_mode(mode) and retrieval_hits:
        debug_trace.update({
            "real_claude_response_attempted": _tenant_sales_listing_claude_attempted,
            "real_claude_response_called": _tenant_sales_listing_claude_called,
            "real_claude_response_mode": _tenant_sales_listing_claude_mode or "product_listing",
            "real_claude_skip_reason": _tenant_sales_listing_claude_skip_reason,
            "real_claude_error_type": _tenant_sales_listing_claude_error_type,
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
    _claude_advisor_response = None
    if not (_is_tenant_sales_mode(mode) and (_tenant_sales_claude_rewritten or retrieval_hits)):
        _claude_advisor_response = _try_claude_advisor_response(
            mode=mode,
            user_message=req.message,
            context=context,
            customer_brief=_tenant_sales_agent_brief if _is_tenant_sales_mode(mode) else {},
            slots=(sales_state.slots if sales_state else slots_for_debug),
            debug_trace=debug_trace,
        )
    log_retrieval_debug({
        **debug_trace,
        **summarize_retrieval_debug(retrieval_hits, context),
        "question": req.message,
        "channel": req.channel,
        "conversation_id": conv_id,
        "tenant_id": req.tenant_id,
        "allow_rag": allow_rag,
    })

    if _claude_advisor_response:
        latency_ms = 0
        log_event({
            "event": "chat",
            "question": req.message,
            "answer": _claude_advisor_response[:1200],
            "latency_ms": latency_ms,
            "model": "claude-advisor",
            "adapter": None,
            "provider": "claude",
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "context_length": len(context),
            "kb_loaded": active_kb is not None,
            "sales_stage": stage_for_debug,
            "sales_slots": slots_for_debug,
            "debug": _with_production_debug_panel(debug_trace),
        })
        try:
            save_turn(conv_id, req.message, _claude_advisor_response[:1200])
        except Exception:
            pass
        if sales_enabled and sales_state is not None:
            _save_sales_state(sales_state)
        response_trigger_purchase_request = False if sales_enabled else (trigger_purchase_request if _is_tenant_sales_mode(mode) else False)
        return ChatResp(
            reply=_claude_advisor_response[:1200],
            latency_ms=latency_ms,
            model="claude-advisor",
            adapter=None,
            trigger_purchase_request=response_trigger_purchase_request,
            captured_phone=captured_phone if _is_tenant_sales_mode(mode) else None,
            captured_name=captured_name if _is_tenant_sales_mode(mode) else None,
            debug=_with_production_debug_panel(debug_trace),
        )

    if answer_mode == "template":
        t0 = time.time()
        if mode == ChatMode.GENERAL_COMPARE.value and backend_items:
            resp = render_general_compare(req.message, backend_items)
        else:
            # Phase 11D: if we have Claude rewritten for tenant_sales, use it instead of raw product renderer
            if _is_tenant_sales_mode(mode) and _tenant_sales_claude_rewritten:
                resp = _tenant_sales_claude_rewritten
                debug_trace.update({
                    "answer_mode": "claude_tenant_sales",
                    "template_renderer": False,
                    "retrieval_count": len(retrieval_hits),
                    "real_claude_response_attempted": True,
                    "real_claude_response_called": True,
                    "real_claude_response_mode": "product_listing",
                })
            elif _is_tenant_sales_mode(mode) and _tenant_sales_style_question_requested and sales_state:
                resp = _tenant_sales_style_consult_reply(sales_state.slots, req.message)
                debug_trace.update({
                    "answer_mode": "tenant_sales_consultation",
                    "template_renderer": False,
                    "retrieval_count": len(retrieval_hits),
                    "tenant_sales_response_kind": "style_consultation",
                })
            elif _is_tenant_sales_mode(mode) and retrieval_hits:
                _listing_brief = _tenant_sales_agent_brief
                if not _listing_brief and sales_state:
                    _listing_brief = sales_state.slots.get(TENANT_SALES_BRIEF_SLOT) or {}
                if not _listing_brief:
                    _listing_brief = slots_for_debug if isinstance(slots_for_debug, dict) else {}
                resp = _agent_compose_listing(
                    req.message,
                    retrieval_hits,
                    _listing_brief,
                )
                debug_trace.update({
                    "answer_mode": "tenant_sales_agent",
                    "template_renderer": False,
                    "retrieval_count": len(retrieval_hits),
                    "tenant_sales_response_kind": "agent_listing_fallback",
                })
            else:
                resp = render_product_answer(req.message, context)
                debug_trace.update({
                    "answer_mode": "template",
                    "template_renderer": True,
                    "retrieval_count": len(retrieval_hits),
                })
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
            "model": "claude-tenant-sales" if (_is_tenant_sales_mode(mode) and _tenant_sales_claude_rewritten) else "product-template",
            "adapter": None,
            "provider": provider,
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "context_length": len(context),
            "kb_loaded": active_kb is not None,
            "sales_stage": stage_for_debug,
            "sales_slots": slots_for_debug,
            "debug": _with_production_debug_panel(debug_trace),
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
            model="claude-tenant-sales" if (_is_tenant_sales_mode(mode) and _tenant_sales_claude_rewritten) else "product-template",
            adapter=None,
            trigger_purchase_request=response_trigger_purchase_request,
            captured_phone=captured_phone if _is_tenant_sales_mode(mode) else None,
            captured_name=captured_name if _is_tenant_sales_mode(mode) else None,
            debug=_with_production_debug_panel(debug_trace),
        )

    # ---- SIMILAR SUGGESTION (use KB hits) ----
    if _is_tenant_sales_mode(mode) and active_kb is not None and allow_rag and want_similar(req.message):
        similar_hits = retrieval_hits
        if len(similar_hits) < 8:
            similar_hits = search_hits(active_kb, _tenant_sales_search_query or req.message, k=8, tenant_id=req.tenant_id)
        if _tenant_sales_requested_cat:
            similar_hits = filter_by_category(similar_hits, _tenant_sales_requested_cat)
        # Phase 10J: apply price constraint to similar hits too
        if similar_hits and sales_state and _is_tenant_sales_mode(mode) and sales_state.slots:
            _ss2 = sales_state.slots
            _bmin2 = _ss2.get("budget_min") or ""
            _minvnd2 = None
            _maxvnd2 = None
            if _bmin2:
                _m2 = __import__("re").search(r"(\d+(?:[.,]\d+)?)\s*(triÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u|tr|trieu|nghÃƒÆ’Ã‚Â¬n|nghin)", _bmin2, __import__("re").I)
                if _m2:
                    _v2 = float(_m2.group(1).replace(",", "."))
                    _mu2 = 1_000_000 if _m2.group(2) in ("triÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u", "tr", "trieu") else 1_000
                    _minvnd2 = int(_v2 * _mu2)
            if not _bmin2:
                _ut2 = _ss2.get("budget") or _ss2.get("budget_text") or ""
                if _ut2:
                    _m3 = __import__("re").search(r"(\d+(?:[.,]\d+)?)\s*(triÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u|tr|trieu|nghÃƒÆ’Ã‚Â¬n|nghin)", _ut2, __import__("re").I)
                    if _m3:
                        _v3 = float(_m3.group(1).replace(",", "."))
                        _mu3 = 1_000_000 if _m3.group(2) in ("triÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u", "tr", "trieu") else 1_000
                        _maxvnd2 = int(_v3 * _mu3)
            if _minvnd2 is not None or _maxvnd2 is not None:
                _fh2 = []
                for _hk in similar_hits:
                    _mk = getattr(_hk, "metadata", {}) if hasattr(_hk, "metadata") else {}
                    _pr2 = None
                    if isinstance(_mk, dict):
                        _pr2 = _mk.get("price")
                    if _pr2 is None:
                        _fh2.append(_hk); continue
                    try:
                        _pv2 = float(_pr2)
                    except (TypeError, ValueError):
                        _fh2.append(_hk); continue
                    if _minvnd2 is not None and _pv2 < _minvnd2:
                        continue
                    if _maxvnd2 is not None and _pv2 > _maxvnd2:
                        continue
                    _fh2.append(_hk)
                similar_hits = _fh2
        items = top_similar_items(similar_hits, limit=3)

        if items:
            reply = (
                'Mình gợi ý một vài sản phẩm tương tự trong dữ liệu hiện có:\n' +
                "\n".join([f"- {t} ({u})" if u else f"- {t}" for t, u in items])
            )
        else:
            reply = "MÃƒÆ’Ã‚Â¬nh chÃƒâ€ Ã‚Â°a tÃƒÆ’Ã‚Â¬m thÃƒÂ¡Ã‚ÂºÃ‚Â¥y sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m cÃƒÆ’Ã‚Â¹ng loÃƒÂ¡Ã‚ÂºÃ‚Â¡i phÃƒÆ’Ã‚Â¹ hÃƒÂ¡Ã‚Â»Ã‚Â£p trong dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u hiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n cÃƒÆ’Ã‚Â³. BÃƒÂ¡Ã‚ÂºÃ‚Â¡n cÃƒÆ’Ã‚Â³ muÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœn nÃƒÂ¡Ã‚Â»Ã¢â‚¬Âºi Ãƒâ€žÃ¢â‚¬ËœiÃƒÂ¡Ã‚Â»Ã‚Âu kiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n hoÃƒÂ¡Ã‚ÂºÃ‚Â·c chÃƒÂ¡Ã‚Â»Ã‚Ân nhÃƒÆ’Ã‚Â³m sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m khÃƒÆ’Ã‚Â¡c khÃƒÆ’Ã‚Â´ng?"

        log_event({
            "event": "similar_suggestion",
            "question": req.message,
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "items": [{"title": t, "url": u} for t, u in items] if items else [],
            "debug": _with_production_debug_panel(debug_trace),
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
            debug=_with_production_debug_panel(debug_trace),
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
        elif _is_pytest_blocking_real_claude():
            # Phase 11F: pytest guard - never call real Claude in normal pytest
            out = ""
            claude_error_code = "pytest_real_llm_disabled"
            claude_error_preview = "pytest blocked real claude"
            debug_trace["real_claude_skip_reason"] = "pytest_real_llm_disabled"
        else:
            llm_called = True
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
            debug_trace["llm_error_type"] = claude_error_code
        if claude_error_code:
            debug_trace["claude_error"] = {
                "type": claude_error_code,
                "preview": claude_error_preview,
                "model": api_model,
                "base_url": api_base_url,
            }
        if llm_called and not claude_error_code:
            debug_trace["llm_called"] = True
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
        resp = "Xin lÃƒÂ¡Ã‚Â»Ã¢â‚¬â€i, hÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡ thÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœng Ãƒâ€žÃ¢â‚¬Ëœang gÃƒÂ¡Ã‚ÂºÃ‚Â·p sÃƒÂ¡Ã‚Â»Ã‚Â± cÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœ khi xÃƒÂ¡Ã‚Â»Ã‚Â­ lÃƒÆ’Ã‚Â½ yÃƒÆ’Ã‚Âªu cÃƒÂ¡Ã‚ÂºÃ‚Â§u. BÃƒÂ¡Ã‚ÂºÃ‚Â¡n thÃƒÂ¡Ã‚Â»Ã‚Â­ lÃƒÂ¡Ã‚ÂºÃ‚Â¡i giÃƒÆ’Ã‚Âºp mÃƒÆ’Ã‚Â¬nh nhÃƒÆ’Ã‚Â©."

    # Keep answers concise, but not too short for consultative flow
    if response_model != "structured_price":
        sentences = re.split(r'(?<=[.!?])\s+', resp)
        resp = " ".join(sentences[:6]).strip()

    NOT_FOUND = "I couldnÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢t find that in this storeÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢s data."

    if provider != "stub":
        if _is_tenant_sales_mode(mode) and _prefer_vietnamese_response(req, mode) and ((not context) or (NOT_FOUND.lower() in resp.lower())):
            resp = (
                "MÃƒÆ’Ã‚Â¬nh chÃƒâ€ Ã‚Â°a cÃƒÆ’Ã‚Â³ Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã‚Â§ dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u tÃƒÂ¡Ã‚Â»Ã‚Â« kho tri thÃƒÂ¡Ã‚Â»Ã‚Â©c cÃƒÂ¡Ã‚Â»Ã‚Â§a cÃƒÂ¡Ã‚Â»Ã‚Â­a hÃƒÆ’Ã‚Â ng Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ trÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi thÃƒÂ¡Ã‚ÂºÃ‚Â­t chÃƒÆ’Ã‚Â­nh xÃƒÆ’Ã‚Â¡c. "
                "BÃƒÂ¡Ã‚ÂºÃ‚Â¡n gÃƒÂ¡Ã‚Â»Ã‚Â­i giÃƒÆ’Ã‚Âºp mÃƒÆ’Ã‚Â¬nh tÃƒÆ’Ã‚Âªn sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m, mÃƒÆ’Ã‚Â£ sÃƒÂ¡Ã‚ÂºÃ‚Â£n phÃƒÂ¡Ã‚ÂºÃ‚Â©m hoÃƒÂ¡Ã‚ÂºÃ‚Â·c nhu cÃƒÂ¡Ã‚ÂºÃ‚Â§u cÃƒÂ¡Ã‚Â»Ã‚Â¥ thÃƒÂ¡Ã‚Â»Ã†â€™ hÃƒâ€ Ã‚Â¡n nhÃƒÆ’Ã‚Â©; "
                "mÃƒÆ’Ã‚Â¬nh cÃƒâ€¦Ã‚Â©ng cÃƒÆ’Ã‚Â³ thÃƒÂ¡Ã‚Â»Ã†â€™ chuyÃƒÂ¡Ã‚Â»Ã†â€™n cho nhÃƒÆ’Ã‚Â¢n viÃƒÆ’Ã‚Âªn tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n nÃƒÂ¡Ã‚ÂºÃ‚Â¿u bÃƒÂ¡Ã‚ÂºÃ‚Â¡n muÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœn."
            )
        elif _is_tenant_sales_mode(mode) and ((not context) or (NOT_FOUND.lower() in resp.lower())):
            resp = (
                "MÃƒÆ’Ã‚Â¬nh chÃƒâ€ Ã‚Â°a Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã‚Â§ thÃƒÆ’Ã‚Â´ng tin Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã†â€™ tÃƒâ€ Ã‚Â° vÃƒÂ¡Ã‚ÂºÃ‚Â¥n chÃƒÆ’Ã‚Â­nh xÃƒÆ’Ã‚Â¡c. BÃƒÂ¡Ã‚ÂºÃ‚Â¡n cho mÃƒÆ’Ã‚Â¬nh biÃƒÂ¡Ã‚ÂºÃ‚Â¿t thÃƒÆ’Ã‚Âªm nhu cÃƒÂ¡Ã‚ÂºÃ‚Â§u, ngÃƒÆ’Ã‚Â¢n sÃƒÆ’Ã‚Â¡ch hoÃƒÂ¡Ã‚ÂºÃ‚Â·c khÃƒÆ’Ã‚Â´ng gian sÃƒÂ¡Ã‚Â»Ã‚Â­ dÃƒÂ¡Ã‚Â»Ã‚Â¥ng nhÃƒÆ’Ã‚Â©."
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
            "\n\nNÃƒÂ¡Ã‚ÂºÃ‚Â¿u muÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœn gÃƒÂ¡Ã‚Â»Ã‚Â­i yÃƒÆ’Ã‚Âªu cÃƒÂ¡Ã‚ÂºÃ‚Â§u cho cÃƒÂ¡Ã‚Â»Ã‚Â­a hÃƒÆ’Ã‚Â ng, bÃƒÂ¡Ã‚ÂºÃ‚Â¡n trÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi CONFIRM. "
            "NÃƒÂ¡Ã‚ÂºÃ‚Â¿u muÃƒÂ¡Ã‚Â»Ã¢â‚¬Ëœn dÃƒÂ¡Ã‚Â»Ã‚Â«ng, bÃƒÂ¡Ã‚ÂºÃ‚Â¡n trÃƒÂ¡Ã‚ÂºÃ‚Â£ lÃƒÂ¡Ã‚Â»Ã‚Âi CANCEL. "
            'Mình chưa xử lý thanh toán trực tiếp trong chat.'
        )


    resp = _apply_grounding_guard(req.message, context, resp)

    # --- Output guardrail: if model slips into unverified facts, replace with safe fallback ---
    if BAD_FACTS.search(resp):
        resp = (
            "MÃƒÆ’Ã‚Â¬nh chÃƒâ€ Ã‚Â°a tÃƒÆ’Ã‚Â¬m thÃƒÂ¡Ã‚ÂºÃ‚Â¥y thÃƒÆ’Ã‚Â´ng tin Ãƒâ€žÃ¢â‚¬ËœÃƒÂ¡Ã‚Â»Ã‚Â§ chÃƒÂ¡Ã‚ÂºÃ‚Â¯c chÃƒÂ¡Ã‚ÂºÃ‚Â¯n trong dÃƒÂ¡Ã‚Â»Ã‚Â¯ liÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡u hiÃƒÂ¡Ã‚Â»Ã¢â‚¬Â¡n cÃƒÆ’Ã‚Â³. BÃƒÂ¡Ã‚ÂºÃ‚Â¡n cÃƒÆ’Ã‚Â³ thÃƒÂ¡Ã‚Â»Ã†â€™ mÃƒÆ’Ã‚Â´ tÃƒÂ¡Ã‚ÂºÃ‚Â£ cÃƒÂ¡Ã‚Â»Ã‚Â¥ thÃƒÂ¡Ã‚Â»Ã†â€™ hÃƒâ€ Ã‚Â¡n nhu cÃƒÂ¡Ã‚ÂºÃ‚Â§u Ãƒâ€žÃ¢â‚¬ËœÃƒâ€ Ã‚Â°ÃƒÂ¡Ã‚Â»Ã‚Â£c khÃƒÆ’Ã‚Â´ng?"
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
        "debug": _with_production_debug_panel(debug_trace),
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
        debug=_with_production_debug_panel(debug_trace),
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

