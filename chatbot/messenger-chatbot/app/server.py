import os
import time
import re
import threading
from typing import List, Optional, Dict, Tuple, Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .model_loader import get_pipeline
from .prompt import build_prompt

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
    # chạy warmup nền để server lên ngay, /healthz trả OK luôn
    def run():
        try:
            get_or_create_pipe(BASE_MODEL_DEFAULT, ADAPTER_DEFAULT, TOKENIZER_DEFAULT)
        except Exception as e:
            print("[warmup] failed:", e)

    threading.Thread(target=run, daemon=True).start()

@app.get("/healthz")
def healthz():
    return {"status": "ok", "cached_pipelines": len(PIPE_CACHE)}

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

    prompt = build_prompt(req.message, req.history, cfg.system_prompt)

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

    # Robust extract: ưu tiên "### Assistant:" nếu có, fallback raw
    if "### Assistant:" in out:
        resp = out.split("### Assistant:")[-1].strip()
    elif "### Response:" in out:
        resp = out.split("### Response:")[-1].strip()
    else:
        resp = out.strip()

    # Nếu pipeline vẫn trả full text (prompt + completion) → cắt prompt
    if resp.startswith(prompt):
        resp = resp[len(prompt):].strip()

    # stop markers
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
    
    sentences = re.split(r'(?<=[.!?…])\s+', resp)
    resp = " ".join(sentences[:4]).strip()

    latency_ms = int((time.time() - t0) * 1000)
    return ChatResp(reply=resp[:1200], latency_ms=latency_ms, model=base_model, adapter=adapter)
