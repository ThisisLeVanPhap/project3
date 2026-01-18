# prompt.py
from typing import List, Optional

DEFAULT_SYSTEM = (
    "You are a helpful sales assistant for a furniture store. "
    "Write clear, friendly, and concise answers (3–5 sentences). "
    "Ask at most ONE clarifying question when needed. "
    "Do not repeat yourself."
)

def build_prompt(message: str, history: List[str], system_prompt: Optional[str] = None) -> str:
    system_hint = system_prompt or DEFAULT_SYSTEM

    # History in this project is treated as user turns (to avoid faking assistant turns).
    convo = [f"### System:\n{system_hint}\n"]
    for turn in history[-6:]:
        convo.append(f"### User:\n{turn}\n")

    convo.append(f"### User:\n{message}\n### Assistant:\n")
    return "".join(convo)
