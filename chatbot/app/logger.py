import json, os, time
from typing import Dict, Any

LOG_DIR = os.getenv("LOG_DIR", "./logs")
os.makedirs(LOG_DIR, exist_ok=True)

CHAT_LOG = os.path.join(LOG_DIR, "chat.jsonl")
FEEDBACK_LOG = os.path.join(LOG_DIR, "feedback.jsonl")
DEBUG_TRUE_VALUES = {"1", "true", "yes", "on"}


def _is_enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in DEBUG_TRUE_VALUES

def log_event(obj: Dict[str, Any], path: str = CHAT_LOG):
    row = dict(obj)
    row["timestamp_ms"] = int(time.time() * 1000)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def log_feedback(obj: Dict[str, Any]):
    log_event(obj, FEEDBACK_LOG)


def log_retrieval_debug(obj: Dict[str, Any]):
    if not _is_enabled("RETRIEVAL_DEBUG"):
        return

    row = {"event": "retrieval_debug", **obj}
    log_event(row)

    doc_count = row.get("retrieved_docs", 0)
    scores = row.get("top_scores", [])
    snippets = row.get("selected_context_snippets", [])
    print(f"[retrieval] docs={doc_count} scores={scores}")
    for idx, snippet in enumerate(snippets, start=1):
        print(f"[retrieval] snippet_{idx}: {snippet}")


def log_chat_timing(obj: Dict[str, Any]):
    row = {"event": "chat_timing", **obj}
    log_event(row)

    conv_id = row.get("conversation_id", "anon")
    response_style = row.get("response_style", "natural")
    total_ms = row.get("total_ms", 0)
    retrieval_ms = row.get("retrieval_ms", 0)
    prompt_ms = row.get("prompt_build_ms", 0)
    generation_ms = row.get("generation_ms", 0)
    response_ms = row.get("response_assembly_ms", 0)
    print(
        "[chat_timing] "
        f"conversation_id={conv_id} response_style={response_style} total_ms={total_ms} "
        f"retrieval_ms={retrieval_ms} prompt_build_ms={prompt_ms} "
        f"generation_ms={generation_ms} response_assembly_ms={response_ms}"
    )
