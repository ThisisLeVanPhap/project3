import os
import json
import time
from typing import List, Optional

import requests
from fastapi import FastAPI, Request
from pydantic import BaseModel


from .model_loader import get_pipeline
from .prompt import build_prompt

# ----- Env -----
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "my-verify")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
ADAPTER_PATH = os.getenv("LORA_ADAPTER", "out/lora_adapter")
BASE_MODEL = os.getenv("BASE_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "256"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
TOP_P = float(os.getenv("TOP_P", "0.9"))


app = FastAPI(title="Messenger Chatbot")
pipe = None


class ChatReq(BaseModel):
    message: str
    history: Optional[List[str]] = []

@app.on_event("startup")
def _warmup():
    global pipe
    t0 = time.time()
    pipe = get_pipeline(base=BASE_MODEL, adapter=ADAPTER_PATH)
    print(f"Model loaded in {time.time()-t0:.2f}s | base={BASE_MODEL} | adapter={ADAPTER_PATH}")

@app.get("/healthz")
def healthz():
    return {"status": "ok", "base": BASE_MODEL, "adapter": ADAPTER_PATH}

@app.post("/chat")
def chat(req: ChatReq):
    prompt = build_prompt(req.message, req.history or [])
    t0 = time.time()
    out = pipe(
        prompt,
        max_new_tokens=120,
        min_new_tokens=40,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        top_k=50,
        no_repeat_ngram_size=3,
        repetition_penalty=1.15,
        pad_token_id=pipe.tokenizer.eos_token_id,
        eos_token_id=pipe.tokenizer.eos_token_id,
    )[0]["generated_text"]

    # Lấy phần sau "### Response:"
    resp = out.split("### Response:")[-1].strip()

    # Cắt tiếp nếu model bắt đầu sinh thêm turn mới
    stop_markers = [
        "### User:",
        "## # User:",
        "### Instruction:",
        "### Input:",
        "\nUser:",
        "\n# User:",
        "\n## User:",
    ]
    for m in stop_markers:
        idx = resp.find(m)
        if idx != -1:
            resp = resp[:idx].strip()
            break

    # Giữ lại tối đa ~4 câu cho gọn
    import re
    sentences = re.split(r'(?<=[.!?…])\s+', resp)
    resp = " ".join(sentences[:4])

    return {
        "reply": resp[:1200],
        "latency_ms": int((time.time() - t0) * 1000),
        "model": BASE_MODEL,
        "adapter": ADAPTER_PATH,
    }

# -------- Messenger webhook --------
@app.get("/webhook")
def verify(hub_mode: str = None, hub_challenge: str = None, hub_verify_token: str = None):
    if hub_verify_token == FB_VERIFY_TOKEN:
        try:
            return int(hub_challenge or 0)
        except Exception:
            return hub_challenge or "" # sometimes FB expects raw string
    return {"status": "forbidden"}

def reply_text(psid: str, text: str):
    if not FB_PAGE_TOKEN:
        print("[WARN] FB_PAGE_TOKEN not set; skipping send.")
        return
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={FB_PAGE_TOKEN}"
    body = {"recipient": {"id": psid}, "message": {"text": text[:640]}}
    try:
        requests.post(url, json=body, timeout=10)
    except Exception as e:
        print("[ERR] send message:", e)

@app.post("/webhook")
async def receive(req: Request):
    payload = await req.json()
    entries = payload.get("entry", [])
    for entry in entries:      
        for msg in entry.get("messaging", []):
            sender = msg.get("sender", {}).get("id") 
            if not sender:
                continue 
            # Only text for demo
            text = msg.get("message", {}).get("text")
            if text:
                bot = chat(ChatReq(message=text, history=[]))
                reply_text(sender, bot.get("reply", "Xin lỗi, mình đang lỗi :("))
    return {"status": "ok"}