import os
import time
import re
import threading
import requests
from typing import List, Optional, Dict, Tuple, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .guardrails import rule_reply, want_similar
from .logger import log_event, log_feedback

# --- SALES FLOW imports ---
from .state import get_state, save_turn, set_stage, reset_state
from .sales_flow import extract_slots, next_stage, build_sales_prefix, detect_intent, has_sufficient_constraints

# --- CONSULTATION imports ---
from .consultation import extract_consultation_slots, build_consultation_prefix, next_consultation_stage, extract_phone

from .model_loader import get_pipeline
from .prompt import build_messages, DEFAULT_SYSTEM
from .retriever import SimpleKb


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
        # Product changed - reset product-specific slots
        if mode == "general_consumer":
            # In consultation mode, reset room_type and room_size_sqm as they're product-specific
            existing_slots.pop("room_type", None)
            existing_slots.pop("room_size_sqm", None)
            # Also clear budget_range? Keep budget as it's general. Clear only if we want fresh.
            # We keep style_preference, color, material as they're cross-product.
        else:
            # In sales flow, product_type is the main product slot.
            # No other product-specific slots to reset currently.
            pass



def _call_claude_api(
    prompt: str,
    api_key: str,
    api_model: str,
    api_base_url: str,
    max_tokens: int,
    temperature: float,
    top_p: float
) -> str:
    """Call Anthropic Claude API and return generated text."""
    if not api_key:
        return ""  # empty triggers fallback

    # Clean prompt: remove trailing "Response:" lines
    cleaned_prompt = prompt.rstrip()
    if "Response:" in cleaned_prompt:
        cleaned_prompt = cleaned_prompt.split("Response:")[0].rstrip()

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }

    data = {
        "model": api_model,
        "messages": [{"role": "user", "content": cleaned_prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p
    }

    try:
        resp = requests.post(
            f"{api_base_url.rstrip('/')}/v1/messages",
            headers=headers,
            json=data,
            timeout=10
        )
        if resp.status_code != 200:
            return ""  # fallback to empty
        result = resp.json()
        # Anthropic response: {"content": [{"type": "text", "text": "..."}]}
        return result["content"][0]["text"]
    except Exception:
        return ""  # fallback to empty


# --- Output guardrail: block unverified payment/refund/timing claims ---
BAD_FACTS = re.compile(
    r"\b(within\s+\d+\s+(day|days|business\s+days)|refund|complete payment|receive the item)\b",
    re.I,
)


BASE_MODEL_DEFAULT = os.getenv("BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
ADAPTER_DEFAULT = os.getenv("LORA_ADAPTER") or None
TOKENIZER_DEFAULT = os.getenv("TOKENIZER_PATH") or None

MAX_NEW_TOKENS_DEFAULT = int(os.getenv("MAX_NEW_TOKENS", "256"))
TEMPERATURE_DEFAULT = float(os.getenv("TEMPERATURE", "0.7"))
TOP_P_DEFAULT = float(os.getenv("TOP_P", "0.9"))
TOP_K_DEFAULT = int(os.getenv("TOP_K", "50"))

app = FastAPI(title="Multi-tenant Chatbot Model Server")

PIPE_CACHE: Dict[Tuple[str, Optional[str], Optional[str]], Any] = {}
CACHE_LOCK = threading.Lock()

# ---- READY flags ----
READY = False
READY_ERR: Optional[str] = None
READY_LOCK = threading.Lock()

# KB: load theo env KB_DIR (mỗi process python 1 tenant)
KB_DIR = os.getenv("KB_DIR")
KB = None
if KB_DIR:
    try:
        chunks_path = os.path.join(KB_DIR, "chunks.jsonl")
        index_path = os.path.join(KB_DIR, "index.json")
        KB = SimpleKb(chunks_path, index_path)
        print("[kb] loaded from", KB_DIR)
    except Exception as e:
        print("[kb] load failed:", e)
        KB = None


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
    mode: Optional[str] = None  # tenant_sales | general_consumer


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


def _set_ready(value: bool, err: Optional[str] = None):
    global READY, READY_ERR
    with READY_LOCK:
        READY = value
        READY_ERR = err


def get_or_create_pipe(base_model: str, adapter: Optional[str], tokenizer_path: Optional[str]):
    key = (base_model, adapter, tokenizer_path)
    with CACHE_LOCK:
        if key not in PIPE_CACHE:
            pipe = get_pipeline(base=base_model, adapter=adapter, tokenizer_path=tokenizer_path)
            PIPE_CACHE[key] = pipe
        return PIPE_CACHE[key]


@app.on_event("startup")
def _warmup():
    # Warmup should build at least one pipeline so server is actually usable.
    def run():
        try:
            # Building the pipeline can take time on CPU.
            get_or_create_pipe(BASE_MODEL_DEFAULT, ADAPTER_DEFAULT, TOKENIZER_DEFAULT)
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
    return {
        "status": "ready" if ready else "loading",
        "ready": ready,
        "error": err,
        "cached_pipelines": len(PIPE_CACHE),
        "kb_dir": KB_DIR,
        "kb_loaded": KB is not None
    }


class FeedbackReq(BaseModel):
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = None
    channel: Optional[str] = None
    question: str
    answer: str
    is_correct: bool
    note: Optional[str] = ""


@app.post("/feedback")
def feedback(req: FeedbackReq):
    log_feedback(req.model_dump())
    return {"ok": True}


@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq):
    # Defense-in-depth: refuse chat if model is not ready yet.
    with READY_LOCK:
        if not READY:
            raise HTTPException(status_code=503, detail="Model is still loading")

    cfg = req.gen

    base_model = cfg.base_model or BASE_MODEL_DEFAULT
    adapter = cfg.adapter or ADAPTER_DEFAULT
    tokenizer_path = cfg.tokenizer_path or TOKENIZER_DEFAULT
    mode = cfg.mode or "tenant_sales"

    max_new_tokens = cfg.max_new_tokens or MAX_NEW_TOKENS_DEFAULT
    temperature = cfg.temperature or TEMPERATURE_DEFAULT
    top_p = cfg.top_p or TOP_P_DEFAULT
    top_k = int(cfg.top_k) if cfg.top_k is not None else TOP_K_DEFAULT

    # Debug log - write to stderr to ensure visibility
    import sys
    print(f"[SERVER DEBUG] Received mode: {mode}, base_model: {base_model}", file=sys.stderr)

    # Ensure conversation_id exists for stateful flow
    conv_id = req.conversation_id or "anon"

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

        log_event({
            "event": "reset",
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
        })

        return ChatResp(
            reply="Got it — I’ve started a new consultation. What are you shopping for today?",
            latency_ms=0,
            model="system",
            adapter=adapter
        )

    # ---- RULE layer (guardrails) ----
    rr = rule_reply(req.message)
    if rr:
        log_event({
            "event": "rule_hit",
            "rule_type": rr["type"],
            "question": req.message,
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
        })
        # Save turn (optional but useful for audit)
        try:
            save_turn(conv_id, req.message, rr["reply"])
        except Exception:
            pass
        return ChatResp(reply=rr["reply"], latency_ms=0, model="rule", adapter=adapter)

    # --- SALES FLOW: state/slots/stage (AFTER RULE layer) ---
    st = get_state(conv_id)

    # Default values for lead capture trigger (will be updated below)
    trigger_purchase_request = False
    captured_phone = None
    captured_name = None

    # update slots from this user message
    try:
        # Capture current stage BEFORE transition (for intent context and trigger)
        old_stage = getattr(st, "stage", "discover")

        if mode == "general_consumer":
            # Use consultation-specific slot extraction
            new_slots = extract_consultation_slots(req.message)
            _detect_and_track_preference_changes(st.slots, new_slots)
            _handle_topic_change(st.slots, new_slots, mode)
            if new_slots:
                st.slots.update(new_slots)
            # Extract phone for lead capture
            phone = extract_phone(req.message)
            if phone:
                st.slots["captured_phone"] = phone
            # Extract name (simple: look for "tên là..." patterns)
            name_match = re.search(r"(?:tên|ten|name)\s*(?:là|la|is)?\s*([A-Za-z\s]{2,50})", req.message, re.I)
            if name_match:
                st.slots["captured_name"] = name_match.group(1).strip()
            # decide next stage using consultation state machine (with old_stage)
            st.stage = next_consultation_stage(old_stage, st.slots, req.message)
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
        user_intent = detect_intent(req.message, old_stage)
        trigger_purchase_request = (old_stage == "close" and user_intent == "confirm")
        # For sales flow, phone/name are not extracted here; they come from transcript in Java
        captured_phone = st.slots.get("captured_phone")
        captured_name = st.slots.get("captured_name")
    except Exception:
        # Don't break chat if slot extractor fails
        pass

    # ---- Provider selection ----
    provider = cfg.provider or "local"

    if provider == "claude":
        # Claude API path
        api_key = cfg.api_key or 'sk-proj-fe708bb0167c4c18ae0ddb7ed8701d1a'
        api_model = cfg.api_model or 'claude-3-5-sonnet-20241022'
        api_base_url = cfg.api_base_url or 'https://api.anthropic.com'

        t0 = time.time()
        out = _call_claude_api(
            req.message,
            api_key,
            api_model,
            api_base_url,
            max_new_tokens,
            temperature,
            top_p
        )
        latency_ms = int((time.time() - t0) * 1000)

        resp = out.strip() if out else "Sorry, I couldn't process that request right now."
        # Concise answer
        sentences = re.split(r'(?<=[.!?…])\s+', resp)
        resp = " ".join(sentences[:6]).strip()

        log_event({
            "event": "chat",
            "question": req.message,
            "answer": resp[:1200],
            "latency_ms": latency_ms,
            "model": api_model,
            "adapter": None,
            "channel": req.channel,
            "conversation_id": conv_id,
            "tenant_id": req.tenant_id,
            "context_length": 0,
            "kb_loaded": KB is not None,
            "sales_stage": getattr(st, "stage", None),
            "sales_slots": getattr(st, "slots", {}),
        })
        try:
            save_turn(conv_id, req.message, resp)
        except Exception:
            pass
        return ChatResp(
            reply=resp[:1200],
            latency_ms=latency_ms,
            model=api_model,
            adapter=None
        )

    pipe = get_or_create_pipe(base_model, adapter, tokenizer_path)

    # ---- RAG context from KB ----
    ctx_blocks = []
    # Bonus: reduce hallucination from early generic queries by limiting RAG.
    # Rule of thumb: only inject KB when user provided a link/code or the convo is past early discovery.
    allow_rag = False
    try:
        msg = (req.message or "").strip()
        words = [w for w in msg.split() if w]
        has_link = bool(re.search(r"https?://|www\.", msg, re.I))
        allow_rag = has_link or (len(words) >= 6) or (getattr(st, "stage", "discover") != "discover")
    except Exception:
        allow_rag = False

    if KB is not None and allow_rag:
        hits = KB.search(req.message, k=4)
        for h in hits:
            title = (h.get("title") or "").strip()
            url = (h.get("url") or "").strip()
            content = (h.get("content") or "").strip()
            if not content:
                continue
            ctx_blocks.append(f"- {title} ({url}): {content[:900]}")
    context = "\n".join(ctx_blocks)

    # ---- SIMILAR SUGGESTION (use KB hits) ----
    if KB is not None and allow_rag and want_similar(req.message):
        hits = KB.search(req.message, k=8)

        seen = set()
        items = []
        for h in hits:
            title = (h.get("title") or "").strip()
            url = (h.get("url") or "").strip()
            if title and title not in seen:
                seen.add(title)
                items.append((title, url))
            if len(items) >= 3:
                break

        if items:
            reply = (
                "Here are a few similar products you might want to consider:\n" +
                "\n".join([f"- {t} ({u})" if u else f"- {t}" for t, u in items]) +
                "\nWhat would you like to prioritize: style, size, or material?"
            )

            log_event({
                "event": "similar_suggestion",
                "question": req.message,
                "channel": req.channel,
                "conversation_id": conv_id,
                "tenant_id": req.tenant_id,
                "items": [{"title": t, "url": u} for t, u in items],
            })

            # Save turn for stateful flow continuity
            try:
                save_turn(conv_id, req.message, reply[:1200])
            except Exception:
                pass

            return ChatResp(
                reply=reply[:1200],
                latency_ms=0,
                model=base_model,
                adapter=adapter
            )

    # ---- SALES flow prefix inside system prompt ----
    sales_prefix = ""
    try:
        if mode == "general_consumer":
            sales_prefix = build_consultation_prefix(getattr(st, "stage", "discover"), getattr(st, "slots", {}))
        else:
            sales_prefix = build_sales_prefix(getattr(st, "stage", "discover"), getattr(st, "slots", {}))
    except Exception:
        sales_prefix = ""

    sys_prompt = cfg.system_prompt or (sales_prefix + "\n" + DEFAULT_SYSTEM)

    messages = build_messages(req.message, req.history, sys_prompt)

    prompt_text = pipe.tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    t0 = time.time()
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

    resp = out.strip()

    # Keep answers concise, but not too short for consultative flow
    sentences = re.split(r'(?<=[.!?])\s+', resp)
    resp = " ".join(sentences[:6]).strip()

    NOT_FOUND = "I couldn’t find that in this store’s data."

    # For general_consumer mode, do NOT apply KB-based fallback - the consultation works without KB
    if mode != "general_consumer" and ((not context) or (NOT_FOUND.lower() in resp.lower())):
        resp = (
            "Sorry, I couldn’t find enough information to answer that accurately. "
            "If you can share the product name or code, I can try again, "
            "or I can connect you with a staff member for further assistance."
        )

    # --- SALES FLOW: close stage hard CTA (CONFIRM / CANCEL / no payment) ---
    if getattr(st, "stage", None) == "close":
        if mode == "general_consumer":
            resp = resp.strip()
            resp += (
                "\n\nWould you like to: "
                "1) Get specific product links to browse, "
                "2) Talk to a human advisor for final help, or "
                "3) Continue exploring options? "
                "Just let me know!"
            )
        else:
            resp = resp.strip()
            resp += (
                "\n\nTo proceed, reply CONFIRM and I’ll create a purchase request for our staff. "
                "Reply CANCEL to stop. "
                "I can’t process payments directly in chat."
            )

    # --- Output guardrail: if model slips into unverified facts, replace with safe fallback ---
    if BAD_FACTS.search(resp):
        resp = (
            "Sorry — I can’t confirm payment, delivery timing, or refund details in chat without verified store data. "
            "If you share the product link/name, I can check what’s available, or I can connect you with a staff member to confirm the details."
        )

    latency_ms = int((time.time() - t0) * 1000)

    log_event({
        "event": "chat",
        "question": req.message,
        "answer": resp[:1200],
        "latency_ms": latency_ms,
        "model": base_model,
        "adapter": adapter,
        "channel": req.channel,
        "conversation_id": conv_id,
        "tenant_id": req.tenant_id,
        "context_length": len(context),
        "kb_loaded": KB is not None,
        "sales_stage": getattr(st, "stage", None),
        "sales_slots": getattr(st, "slots", {}),
    })

    # --- SALES FLOW: save conversation turn ---
    try:
        save_turn(conv_id, req.message, resp)
    except Exception:
        pass

    return ChatResp(
        reply=resp[:1200],
        latency_ms=latency_ms,
        model=base_model,
        adapter=adapter,
        trigger_purchase_request=trigger_purchase_request,
        captured_phone=captured_phone,
        captured_name=captured_name
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
