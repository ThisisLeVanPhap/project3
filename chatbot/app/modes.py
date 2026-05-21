import re
from enum import Enum
from typing import Optional


class ChatMode(str, Enum):
    TENANT_SALES = "tenant_sales"
    GENERAL_COMPARE = "general_compare"
    MARKET_PRICE = "market_price"


MODE_ALIASES = {
    "sales": ChatMode.TENANT_SALES.value,
    "tenant": ChatMode.TENANT_SALES.value,
    "shop": ChatMode.TENANT_SALES.value,
    "general": ChatMode.GENERAL_COMPARE.value,
    "general_consumer": ChatMode.GENERAL_COMPARE.value,
    "compare": ChatMode.GENERAL_COMPARE.value,
    "comparison": ChatMode.GENERAL_COMPARE.value,
    "market": ChatMode.MARKET_PRICE.value,
    "price": ChatMode.MARKET_PRICE.value,
    "market_reference": ChatMode.MARKET_PRICE.value,
}

COMPARE_HINTS = re.compile(
    r"\b(compare|comparison|vs|versus|difference|differences|which one|which should|"
    r"so sanh|so sánh|khac nhau|khác nhau|nen chon|nên chọn|lua chon|lựa chọn)\b",
    re.I,
)

MARKET_PRICE_HINTS = re.compile(
    r"\b(market price|price range|reasonable price|price reference|outlier|overpriced|underpriced|"
    r"gia thi truong|giá thị trường|khoang gia|khoảng giá|tham chieu gia|tham chiếu giá|"
    r"gia hop ly|giá hợp lý|cao bat thuong|cao bất thường|thap bat thuong|thấp bất thường)\b",
    re.I,
)

MODE_SYSTEM_INSTRUCTIONS = {
    ChatMode.TENANT_SALES.value: (
        "MODE: tenant_sales.\n"
        "- Answer for one tenant/store using only that tenant KB when product facts are needed.\n"
        "- You may consult on needs, budget, dimensions, materials, style, room fit, and buying readiness.\n"
        "- If the customer is ready to buy, guide them toward the next sales step without claiming payment is processed in chat.\n"
    ),
    ChatMode.GENERAL_COMPARE.value: (
        "MODE: general_compare.\n"
        "- Answer as a neutral comparison advisor, not as a sales closer.\n"
        "- Use a stable comparison format with these sections: Nguồn dữ liệu, Các lựa chọn so sánh, Tiêu chí so sánh, Kết luận trung lập.\n"
        "- Compare up to the supported options, aiming for at least 3 when the context supports it.\n"
        "- Use at least 3 comparison criteria such as price, material, size, style, and intended use.\n"
        "- For any missing fact, explicitly write 'chưa có dữ liệu' instead of guessing.\n"
        "- Keep the comparison neutral and do not recommend placing an order.\n"
        "- Never create leads, purchase requests, or ask the user to confirm an order.\n"
    ),
    ChatMode.MARKET_PRICE.value: (
        "MODE: market_price.\n"
        "- Answer only as a market price/reference analyst.\n"
        "- Use a stable format with these sections: Nguồn dữ liệu dùng, Khoảng giá tham khảo, Nhận xét mức giá, Cảnh báo dữ liệu.\n"
        "- State the provider/source used and only state a reference range when supported by retrieved context or explicit price references.\n"
        "- If the user supplied a price, judge it as low, within range, high, or insufficient data based only on supported references.\n"
        "- If data is mock/demo or insufficient, say that clearly.\n"
        "- Do not recommend buying a specific product or push a sales next step.\n"
        "- Never create leads or purchase requests.\n"
    ),
}


def auto_detect_mode(message: str) -> str:
    text = message or ""
    if MARKET_PRICE_HINTS.search(text):
        return ChatMode.MARKET_PRICE.value
    if COMPARE_HINTS.search(text):
        return ChatMode.GENERAL_COMPARE.value
    return ChatMode.TENANT_SALES.value


def normalize_chat_mode(mode: Optional[str], message: str = "") -> str:
    raw = (mode or "").strip().lower()
    if not raw:
        return auto_detect_mode(message)

    raw = MODE_ALIASES.get(raw, raw)
    allowed = {item.value for item in ChatMode}
    if raw not in allowed:
        raise ValueError(f"Unsupported chat mode: {mode}")
    return raw


def mode_system_instruction(mode: str) -> str:
    return MODE_SYSTEM_INSTRUCTIONS.get(mode, MODE_SYSTEM_INSTRUCTIONS[ChatMode.TENANT_SALES.value])
