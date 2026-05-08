import re
from typing import Dict, Any, Optional

# --- Consultation-specific patterns ---
RX_ROOM_TYPE = re.compile(
    r"\b(living room|phòng khách|bedroom|phòng ngủ|dining room|phòng ăn|kitchen|bếp|"
    r"home office|văn phòng tại nhà|apartment|căn hộ|studio|balcony|ban công)\b",
    re.I,
)
RX_ROOM_SIZE = re.compile(
    r"\b(\d{1,3}(?:[.,]\d{2})?)\s*(m²|m2|sqm|square meters|mét vuông)\b",
    re.I,
)
RX_PRODUCT_TYPE = re.compile(
    r"\b(sofa|ghế sofa|bed|giường|table|bàn|dining table|bàn ăn|"
    r"wardrobe|tủ|cabinet|tủ tủ|bookshelf|kệ sách|chair|ghế|desk|bàn làm việc)\b",
    re.I,
)
RX_PRODUCT_TYPE_VI = re.compile(
    r"\b(ghế sofa|sofa|giường|bed|bàn|table|tủ|wardrobe|kệ|shelf|ghế|chair|bàn làm việc|desk)\b",
    re.I,
)
RX_BUDGET_RANGE = re.compile(
    r"\b(\d+)\s*(?:-|to|đến|tới)\s*(\d+)\s*(triệu|tr|nghìn|k|vnd|vnđ|\$|usd)?\b",
    re.I,
)
RX_STYLE = re.compile(
    r"\b(modern|minimal|classic|scandinavian|boho|industrial|luxury)\b",
    re.I,
)
RX_STYLE_VI = re.compile(
    r"\b(hiện đại|tối giản|cổ điển|bắc âu|boho|công nghiệp|cao cấp|luxury)\b",
    re.I,
)
RX_PHONE = re.compile(
    r"(?<![\d])(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?![\d])"
)
STYLE_MAP_VI = {
    "hiện đại": "modern",
    "tối giản": "minimal",
    "cổ điển": "classic",
    "bắc âu": "scandinavian",
    "boho": "boho",
    "công nghiệp": "industrial",
    "cao cấp": "luxury",
}

# Room type mapping for normalization
ROOM_TYPE_MAP = {
    "living room": "living_room",
    "phòng khách": "living_room",
    "bedroom": "bedroom",
    "phòng ngủ": "bedroom",
    "dining room": "dining_room",
    "phòng ăn": "dining_room",
    "kitchen": "kitchen",
    "bếp": "kitchen",
    "home office": "office",
    "văn phòng tại nhà": "office",
    "apartment": "apartment",
    "căn hộ": "apartment",
    "studio": "studio",
    "balcony": "balcony",
    "ban công": "balcony",
}

# Budget range mapping (in million VND or USD)
BUDGET_LEVELS = {
    "low": {"min": 0, "max": 5, "currency": "triệu"},
    "medium": {"min": 5, "max": 15, "currency": "triệu"},
    "high": {"min": 15, "max": 100, "currency": "triệu"},
}


def extract_consultation_slots(text: str) -> Dict[str, Any]:
    """
    Extract consultation-specific attributes from user message.
    Returns a dict with keys: room_type, room_size_sqm, budget_range, style_preference, product_type
    """
    t = text or ""
    slots: Dict[str, Any] = {}

    # Room type
    room_match = RX_ROOM_TYPE.search(t)
    if room_match:
        raw_room = room_match.group(1).lower()
        slots["room_type"] = ROOM_TYPE_MAP.get(raw_room, raw_room)

    # Room size (in sqm)
    size_match = RX_ROOM_SIZE.search(t)
    if size_match:
        try:
            size_str = size_match.group(1).replace(",", ".")
            slots["room_size_sqm"] = float(size_str)
        except ValueError:
            pass

    # Product type
    prod_match = RX_PRODUCT_TYPE.search(t)
    if not prod_match:
        prod_match = RX_PRODUCT_TYPE_VI.search(t)
    if prod_match:
        slots["product_type"] = prod_match.group(1).lower()

    # Budget range
    budget_range_match = RX_BUDGET_RANGE.search(t)
    if budget_range_match:
        min_val = float(budget_range_match.group(1))
        max_val = float(budget_range_match.group(2))
        currency = budget_range_match.group(3) or "triệu"
        slots["budget_range"] = {
            "min": min_val,
            "max": max_val,
            "currency": currency.lower()
        }
    else:
        # Check for simple budget mentions (e.g., "under 5 million")
        if re.search(r"\b(under|dưới|tối đa)\s*(\d+)\s*(triệu|tr|nghìn|k)", t, re.I):
            m = re.search(r"(\d+)\s*(triệu|tr|nghìn|k)", t, re.I)
            if m:
                val = float(m.group(1))
                slots["budget_range"] = {"min": 0, "max": val, "currency": m.group(2).lower()}

    # Style preference
    style_match = RX_STYLE.search(t)
    if not style_match:
        style_match = RX_STYLE_VI.search(t)
    if style_match:
        raw_style = style_match.group(1).lower()
        slots["style_preference"] = STYLE_MAP_VI.get(raw_style, raw_style)

    return slots


def detect_interest(text: str) -> bool:
    """
    Detect if user has expressed interest in purchasing/ordering.
    """
    interest_patterns = [
        r"\b(mua|đặt|order|buy|chốt|decide|chọn|pick|lấy|ok|được|okey|yes|có)\b",
        r"\b(gửi link|link sản phẩm|product link|xem link)\b",
        r"\b(giá bao nhiêu|giá|price|bao nhiêu tiền)\b",
    ]
    t = text or ""
    for pattern in interest_patterns:
        if re.search(pattern, t, re.I):
            return True
    return False


def extract_phone(text: str) -> Optional[str]:
    """
    Extract Vietnamese phone number from text.
    Returns cleaned numeric string (e.g., "0901234567")
    """
    t = text or ""
    match = RX_PHONE.search(t)
    if match:
        phone = match.group()
        # Clean to digits only, keep leading + if present
        return re.sub(r"[^\d+]", "", phone)
    return None


def build_consultation_prefix(stage: str, slots: Dict[str, Any]) -> str:
    """
    Build a system prompt prefix for the general consumer consultation flow.
    This guides the LLM to act as a shopping advisor.
    """
    parts = []
    changes = []

    # Track preference changes (same keys as in sales flow)
    for key in ["style_preference", "color", "material", "budget_range", "room_type"]:
        prev_key = f"{key}_prev"
        if key in slots and prev_key in slots:
            old = slots[prev_key]
            new = slots[key]
            if old != new:
                changes.append(f"{key}: {old} → {new}")

    # Summarize known customer context
    if slots.get("room_type"):
        parts.append(f"Room: {slots['room_type']}")
    if slots.get("room_size_sqm"):
        parts.append(f"Size: ~{slots['room_size_sqm']}m²")
    if slots.get("product_type"):
        parts.append(f"Looking for: {slots['product_type']}")
    if slots.get("budget_range"):
        b = slots["budget_range"]
        parts.append(f"Budget: {b['min']}-{b['max']} {b.get('currency', '')}")
    if slots.get("style_preference"):
        parts.append(f"Style: {slots['style_preference']}")
    if slots.get("color"):
        parts.append(f"Color preference: {slots['color']}")
    if slots.get("material"):
        parts.append(f"Material preference: {slots['material']}")

    context = " | ".join(parts) if parts else "No preferences collected yet"

    # Add change information if any
    change_note = ""
    if changes:
        change_note = "Recent changes: " + "; ".join(changes) + ".\n"

    stage_instructions = {
        "discover": (
            "You are in DISCOVER stage. "
            "Ask 1-2 friendly questions to understand: "
            "1) Which room they're furnishing, "
            "2) What product they need, "
            "3) Approximate budget. "
            "Keep questions short and natural. Do NOT overwhelm with options yet."
        ),
        "propose": (
            "You are in PROPOSE stage. "
            "Based on collected preferences, give 1-2 specific suggestions. "
            "Mention why the suggestion fits their room size, budget, and style. "
            "Ask ONE follow-up question to refine further."
        ),
        "refine": (
            "You are in REFINE stage. "
            "The user has provided more details. "
            "Offer more specific advice, material recommendations, or layout tips. "
            "If they seem ready, gently guide toward next steps."
        ),
        "lead_capture": (
            "You are in LEAD CAPTURE stage. "
            "The user has shown interest in purchasing. "
            "Ask for their phone number so staff can contact them. "
            "Also ask for their name (optional). "
            "Keep it simple: 'Bạn để lại SĐT nhé, nhân viên sẽ liên hệ tư vấn chi tiết.'"
        ),
        "close": (
            "You are in CLOSE stage. "
            "Thank them and confirm that their request has been saved. "
            "Tell them staff will contact them soon. "
            "Offer: 'Bạn có thể xem thêm sản phẩm, hoặc nói chuyện với nhân viên để được hỗ trợ thêm.'"
        ),
        "handoff": (
            "You are in HANDOFF stage. "
            "Provide contact information and reassure help is coming."
        ),
    }

    current_stage = stage if stage in stage_instructions else "discover"

    return (
        f"[AI Interior Shopping Advisor]\n"
        f"Current stage: {current_stage.upper()}\n"
        f"Customer context: {context}\n"
        f"{change_note}"
        f"\n{stage_instructions[current_stage]}\n\n"
        "IMPORTANT:\n"
        "- Be conversational but focused. Do NOT give generic advice.\n"
        "- Reference their specific preferences (style, color, material, budget, room size) in every response.\n"
        "- If they mention a product, explain WHY it suits their situation.\n"
        "- If information is missing, ask ONE clarifying question.\n"
        "- Keep answers concise (2-3 sentences) unless they ask for details.\n"
        "- Reply in the same language as the user.\n"
        "- ACKNOWLEDGE CHANGES: If you see a 'Recent changes' note, acknowledge the user's updated preference naturally. Example: 'I see you've changed from X to Y—that's a great choice for...'\n"
        "\n"
        "NATURALNESS:\n"
        "- Vary your openings: 'Bạn có thể cân nhắc...', 'Một lựa chọn tốt là...', 'Theo mình...', 'Mình nghĩ...'\n"
        "- Show light empathy: 'Mình hiểu phòng nhỏ sẽ khó chọn...', 'Với khoảng ngân sách này...'\n"
        "- Avoid bullet-point lists unless user asks for step-by-step. Use flowing sentences.\n"
        "- Mix sentence structures. Don't be robotic or repetitive.\n"
        "- Sound like a real shopping friend giving honest advice.\n"
        "\n"
        "OFF-TOPIC & DISENGAGEMENT:\n"
        "- If user asks about unrelated topics (politics, sports, weather, personal questions), politely redirect: 'Mình là trợ lý tư vấn nội thất, mình có thể giúp gì cho bạn về ghế, bàn, tủ hay các sản phẩm khác?'\n"
        "- If user indicates disengagement ('thôi', 'để sau', 'ok rồi'), respond with a soft close: 'Tạm biệt! Nếu sau này cần tư vấn, bạn cứ quay lại nhé.' and transition to handoff.\n"
    )


def next_consultation_stage(current: str, slots: Dict[str, Any], user_text: str) -> str:
    """
    Simple state machine for consultation flow.
    """
    text_lower = user_text.lower()

    # Check for handoff intent
    if re.search(r"\b(talk to|human|agent|staff|nhân viên|tư vấn viên|người thật)\b", user_text, re.I):
        return "handoff"

    # Check for disengagement - soft close to handoff
    disengage_phrases = [
        "thôi", "thoát", "dừng", "dừng lại", "không còn", "không cần",
        "để sau", "sau này", "khi khác", "bỏ đi", "hủy",
        "ok rồi", "được rồi", "xong rồi", "vậy thôi", "vậy nhé",
        "tạm biệt", "bye", "goodbye"
    ]
    if len(user_text.split()) <= 4:
        for phrase in disengage_phrases:
            if phrase in text_lower:
                return "handoff"

    # Check for off-topic - stay in current stage but will trigger redirect in LLM
    off_topic_patterns = [
        r"\b(politics|bầu cử|chính trị|thể thao|bóng đá|football|kinh nghiệm cá nhân)\b",
        r"\b(đi chơi|đi du lịch|du lịch|đi chỗ nào|ăn gì hôm nay)\b",
        r"\b(trà sữa|coffee|cafe|nước uống|đi ăn)\b",
        r"\b(weather|thời tiết|nóng|lạnh|mưa)\b",
        r"\b(how are you|how do you feel|bạn khỏe không|khỏe không)\b",
        r"\b(tên bạn|bạn là ai|who are you|what are you)\b",
    ]
    for pattern in off_topic_patterns:
        if re.search(pattern, text_lower, re.I):
            return current  # stay in current stage, LLM will redirect

    # Discover -> Propose: when we have at least 2 pieces of info
    if current == "discover":
        info_count = sum(1 for k in ["room_type", "product_type", "budget_range", "style_preference"] if slots.get(k))
        if info_count >= 2:
            return "propose"

    # Propose -> Refine: when user asks follow-up or provides more constraints
    if current == "propose":
        if len(user_text.split()) > 15 or re.search(r"\b(more|chi tiết|detail|so sánh|compare)\b", user_text, re.I):
            return "refine"

    # Refine -> Lead Capture: when user expresses intent to buy/decide
    if current == "refine":
        if detect_interest(user_text):
            return "lead_capture"

    # Lead Capture -> Close: when phone number is provided
    if current == "lead_capture":
        if extract_phone(user_text):
            return "close"

    return current
