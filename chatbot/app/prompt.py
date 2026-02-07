# prompt.py
from typing import List, Optional, Dict, Any

DEFAULT_SYSTEM = (
    "You are a helpful sales assistant for a furniture store. "
    "Write clear, friendly, and concise answers (3–5 sentences). "
    "Ask at most ONE clarifying question when needed. "
    "Do not repeat yourself."
)

def build_messages(message: str, history: List[str], system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
    system_hint = system_prompt or DEFAULT_SYSTEM

    messages = [{"role": "system", "content": system_hint}]

    # history is treated as user turns only (as your project intended)
    for turn in history[-6:]:
        messages.append({"role": "user", "content": turn})

    messages.append({"role": "user", "content": message})
    return messages
