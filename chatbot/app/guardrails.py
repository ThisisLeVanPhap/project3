import re
from typing import Optional, Dict, Any

from .prompt import is_vietnamese_text

# Categories for price lookup - kept in sync with price_reference.json
PRICE_CATEGORIES = [
    "sofa", "table", "dining table", "chair", "desk", "bed", "cabinet", "wardrobe"
]

RX_PRICE_QUERY = re.compile(
    r"\b(price|cost|how much|reasonable|typical|range|average|giá|bao nhiêu|khoảng|phải chăng|đắt|rẻ)\b",
    re.I,
)

# Price amount extraction: matches "$1,200", "$1200", "1200 USD", "1.2M", "2 tỷ", "1.5 triệu"
RX_PRICE_AMOUNT = re.compile(
    r"(?:\$|usd|đô la)?\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:\.?[0-9]*)?|"
    r"[0-9]+(?:\.[0-9]+)?)\s*(triệu|trieu|nghìn|nghin|k|usd|vnd|vnđ|đ)?",
    re.I,
)

RX_INVENTORY = re.compile(
    r"\b(in stock|available|availability|left|remain|c[oò]n h[aà]ng|sẵn hàng|c[oò]n kh[oô]ng)\b",
    re.I,
)
RX_BARGAIN = re.compile(
    r"\b(discount|cheaper|lower price|deal|bargain|gi[aả]m gi[aá]|khuy[eế]n m[aạ]i|"
    r"b[oớ]t gi[aá]|gi[aá] t[oố]t|r[eẻ] h[oơ]n)\b",
    re.I,
)
RX_HUMAN = re.compile(
    r"\b(human|agent|staff|representative|call|hotline|nh[aâ]n vi[eê]n|tư v[aấ]n vi[eê]n|"
    r"người thật|gọi|li[eê]n hệ)\b",
    re.I,
)
RX_SIMILAR = re.compile(
    r"\b(similar|alternative|close to|like this|tương tự|na ná|gần giống|giống mẫu này|"
    r"phương án khác)\b",
    re.I,
)


def _localized_reply(user_msg: str, english: str, vietnamese: str) -> str:
    return vietnamese if is_vietnamese_text(user_msg) else english


def _detect_price_category(text: str) -> Optional[str]:
    """Detect furniture category from message."""
    lowered = text.lower()
    for cat in PRICE_CATEGORIES:
        if cat in lowered:
            return cat
    return None


def _extract_price_amount(text: str) -> Optional[float]:
    """Extract first numeric price from message, handling Vietnamese units.

    Rules:
    - "triệu" = multiply by 1,000,000
    - "nghìn"/"k" = multiply by 1,000
    - Assume VND if unit is "triệu", "nghìn", "k", "đ"
    - Convert VND → USD (1 USD = 25,000 VND)
    """
    matches = RX_PRICE_AMOUNT.findall(text)
    if not matches:
        return None

    for m in matches:
        # m is tuple: (number, unit)
        raw_num = m[0].strip()
        unit = (m[1] or "").strip().lower() if len(m) > 1 else ""

        if not raw_num:
            continue

        # Remove commas from number (e.g., "1,200" → "1200")
        raw_num = raw_num.replace(",", "")

        try:
            value = float(raw_num)
        except ValueError:
            continue

        # Apply unit multipliers
        if unit:
            if "triệu" in unit or "trieu" in unit:
                value *= 1_000_000
            elif "nghìn" in unit or "nghin" in unit or unit == "k":
                value *= 1_000

            # Convert VND to USD if unit indicates VND currency
            if any(vnd_marker in unit for vnd_marker in ["triệu", "trieu", "nghìn", "nghin", "k", "đ", "vnd", "vnđ"]):
                value = value / 25000  # 1 USD ≈ 25,000 VND

        return value

    return None


def _format_price_reply(category: str, info: Dict, user_msg: str, user_price: Optional[float] = None) -> str:
    """Format price range reply with classification."""
    min_p = info.get("min", 0)
    max_p = info.get("max", 0)
    avg_p = info.get("avg", (min_p + max_p) / 2)
    curr = info.get("currency", "USD")
    unit = info.get("unit", "piece")

    # Base reply
    range_text = f"{curr} {min_p}-{max_p}"
    avg_text = f"{curr} {avg_p}"

    if user_price is not None:
        # Classify relative to average
        ratio = user_price / avg_p if avg_p > 0 else 0
        if ratio < 0.7:
            classification = "low" if is_vietnamese_text(user_msg) else "below average"
            comparison = "lower than" if is_vietnamese_text(user_msg) else "below the typical"
        elif ratio > 1.3:
            classification = "high" if is_vietnamese_text(user_msg) else "above average"
            comparison = "higher than" if is_vietnamese_text(user_msg) else "above the typical"
        else:
            classification = "normal" if is_vietnamese_text(user_msg) else "within typical range"
            comparison = "within" if is_vietnamese_text(user_msg) else "within the typical"

        if is_vietnamese_text(user_msg):
            en = (
                f"The typical price range for {category}s is {range_text} per {unit}, "
                f"with an average of {avg_text}. "
                f"A price of {curr} {user_price:,.0f} is {comparison} market average, "
                f"which is {classification} for this category."
            )
            vi = (
                f"Phạm vi giá điển hình cho {category} là {range_text} mỗi {unit}, "
                f"trung bình {avg_text}. "
                f"Giá {curr} {user_price:,.0f} là {comparison} mức trung bình thị trường, "
                f"thuộc nhóm {classification} cho danh mục này."
            )
        else:
            en = (
                f"The typical price range for {category}s is {range_text} per {unit}, "
                f"with an average of {avg_text}. "
                f"A price of {curr} {user_price:,.0f} is {comparison} average, "
                f"which is {classification} for this category."
            )
            vi = en  # Should not happen, but fallback
    else:
        # No user price provided - just show range
        if is_vietnamese_text(user_msg):
            en = (
                f"The typical price range for {category}s is {range_text} per {unit}. "
                f"The average is around {avg_text}. "
                f"This falls in the normal range for this category."
            )
            vi = (
                f"Phạm vi giá điển hình cho {category} là {range_text} mỗi {unit}. "
                f"Trung bình khoảng {avg_text}. "
                f"Đây là mức giá bình thường cho danh mục này."
            )
        else:
            en = (
                f"The typical price range for {category}s is {range_text} per {unit}. "
                f"The average is around {avg_text}. "
                f"This falls in the normal range for this category."
            )
            vi = en

    return _localized_reply(user_msg, en, vi)


def rule_reply(user_msg: str) -> Optional[Dict[str, Any]]:
    m = user_msg.strip()

    if RX_HUMAN.search(m):
        return {
            "type": "handoff",
            "reply": _localized_reply(
                user_msg,
                "I can connect you with a human staff member for direct assistance. "
                "Please let me know a convenient time or share your contact details.",
                "Mình có thể kết nối bạn với nhân viên tư vấn để hỗ trợ trực tiếp. "
                "Bạn cho mình biết thời gian thuận tiện hoặc để lại thông tin liên hệ nhé.",
            ),
        }

    if RX_INVENTORY.search(m):
        return {
            "type": "inventory_mock",
            "reply": _localized_reply(
                user_msg,
                "I don't have real-time inventory data at the moment. "
                "To be accurate, I can ask a staff member to check availability for you. "
                "Could you share the product name or code?",
                "Hiện tại mình chưa có dữ liệu tồn kho theo thời gian thực. "
                "Để kiểm tra chính xác, mình có thể nhờ nhân viên kiểm tra giúp bạn. "
                "Bạn gửi tên hoặc mã sản phẩm nhé?",
            ),
        }

    if RX_BARGAIN.search(m):
        return {
            "type": "bargain_policy",
            "reply": _localized_reply(
                user_msg,
                "I'm unable to adjust prices directly in chat. "
                "If you have a target budget, I can suggest similar options that fit it better.",
                "Mình không thể điều chỉnh giá trực tiếp trong chat. "
                "Nếu bạn có mức ngân sách mong muốn, mình có thể gợi ý những mẫu tương tự phù hợp hơn.",
            ),
        }

    return None


def want_similar(user_msg: str) -> bool:
    return RX_SIMILAR.search(user_msg or "") is not None
