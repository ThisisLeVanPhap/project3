import re
from typing import List, Optional, Dict, Any

DEFAULT_SYSTEM = (
    "You are a helpful sales assistant for a furniture store. "
    "Write clear, friendly, and concise answers in 2-4 short sentences. "
    "Give at most TWO concrete suggestions or bullets unless the user asks for more. "
    "Ask at most ONE brief clarifying question when needed. "
    "Do not repeat yourself. "
    "Reply in the same language as the user. If the user writes in Vietnamese, reply in Vietnamese.\n"
    "\n"
    "TONE & EMPATHY:\n"
    "- Vary your opening: sometimes 'Bạn có thể cân nhắc...', sometimes 'Một lựa chọn phù hợp là...', sometimes 'Theo mình...'\n"
    "- Show light empathy when appropriate: 'Mình hiểu với không gian nhỏ...', 'Với ngân sách này, mình nghĩ...'\n"
    "- Avoid formulaic patterns and repetitive sentence structures. Mix short and medium-length sentences.\n"
    "- Keep it natural, like a helpful friend giving advice, not a robot listing options.\n"
)

GROUNDING_INSTRUCTIONS = (
    "When verified KB context is provided, ground the answer in that evidence instead of giving generic advice. "
    "Use 1-2 concrete facts from the KB context early in the reply whenever possible. "
    "Prefer concrete product types, materials, size or apartment-fit guidance, and policy details that appear in the KB context. "
    "Treat anything not supported by the KB context as unknown. "
    "Do not invent facts beyond the KB context. If the KB context is thin, say what is actually supported and keep the rest modest."
)

VIETNAMESE_MARKERS = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩị"
    r"òóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]|"
    r"\b(xin chào|tôi|mình|muốn|cần|ghế|sofa|bàn|tủ|phòng|căn hộ|chung cư|"
    r"nhỏ|rẻ|giảm giá|còn hàng|so sánh|đặt hàng|mua)\b",
    re.I,
)

ASCII_VIETNAMESE_PHRASES = re.compile(
    r"\b("
    r"chinh sach|thanh toan|dat coc|chuyen khoan|giao hang|bao hanh|doi tra|"
    r"chat lieu|so sanh|phong khach|can ho|nhu the nao|the nao|cua hang"
    r")\b",
    re.I,
)

ASCII_VIETNAMESE_WORDS = re.compile(
    r"\b("
    r"chinh|sach|thanh|toan|dat|coc|chuyen|khoan|giao|hang|bao|hanh|doi|tra|"
    r"chat|lieu|so|sanh|phong|khach|can|ho|nhu|nao|cua"
    r")\b",
    re.I,
)


def is_vietnamese_text(text: str) -> bool:
    raw = text or ""
    if VIETNAMESE_MARKERS.search(raw):
        return True

    lowered = raw.lower()
    if ASCII_VIETNAMESE_PHRASES.search(lowered):
        return True

    word_hits = {match.group(0) for match in ASCII_VIETNAMESE_WORDS.finditer(lowered)}
    return len(word_hits) >= 3


def _grounding_rules_for_message(message: str) -> str:
    text = (message or "").lower()
    rules = [
        "Do not answer from general sales intuition when verified KB context is available.",
        "Do not add unsupported policy, payment, delivery, product, or material details.",
        "If the KB context is incomplete for the user's exact question, say that briefly instead of guessing.",
    ]

    if re.search(r"\b(payment|pay|thanh toan|dat coc|chuyen khoan|tra gop)\b", text, re.I):
        rules.append(
            "For payment or policy questions, mention only methods, conditions, distance ranges, or contact details that appear in the KB context."
        )
    if re.search(r"\b(compare|difference|vs|chat lieu|vai|da|go|ni|so sanh)\b", text, re.I):
        rules.append(
            "For comparison questions, compare only the attributes explicitly supported in the KB context; if the KB does not support a direct comparison, say so."
        )
    if re.search(r"\b(sofa|can ho|chung cu|phong khach|small|compact|gon)\b", text, re.I):
        rules.append(
            "For sofa guidance, prefer specific apartment-fit or size-fit suggestions from the KB context over broad lifestyle advice."
        )

    return "\n".join(f"- {rule}" for rule in rules)


def build_messages(
    message: str,
    history: List[str],
    system_prompt: Optional[str] = None,
    grounding_context: Optional[str] = None,
) -> List[Dict[str, Any]]:
    system_hint = system_prompt or DEFAULT_SYSTEM

    messages = [{"role": "system", "content": system_hint}]
    if grounding_context:
        messages.append({
            "role": "system",
            "content": (
                f"{GROUNDING_INSTRUCTIONS}\n\n"
                "Grounding rules for this user message:\n"
                f"{_grounding_rules_for_message(message)}\n\n"
                "Verified KB context:\n"
                f"{grounding_context}"
            ),
        })
    if is_vietnamese_text(message):
        messages.append({
            "role": "system",
            "content": (
                "The latest user message is in Vietnamese. "
                "Reply fully in Vietnamese and keep the tone helpful, natural, and sales-oriented. "
                "Keep the answer short and practical, with at most two concrete suggestions. "
                "When KB evidence exists, turn it into specific buyer guidance instead of generic filler."
            ),
        })

    # history is treated as user turns only (as your project intended)
    for turn in history[-6:]:
        messages.append({"role": "user", "content": turn})

    messages.append({"role": "user", "content": message})
    return messages
