import re
import unicodedata
from typing import Dict, Any

RX_BUDGET = re.compile(r"\b(\$|usd)\s*([0-9]{2,5})\b|under\s*\$?\s*([0-9]{2,5})\b", re.I)
RX_BUDGET_VI = re.compile(
    r"\b(?:ng[aâ]n s[aá]ch|t[aầ]m gi[aá]|kho[aả]ng|dưới|tối đa)\s*"
    r"([0-9]+(?:[.,][0-9]+)?)\s*(triệu|tr|nghìn|k|vnd|vnđ)?\b",
    re.I,
)
RX_BUDGET_RANGE = re.compile(
    r"\b(\d+)\s*(?:-|to|đến|tới)\s*(\d+)\s*(triệu|tr|nghìn|k|vnd|vnđ|\$|usd)?\b",
    re.I,
)
RX_SMALL = re.compile(r"\b(small|tiny|compact|studio|apartment|small room)\b", re.I)
RX_SMALL_VI = re.compile(r"\b(nhỏ|chật|gọn|căn hộ|chung cư|phòng nhỏ|studio)\b", re.I)
RX_PETS = re.compile(r"\b(pet|dog|cat)\b", re.I)
RX_PETS_VI = re.compile(r"\b(thú cưng|chó|mèo)\b", re.I)
RX_KIDS = re.compile(r"\b(kid|child|toddler|baby)\b", re.I)
RX_KIDS_VI = re.compile(r"\b(trẻ em|em bé|bé|con nhỏ|trẻ nhỏ)\b", re.I)
RX_BACK_PAIN = re.compile(r"\b(back pain|lumbar|spine|ergonomic|long sitting)\b", re.I)
RX_BACK_PAIN_VI = re.compile(r"\b(đau lưng|mỏi lưng|ngồi lâu|cột sống|êm lưng|tựa lưng)\b", re.I)
RX_EASY_CLEAN = re.compile(r"\b(easy to clean|washable|clean easily|stain resistant)\b", re.I)
RX_EASY_CLEAN_VI = re.compile(r"\b(dễ vệ sinh|de ve sinh|dễ lau|de lau|chống bẩn|chong ban|ít bám bụi|it bam bui)\b", re.I)
RX_DURABILITY_OBJECTION = re.compile(r"\b(bền không|ben khong|có bền|co ben|durable|last long|chắc không|chac khong)\b", re.I)
RX_EXPENSIVE_OBJECTION = re.compile(r"\b(đắt quá|dat qua|hơi đắt|hoi dat|mắc quá|mac qua|expensive|too much|over budget)\b", re.I)
RX_NOT_READY = re.compile(r"\b(chưa chắc|chua chac|cân nhắc|can nhac|để nghĩ|de nghi|not sure|think about|maybe later)\b", re.I)
RX_STYLE = re.compile(r"\b(modern|minimal|classic|scandinavian|boho|industrial|luxury)\b", re.I)
RX_STYLE_VI = re.compile(r"\b(hiện đại|tối giản|cổ điển|bắc âu|boho|công nghiệp|cao cấp|luxury)\b", re.I)
STYLE_MAP_VI = {
    "hiện đại": "modern",
    "tối giản": "minimal",
    "cổ điển": "classic",
    "bắc âu": "scandinavian",
    "boho": "boho",
    "công nghiệp": "industrial",
    "cao cấp": "luxury",
}

def _repair_mojibake(text: str) -> str:
    repaired = text or ""
    for _ in range(3):
        changed = False
        for encoding in ("latin1", "cp1252"):
            try:
                candidate = repaired.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if candidate != repaired:
                repaired = candidate
                changed = True
                break
        if not changed:
            break
    return repaired


def _ascii_fold(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _match_text(text: str) -> str:
    raw = text or ""
    repaired = _repair_mojibake(raw)
    return " ".join([raw, repaired, _ascii_fold(repaired)]).lower()


def _has_handoff(text: str) -> bool:
    folded = _match_text(text)
    return RX_HANDOFF.search(text or "") is not None or re.search(
        r"\b(human|agent|staff|nhan vien|tu van vien|nguoi that)\b",
        folded,
        re.I,
    ) is not None


def _has_compare(text: str) -> bool:
    folded = _match_text(text)
    return RX_COMPARE.search(text or "") is not None or re.search(
        r"\b(compare|comparison|difference|vs|so sanh|khac nhau)\b",
        folded,
        re.I,
    ) is not None


# Color patterns (English and Vietnamese)
RX_COLOR = re.compile(
    r"\b(white|black|gray|grey|brown|beige|cream|yellow|blue|green|red|navy|"
    r"trắng|đen|xám|nâu|be|kem|vàng|xanh|đỏ|lục|tím|hồng|nâu)\b",
    re.I
)
RX_COLOR_SPECIFIC = re.compile(
    r"\b(light|dark|pale|deep|mint|navy|burgundy|teal|olive|sage)\s+(blue|green|red|brown|gray)\b",
    re.I
)

# Material patterns
RX_MATERIAL = re.compile(
    r"\b(wood|oak|walnut|pine|leather|fabric|velvet|cotton|linen|"
    r"metal|steel|iron|gold|brass|glass|marble|granite|"
    r"gỗ|sắt|đồng|thép|kim loại|da|vải|nhung|ren|thổ cẩm|gốm)\b",
    re.I
)
RX_HANDOFF = re.compile(
    r"\b(talk to|human|agent|staff|nh[aâ]n vi[eê]n|tư v[aấ]n vi[eê]n|người thật)\b",
    re.I,
)
RX_COMPARE = re.compile(r"\b(compare|difference|vs|so s[aá]nh|kh[aá]c nhau|so với)\b", re.I)
RX_BUY = re.compile(
    r"\b(buy|order|checkout|purchase|mua|đặt hàng|chốt đơn|lên đơn|thanh toán)\b",
    re.I,
)
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


def _format_budget_text(amount: str, unit: str) -> str:
    raw_amount = amount.replace(",", ".")
    return raw_amount if not unit else f"{raw_amount} {unit.lower()}"


def extract_slots(text: str) -> Dict[str, Any]:
    t = text or ""
    mt = _match_text(t)
    slots: Dict[str, Any] = {}

    m = RX_BUDGET.search(t)
    if m:
        num = m.group(2) or m.group(3)
        if num:
            slots["budget_usd"] = int(num)
    else:
        m_vi = RX_BUDGET_VI.search(t)
        if m_vi:
            slots["budget_text"] = _format_budget_text(m_vi.group(1), m_vi.group(2) or "")
        elif re.search(r"\b(ngan sach|tam gia|khoang|duoi|toi da)\b", mt):
            amount = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*([^\s,.;]*)", t)
            if amount:
                slots["budget_text"] = _format_budget_text(amount.group(1), amount.group(2) or "")

    room_match = RX_ROOM_TYPE.search(t)
    if room_match:
        slots["room"] = room_match.group(1).lower()

    constraints = []
    if RX_SMALL.search(t) or RX_SMALL_VI.search(t) or re.search(r"\b(small|tiny|compact|studio|apartment|nho|chat|gon|can ho|chung cu|phong nho)\b", mt):
        slots["space"] = "small"
        constraints.append("small_room")
    if RX_PETS.search(t) or RX_PETS_VI.search(t) or re.search(r"\b(pet|dog|cat|thu cung|cho|meo)\b", mt):
        slots["pets"] = True
        constraints.append("pets")
    if RX_KIDS.search(t) or RX_KIDS_VI.search(t) or re.search(r"\b(kid|child|toddler|baby|tre em|em be|be|con nho)\b", mt):
        slots["kids"] = True
        slots["children"] = True
        constraints.append("children")
    if RX_BACK_PAIN.search(t) or RX_BACK_PAIN_VI.search(t) or re.search(r"\b(back pain|lumbar|dau lung|moi lung|ngoi lau|cot song|tua lung)\b", mt):
        slots["back_pain"] = True
        slots["health_need"] = "back_pain"
        constraints.append("back_pain")
    if RX_EASY_CLEAN.search(t) or RX_EASY_CLEAN_VI.search(t) or re.search(r"\b(easy clean|easy to clean|washable|de ve sinh|de lau|chong ban|it bam bui)\b", mt):
        slots["easy_clean"] = True
        constraints.append("easy_clean")

    objection_type = None
    if RX_EXPENSIVE_OBJECTION.search(t) or re.search(r"\b(dat qua|hoi dat|mac qua|too expensive|over budget)\b", mt):
        objection_type = "too_expensive"
    elif RX_DURABILITY_OBJECTION.search(t) or re.search(r"\b(ben khong|co ben|durable|last long|chac khong)\b", mt):
        objection_type = "durability"
    elif slots.get("easy_clean"):
        objection_type = "easy_clean" if re.search(r"\b(co hop|phu hop|duoc khong|khong|khó|kho|concern|worry)\b", mt) else None
    elif slots.get("pets"):
        objection_type = "pets" if re.search(r"\b(co hop|phu hop|duoc khong|khong|concern|worry)\b", mt) else None
    elif slots.get("children"):
        objection_type = "children" if re.search(r"\b(co hop|phu hop|duoc khong|khong|concern|worry)\b", mt) else None
    elif slots.get("back_pain"):
        objection_type = "back_pain" if re.search(r"\b(co hop|phu hop|duoc khong|khong|concern|worry)\b", mt) else None
    elif slots.get("space") == "small" and re.search(r"\b(co hop|phu hop|duoc khong|khong|fit|vua|chat)\b", mt):
        objection_type = "small_room_fit"
    elif RX_NOT_READY.search(t) or re.search(r"\b(chua chac|can nhac|de nghi|not sure|think about|maybe later)\b", mt):
        objection_type = "not_ready"
    if objection_type:
        slots["objection_type"] = objection_type
    if constraints:
        slots["constraints"] = constraints

    # Style extraction
    m2 = RX_STYLE.search(t)
    if m2:
        slots["style"] = m2.group(1).lower()
    else:
        m2_vi = RX_STYLE_VI.search(t)
        if m2_vi:
            slots["style"] = STYLE_MAP_VI[m2_vi.group(1).lower()]
        elif re.search(r"\bhien dai\b", mt):
            slots["style"] = "modern"
        elif re.search(r"\btoi gian\b", mt):
            slots["style"] = "minimal"
        elif re.search(r"\bco dien\b", mt):
            slots["style"] = "classic"

    # Color extraction (first match only)
    color_match = RX_COLOR.search(t)
    if color_match:
        slots["color"] = color_match.group(1).lower()
    else:
        color_specific = RX_COLOR_SPECIFIC.search(t)
        if color_specific:
            slots["color"] = f"{color_specific.group(1)} {color_specific.group(2)}".lower()

    # Material extraction (first match only)
    material_match = RX_MATERIAL.search(t)
    if material_match:
        slots["material"] = material_match.group(1).lower()

    return slots


def detect_intent(user_text: str, stage: str = "discover") -> str:
    """Classify user intent: provide_info, ask_info, hesitation, irrelevant, confirm, off_topic, disengage

    Context-aware rules:
    - In close stage: short affirmatives (ok, yes, được, đồng ý) count as confirm
    - In other stages: only explicit purchase phrases trigger confirm
    - Question/hesitation always override
    """
    if not user_text:
        return "irrelevant"

    text = user_text.strip()
    text_lower = _match_text(text)
    word_count = len(text.split())

    # 1. QUESTION DETECTION (strong override for all stages)
    if text.endswith("?") or "?" in text:
        return "ask_info"

    question_starters = ["what", "where", "when", "why", "how", "gì", "làm sao", "thế nào",
                         "khi nào", "bao nhiêu", "có", "phải không", "đúng không", "ạ"]
    if any(text_lower.startswith(q) for q in question_starters):
        return "ask_info"

    # 2. HESITATION DETECTION (strong override for all stages)
    hesitation_phrases = [
        "không chắc", "chưa biết", "chưa rõ", "để nghĩ", "suy nghĩ", "cân nhắc",
        "maybe", "not sure", "consider", "think about", "cần time", "cần suy nghĩ",
        "lưỡng lự", "chờ đã", "đợi đã", "tôi chưa", "toi chua", "tôi không chắc",
        "toi khong chac", "chưa quyết", "chưa quyet", "tôi do dự", "toi do du"
    ]
    for phrase in hesitation_phrases:
        if phrase in text_lower:
            return "hesitation"

    # 3. DISENGAGEMENT DETECTION (user wants to stop/pause)
    disengage_phrases = [
        "thôi", "thoát", "dừng lại", "dừng", "không còn", "không cần",
        "để sau", "sau này", "khi khác", "bỏ đi", "hủy",
        "ok rồi", "được rồi", "xong rồi", "vậy thôi", "vậy nhé",
        "tạm biệt", "bye", "goodbye", "cảm ơn", "thank you"
    ]
    # Disengagement typically short message
    if word_count <= 4:
        for phrase in disengage_phrases:
            if phrase in text_lower:
                return "disengage"

    # 4. OFF-TOPIC DETECTION (unrelated to furniture/shopping)
    # Only clear off-topic phrases, NOT single words (cafe, coffee alone = false positive)
    off_topic_patterns = [
        r"\b(politics|bầu cử|chính trị|thể thao|bóng đá|football)\b",
        r"\b(đi chơi|đi du lịch|du lịch|đi chỗ nào|ăn gì hôm nay)\b",
        r"\b(trà sữa|đi ăn|nhà hàng|restaurant)\b",
        r"\b(weather|thời tiết|nóng|lạnh|mưa|nắng)\b",
        r"\b(how are you|how do you feel|bạn khỏe không|khỏe không)\b",
        r"\b(tên bạn|bạn là ai|who are you|what are you)\b",
    ]
    for pattern in off_topic_patterns:
        if re.search(pattern, text_lower, re.I):
            return "off_topic"

    # 5. CONTEXT-AWARE CONFIRM DETECTION
    # Stage-specific rules
    if stage == "close":
        # In close stage, accept short affirmatives (user ready to finalize)
        short_affirmatives = ["ok", "oke", "yes", "vâng", "được", "đồng ý", "accept", "confirmed"]
        # Only if message is short (1-3 words) and not a question/hesitation
        if word_count <= 3:
            for word in short_affirmatives:
                if word in text_lower.split():
                    return "confirm"
        # Also check for stronger confirm phrases (any length)
        strong_confirm_phrases = [
            r"\bđồng ý mua\b", r"\bxác nhận mua\b", r"\bxác nhận đặt hàng\b",
            r"\bđặt hàng ngay\b", r"\bmua ngay\b", r"\bchốt đơn\b",
            r"\bthanh toán\b", r"\blên đơn\b", r"\bđặt luôn\b",
            r"\btiền đâu\b", r"\bđược đó\b", r"\bvâng ạ\b",
            r"\bconfirm\b", r"\byes please\b", r"\blet's do it\b",
            r"\bi'll take it\b", r"\baccepted\b", r"\bagree to purchase\b",
            r"\bproceed with order\b"
        ]
        for pattern in strong_confirm_phrases:
            if re.search(pattern, text_lower, re.I):
                return "confirm"
    else:
        # In earlier stages (discover, propose, compare), only explicit purchase phrases
        confirm_phrases = [
            r"\bđồng ý mua\b", r"\bxác nhận mua\b", r"\bxác nhận đặt hàng\b",
            r"\bđặt hàng ngay\b", r"\bmua ngay\b", r"\bchốt đơn\b",
            r"\bthanh toán\b", r"\blên đơn\b", r"\bđặt luôn\b",
            r"\btiền đâu\b", r"\bđược đó\b", r"\bvâng ạ\b",
            r"\bconfirm\b", r"\byes please\b", r"\blet's do it\b",
            r"\bi'll take it\b", r"\baccepted\b", r"\bagree to purchase\b",
            r"\bproceed with order\b"
        ]
        for pattern in confirm_phrases:
            if re.search(pattern, text_lower, re.I):
                return "confirm"

    # 6. Negative filter - if message is short greeting/thanks, mark irrelevant
    irrelevant_phrases = ["hello", "hi", "hey", "xin chào", "chào", "cảm ơn", "thank",
                          "thanks", "good morning", "good evening", "chúc"]
    if any(phrase in text_lower for phrase in irrelevant_phrases) and word_count <= 3:
        return "irrelevant"

    # 7. Default: provide_info (user providing details or asking general questions)
    return "provide_info"


def has_sufficient_constraints(slots: Dict[str, Any], stage: str) -> bool:
    """Check if collected constraints are sufficient for the given stage."""
    meaningful_keys = [
        "space", "budget_usd", "budget_text", "style", "pets", "kids",
        "product_type", "color", "material"
    ]
    count = sum(1 for k in meaningful_keys if slots.get(k))

    if stage == "discover":
        return count >= 1
    elif stage in ("propose", "compare"):
        return count >= 2
    elif stage == "close":
        return count >= 2
    return False


def next_stage(current: str, slots: Dict[str, Any], user_text: str) -> str:
    intent = detect_intent(user_text, current)  # pass stage for context-aware detection

    # Always prioritize handoff request
    if _has_handoff(user_text):
        return "handoff"

    # Handle disengagement - DO NOT route to handoff, stay in current stage
    # LLM will handle soft close via prompt instructions
    if intent == "disengage":
        return current

    # Handle off-topic - redirect but stay in current stage
    if intent == "off_topic":
        # Stay in current stage but LLM will handle redirect via prompt
        return current

    if current == "discover":
        # Advance when user provides info/asks questions AND we have at least 1 constraint
        if intent in ("provide_info", "ask_info") and has_sufficient_constraints(slots, "discover"):
            return "propose"

    if current == "propose":
        # User wants to compare options
        if _has_compare(user_text):
            return "compare"
        # User ready to buy (explicit confirm OR providing info with enough constraints)
        if (
            intent == "confirm"
            or re.search(r"\b(dat hang|chot don|mua ngay|thanh toan|len don)\b", _match_text(user_text))
            or (intent == "provide_info" and has_sufficient_constraints(slots, "close"))
        ):
            return "close"

    if current == "compare":
        # From comparison, explicit confirm moves to close
        if intent == "confirm":
            return "close"

    if current == "close":
        # Explicit confirm from close stage moves to handoff
        if intent == "confirm":
            return "handoff"

    # Stay in current stage for hesitation, irrelevant, or insufficient info
    return current


def build_sales_prefix(stage: str, slots: Dict[str, Any]) -> str:
    parts = []
    changes = []

    # Track preference changes
    for key in ["style", "color", "material", "budget_usd", "space"]:
        prev_key = f"{key}_prev"
        if key in slots and prev_key in slots:
            old = slots[prev_key]
            new = slots[key]
            if old != new:
                changes.append(f"{key}: {old} → {new}")

    if slots.get("space") == "small":
        parts.append("Customer has a small space.")
    if slots.get("pets"):
        parts.append("Customer has pets.")
    if slots.get("kids"):
        parts.append("Customer has kids.")
    if "budget_usd" in slots:
        parts.append(f"Customer budget is about ${slots['budget_usd']}.")
    if "budget_text" in slots:
        parts.append(f"Customer budget is about {slots['budget_text']}.")
    if "style" in slots:
        parts.append(f"Customer prefers {slots['style']} style.")
    if "color" in slots:
        parts.append(f"Customer prefers {slots['color']} color.")
    if "material" in slots:
        parts.append(f"Customer prefers {slots['material']} material.")
    if "product_type" in slots:
        parts.append(f"Customer is looking for {slots['product_type']}.")

    context = " ".join(parts) if parts else "No specific preferences captured yet."

    # Add change information if any
    change_note = ""
    if changes:
        change_note = "Recent changes: " + "; ".join(changes) + ".\n"

    stage_instr = {
        "discover": "Next best action: ask 1-2 key discovery questions before recommending.",
        "propose": "Next best action: suggest 2-3 KB-grounded options if evidence exists; otherwise ask for one missing detail.",
        "compare": "Next best action: compare only products present in verified KB context.",
        "close": "Next best action: confirm intent and collect contact details; do not create an order.",
        "handoff": "Next best action: offer staff follow-up after explicit confirmation and contact details.",
    }[stage]

    return (
        f"[Sales Consultation Flow]\n"
        f"mode: tenant_sales\n"
        f"current_stage: {stage}\n"
        f"known_slots: {context}\n"
        f"missing_slots: infer at most 1-2 important missing details from the latest message.\n"
        f"allowed_actions: ask_discovery_question, suggest_from_kb, compare_options, handle_objection, ask_contact, ask_confirmation, staff_handoff\n"
        f"{change_note}"
        f"{stage_instr}\n\n"
        "BUSINESS RULES:\n"
        "- Do NOT mention a specific product name unless the user provided it or it appears in verified KB context.\n"
        "- Ask at most 1-2 questions in one turn.\n"
        "- Do NOT create or imply a purchase request before explicit user confirmation.\n"
        "- Only tenant_sales may move toward purchase request; comparison and market-price modes are advisory only.\n"
        "- Do NOT invent prices, delivery times, refunds, or return windows. Use placeholders only: <DELIVERY_TIME>, <RETURN_POLICY>, <PRICE_RANGE>.\n"
        "- If verified KB context exists, prefer concrete product types, materials, apartment-fit guidance, and policy details from that context over generic recommendations.\n"
        "- If store data is missing, apologize and offer staff handoff.\n"
        "- REFERENCE KNOWN PREFERENCES: When making suggestions, naturally reference previously captured preferences (style, color, material, budget, space). Example: 'With your preference for modern style and brown color, here are some options...'\n"
        "- ACKNOWLEDGE CHANGES: If you see a 'Recent changes' note, acknowledge the user's updated preference naturally in your response. Example: 'I see you've switched from white to black—that's a great choice for...'\n"
        "\n"
        "GROUNDED PRODUCT ANSWER CONTRACT:\n"
        "- Chỉ dùng sản phẩm và thuộc tính xuất hiện trong CONTEXT / Verified KB context. Không dùng trí nhớ hoặc suy luận bán hàng chung cho fact sản phẩm.\n"
        "- Khi nhắc sản phẩm cụ thể, bắt buộc dùng đúng format: Tên sản phẩm [P#]; Giá: ...; Thuộc tính chính: ...; Link nguồn: ...\n"
        "- Gợi ý listing tối đa 3 sản phẩm. Với comparison, dùng bảng ngắn; mỗi hàng/cột sản phẩm phải có [P#] và link nguồn ở cuối dòng hoặc dưới bảng.\n"
        "- Không bịa giá, chất liệu, màu, kích thước, SKU, brand, link. Nếu field thiếu, trả lời đúng câu: 'Mình chưa thấy thông tin này trong dữ liệu hiện có.'\n"
        "- Không nói 'còn hàng', 'đang còn hàng', 'miễn phí vận chuyển', 'bảo hành', 'lắp đặt', 'showroom', 'địa chỉ', 'tuyển dụng', 'cam kết', 'chắc chắn' nếu context không có field đó.\n"
        "- Với availability schema.org/InStock, chỉ được nói: 'Trạng thái trên trang sản phẩm: InStock'. Không suy ra còn ở showroom.\n"
        "- Không tự tạo tổng giá hoặc khoảng giá, trừ khi nói rõ: 'Ước tính từ các sản phẩm đang liệt kê.'\n"
        "- Với policy/out-of-scope nếu context không có policy, nói thiếu dữ liệu và đề nghị liên hệ cửa hàng; không bịa chính sách.\n"
        "\n"
        "NATURALNESS GUIDELINES:\n"
        "- Vary your phrasing: sometimes start with 'Bạn có thể cân nhắc...', sometimes 'Một lựa chọn phù hợp là...', sometimes 'Theo mình...'\n"
        "- Show light empathy when appropriate: 'Mình hiểu với không gian nhỏ...', 'Với ngân sách này, mình nghĩ...'\n"
        "- Avoid always listing bullet points. Use flowing sentences, but keep it to 2-4 sentences total.\n"
        "- Mix sentence lengths. Don't follow the same pattern every time.\n"
        "- Sound like a helpful friend, not a checklist.\n"
        "\n"
        "OFF-TOPIC & DISENGAGEMENT:\n"
        "- If user asks about unrelated topics (politics, sports, weather, personal questions), politely redirect: 'Mình là trợ lý mua sắm nội thất, mình có thể giúp gì cho bạn về ghế, bàn, tủ hay các sản phẩm khác?'\n"
        "- If user indicates disengagement ('thôi', 'để sau', 'ok rồi'), respond with a soft close and end the conversation naturally (e.g., 'Tạm biệt! Nếu sau này cần tư vấn, bạn cứ quay lại nhé.'). Do NOT transition to handoff or ask further questions.\n"
    )
