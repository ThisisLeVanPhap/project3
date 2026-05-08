import re
from typing import List, Optional

from .state import ConversationState

_BUDGET_KEYWORDS = [
    "budget", "under", "cheaper", "more expensive", "i can spend",
    "ngan sach", "ngân sách", "duoi", "dưới", "re hon", "rẻ hơn",
]
_INTENT_CHANGE_KEYWORDS = [
    "actually", "instead", "not for", "this is for",
    "thuc ra", "thật ra", "doi sang", "đổi sang",
    "khong phai cho", "không phải cho", "cai nay cho", "cái này cho",
]
_AMBIGUITY_KEYWORDS = [
    "khong biet nua", "không biết nữa", "chua ro", "chưa rõ",
    "whatever", "maybe", "not sure", "toi cung khong chac",
    "tôi cũng không chắc", "kho chon qua", "khó chọn quá",
    "hay thoi doi sang cai khac", "hay thôi đổi sang cái khác",
]
_DRIFT_RECOVERY_KEYWORDS = [
    "quay lai cai luc nay", "quay lại cái lúc nãy",
    "go back to the earlier option", "y toi la cai ban dau",
    "ý tôi là cái ban đầu", "let's return to the first direction",
]
_REJECTION_KEYWORDS = [
    "don't like", "not this", "too", "none of these",
    "khong thich", "không thích", "khong hop", "không hợp",
    "khong muon", "không muốn",
]
_REFINEMENT_KEYWORDS = [
    "prefer", "more", "less", "mostly", "mainly",
    "thich", "thích", "uu tien", "ưu tiên", "chu yeu", "chủ yếu",
]
_FINALIZATION_KEYWORDS = [
    "which one", "best", "recommend", "choose",
    "cai nao tot nhat", "cái nào tốt nhất",
    "nen chon cai nao", "nên chọn cái nào", "goi y", "gợi ý",
]
_BUDGET_NUMBER_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:baht|thb|usd|dollars?|k|trieu|triệu)?",
    re.I,
)
_PREFERENCE_TOKEN_RE = re.compile(
    r"\b(prefer|more|less|mostly|mainly)\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+){0,2})",
    re.I,
)
_CATEGORY_HINT_RE = re.compile(
    r"\b(earbuds?|speaker|headset|laptop|phone|smartwatch|watch|gift|quà|tai nghe|loa|đồng hồ|điện thoại)\b",
    re.I,
)
_VI_DIACRITICS_RE = re.compile(
    r"[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]",
    re.I,
)
_VI_WORDS = [
    "mình", "muốn", "cái", "cho", "với", "không", "được", "này", "kia",
    "toi", "tôi", "thich", "thích", "nen", "nên", "quay lai", "quay lại",
]
_EN_WORDS = [
    "i", "want", "for", "with", "not", "this", "that", "maybe", "best",
    "recommend", "budget", "gift", "compare", "back",
]


def detect_language_mode(user_message: str) -> str:
    """
    Example VI-heavy mixed input:
    "Mình muốn cái này nhưng budget chỉ khoảng 3 triệu thôi."

    Example messy repeated-direction input:
    "Maybe not this one. Hay thôi đổi sang cái khác... no wait, quay lại cái ban đầu."
    """
    message = (user_message or "").strip()
    lowered = message.lower()

    vi_score = 0
    en_score = 0

    if _VI_DIACRITICS_RE.search(message):
        vi_score += 2
    vi_score += sum(1 for token in _VI_WORDS if token in lowered)
    en_score += sum(1 for token in _EN_WORDS if re.search(rf"\b{re.escape(token)}\b", lowered))

    if vi_score > 0 and en_score > 0:
        return "mixed"
    if vi_score > 0:
        return "vi"
    return "en"


def extract_signals(user_message: str) -> dict:
    message = (user_message or "").strip().lower()

    budget_change = any(keyword in message for keyword in _BUDGET_KEYWORDS)
    if not budget_change:
        budget_change = bool(
            _BUDGET_NUMBER_RE.search(message)
            and any(currency in message for currency in ["baht", "thb", "usd", "$", "triệu", "trieu"])
        )

    return {
        "budget_change": budget_change,
        "intent_change": any(keyword in message for keyword in _INTENT_CHANGE_KEYWORDS),
        "ambiguity": any(keyword in message for keyword in _AMBIGUITY_KEYWORDS),
        "drift_recovery": any(keyword in message for keyword in _DRIFT_RECOVERY_KEYWORDS),
        "rejection": any(keyword in message for keyword in _REJECTION_KEYWORDS),
        "refinement": any(keyword in message for keyword in _REFINEMENT_KEYWORDS),
        "finalization": any(keyword in message for keyword in _FINALIZATION_KEYWORDS),
    }


def select_behavior(signals: dict) -> str:
    if signals.get("intent_change"):
        return "intent_change"
    if signals.get("drift_recovery"):
        return "conversation_drift_recovery"
    if signals.get("ambiguity"):
        return "ambiguity_handling"
    if signals.get("budget_change"):
        return "budget_adjustment"
    if signals.get("rejection"):
        return "rejection_handling"
    if signals.get("refinement"):
        return "preference_refinement"
    return "shortlist_finalization"


def update_state(
    state: ConversationState,
    signals: dict,
    user_message: str,
) -> ConversationState:
    message = (user_message or "").strip()
    lowered = message.lower()
    state.language_mode = detect_language_mode(message)

    if signals.get("intent_change"):
        if state.intent:
            state.last_stable_intent = state.intent
        if state.category:
            state.inactive_preferences.append(state.category)
        state.category = None
        state.shortlisted_options = []
        # Keep general preferences such as budget/style while deactivating stale direction-specific ones.
        state.preferences = _preserve_general_preferences(state.preferences)

    if signals.get("budget_change"):
        amount = _extract_budget_amount(lowered)
        if amount is not None:
            state.budget["min"] = 0
            state.budget["max"] = amount
            state.budget["currency"] = _extract_currency(lowered)

    if signals.get("ambiguity"):
        state.ambiguity_count += 1
    else:
        state.ambiguity_count = 0

    if signals.get("drift_recovery") and state.last_stable_intent and not state.intent:
        state.intent = state.last_stable_intent

    if signals.get("rejection"):
        rejection_value = _extract_rejection_attribute(message)
        if rejection_value and rejection_value not in state.rejected_attributes:
            state.rejected_attributes.append(rejection_value)

    if signals.get("refinement"):
        category_hint = _extract_category_hint(message)
        if category_hint:
            state.category = category_hint
        for preference in _extract_preferences(message):
            if preference not in state.preferences:
                state.preferences.append(preference)

    if not signals.get("intent_change") and state.intent is None:
        intent_hint = _extract_intent_hint(message)
        if intent_hint:
            state.intent = intent_hint
            state.last_stable_intent = intent_hint

    state.last_behavior = select_behavior(signals)
    return state


def _extract_budget_amount(message: str) -> Optional[float]:
    matches = _BUDGET_NUMBER_RE.findall(message)
    if not matches:
        return None
    raw_amount = matches[-1].replace(",", "")
    try:
        return float(raw_amount) if "." in raw_amount else int(raw_amount)
    except ValueError:
        return None


def _extract_currency(message: str) -> str:
    if "usd" in message or "$" in message or "dollar" in message:
        return "USD"
    return "THB"


def _extract_rejection_attribute(message: str) -> str:
    lowered = message.lower()
    if "none of these" in lowered:
        return "none_of_these"
    if "don't like" in lowered:
        idx = lowered.find("don't like")
        return message[idx:].strip()
    if "not this" in lowered:
        return "not_this"
    if "too " in lowered:
        idx = lowered.find("too ")
        return message[idx:].strip()
    if "không thích" in lowered or "khong thich" in lowered:
        return "khong_thich"
    return "rejected"


def _extract_preferences(message: str) -> List[str]:
    preferences: List[str] = []
    for match in _PREFERENCE_TOKEN_RE.finditer(message):
        preferences.append(
            f"{match.group(1).lower()} {match.group(2).strip().lower()}"
        )

    lowered = message.lower()
    fallback_keywords = [
        "prefer", "more", "less", "mostly", "mainly",
        "thích", "thich", "ưu tiên", "uu tien", "đơn giản", "simple",
    ]
    if not preferences:
        for keyword in fallback_keywords:
            if keyword in lowered:
                preferences.append(keyword)
    return preferences


def _preserve_general_preferences(preferences: List[str]) -> List[str]:
    keep_markers = [
        "budget", "style", "modern", "minimal", "classic", "compact", "portable",
        "daily use", "simple", "gọn", "nhỏ", "tối giản", "hiện đại",
    ]
    preserved: List[str] = []
    for item in preferences:
        lowered = item.lower()
        if any(marker in lowered for marker in keep_markers):
            preserved.append(item)
    return preserved


def _extract_category_hint(message: str) -> Optional[str]:
    match = _CATEGORY_HINT_RE.search(message)
    if not match:
        return None
    return match.group(1).lower()


def _extract_intent_hint(message: str) -> Optional[str]:
    lowered = message.lower()
    if "gift" in lowered or "quà" in lowered:
        return "gift"
    if "daily use" in lowered or "hàng ngày" in lowered or "daily" in lowered:
        return "daily_use"
    if "work" in lowered or "công việc" in lowered:
        return "work"
    return None
