import os
import time
import re
import threading
from typing import List, Optional, Dict, Tuple, Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .model_loader import get_pipeline
from .prompt import build_prompt, DEFAULT_SYSTEM
from .retriever import SimpleKb

BASE_MODEL_DEFAULT = os.getenv("BASE_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
ADAPTER_DEFAULT = os.getenv("LORA_ADAPTER") or None
TOKENIZER_DEFAULT = os.getenv("TOKENIZER_PATH") or None

MAX_NEW_TOKENS_DEFAULT = int(os.getenv("MAX_NEW_TOKENS", "256"))
TEMPERATURE_DEFAULT = float(os.getenv("TEMPERATURE", "0.7"))
TOP_P_DEFAULT = float(os.getenv("TOP_P", "0.9"))
TOP_K_DEFAULT = int(os.getenv("TOP_K", "50"))

app = FastAPI(title="Multi-tenant Chatbot Model Server")

PIPE_CACHE: Dict[Tuple[str, Optional[str], Optional[str]], Any] = {}
CACHE_LOCK = threading.Lock()

# KB: load theo env KB_DIR (mỗi process python 1 tenant)
KB_DIR = os.getenv("KB_DIR")  # e.g. "F:/.../kb/ikea_us"
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


class ChatReq(BaseModel):
    message: str
    history: List[str] = Field(default_factory=list)
    gen: GenerationConfig = Field(default_factory=GenerationConfig)


class ChatResp(BaseModel):
    reply: str
    latency_ms: int
    model: str
    adapter: Optional[str]


def get_or_create_pipe(base_model: str, adapter: Optional[str], tokenizer_path: Optional[str]):
    key = (base_model, adapter, tokenizer_path)
    with CACHE_LOCK:
        if key not in PIPE_CACHE:
            pipe = get_pipeline(base=base_model, adapter=adapter, tokenizer_path=tokenizer_path)
            PIPE_CACHE[key] = pipe
        return PIPE_CACHE[key]


@app.on_event("startup")
def _warmup():
    def run():
        try:
            get_or_create_pipe(BASE_MODEL_DEFAULT, ADAPTER_DEFAULT, TOKENIZER_DEFAULT)
        except Exception as e:
            print("[warmup] failed:", e)

    threading.Thread(target=run, daemon=True).start()


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "cached_pipelines": len(PIPE_CACHE),
        "kb_dir": KB_DIR,
        "kb_loaded": KB is not None
    }


@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq):
    cfg = req.gen

    base_model = cfg.base_model or BASE_MODEL_DEFAULT
    adapter = cfg.adapter or ADAPTER_DEFAULT
    tokenizer_path = cfg.tokenizer_path or TOKENIZER_DEFAULT

    max_new_tokens = cfg.max_new_tokens or MAX_NEW_TOKENS_DEFAULT
    temperature = cfg.temperature or TEMPERATURE_DEFAULT
    top_p = cfg.top_p or TOP_P_DEFAULT
    top_k = cfg.top_k or TOP_K_DEFAULT

    pipe = get_or_create_pipe(base_model, adapter, tokenizer_path)

    # ---- RAG context from KB ----
    ctx_blocks = []
    if KB is not None:
        hits = KB.search(req.message, k=4)
        for h in hits:
            title = (h.get("title") or "").strip()
            url = (h.get("url") or "").strip()
            content = (h.get("content") or "").strip()
            if not content:
                continue
            ctx_blocks.append(f"- {title} ({url}): {content[:900]}")
    context = "\n".join(ctx_blocks)

    # ---- system prompt ----
    base_sys = cfg.system_prompt or DEFAULT_SYSTEM
    if context:
        sys_prompt = base_sys + (
            "\n\nYou MUST answer using the store information in CONTEXT.\n"
            "If the answer is not found in CONTEXT, say exactly: "
            "'I couldn't find that in this store's data.'\n"
            "CONTEXT:\n" + context
        )
    else:
        sys_prompt = base_sys

    prompt = build_prompt(req.message, req.history, sys_prompt)

    t0 = time.time()
    out = pipe(
        prompt,
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

    # extract
    if "### Assistant:" in out:
        resp = out.split("### Assistant:")[-1].strip()
    elif "### Response:" in out:
        resp = out.split("### Response:")[-1].strip()
    else:
        resp = out.strip()

    if resp.startswith(prompt):
        resp = resp[len(prompt):].strip()

    stops = cfg.stop or [
        "### User:", "### System:", "### Instruction:", "### Response:", "### Assistant:",
        "## User:", "## System:", "## Instruction:", "## Response:", "## Assistant:",
        "\nUser:", "\nSystem:"
    ]

    for m in stops:
        idx = resp.find(m)
        if idx != -1:
            resp = resp[:idx].strip()
            break

    # keep concise
    sentences = re.split(r'(?<=[.!?…])\s+', resp)
    resp = " ".join(sentences[:4]).strip()

    latency_ms = int((time.time() - t0) * 1000)
    return ChatResp(reply=resp[:1200], latency_ms=latency_ms, model=base_model, adapter=adapter)
