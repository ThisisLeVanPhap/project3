import json, os, time
from typing import Dict, Any

LOG_DIR = os.getenv("LOG_DIR", "./logs")
os.makedirs(LOG_DIR, exist_ok=True)

CHAT_LOG = os.path.join(LOG_DIR, "chat.jsonl")
FEEDBACK_LOG = os.path.join(LOG_DIR, "feedback.jsonl")

def log_event(obj: Dict[str, Any], path: str = CHAT_LOG):
    row = dict(obj)
    row["timestamp_ms"] = int(time.time() * 1000)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def log_feedback(obj: Dict[str, Any]):
    log_event(obj, FEEDBACK_LOG)
