# prompt.py
from typing import List, Optional

DEFAULT_SYSTEM = (
    "Bạn là trợ lý AI tiếng Việt. "
    "Hãy trả lời ngắn gọn, mạch lạc (3–5 câu), không lặp ý."
)

def build_prompt(message: str, history: List[str], system_prompt: Optional[str] = None) -> str:
    system_hint = system_prompt or DEFAULT_SYSTEM

    # Nếu history chỉ là các câu user trước đó -> encode thành User turns, KHÔNG fake assistant
    convo = [f"### System:\n{system_hint}\n"]
    for turn in history[-3:]:
        convo.append(f"### User:\n{turn}\n")

    convo.append(f"### User:\n{message}\n### Assistant:\n")
    return "".join(convo)
