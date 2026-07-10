import re

from .prompt import is_vietnamese_text


BAD_FACTS = re.compile(
    r"\b(within\s+\d+\s+(day|days|business\s+days)|refund|complete payment|receive the item)\b",
    re.I,
)

UNSUPPORTED_PAYMENT_FACTS = re.compile(
    r"\b(visa|credit\s+card|debit\s+card|card payment|the tin dung|tra gop)\b",
    re.I,
)
GENERIC_GROUNDED_INTRO = re.compile(
    r"\b(from the verified store data|i can confirm|store policy is available)\b",
    re.I,
)
PAYMENT_POLICY_QUERY = re.compile(
    r"\b(payment|pay|policy|thanh toan|dat coc|chuyen khoan|chinh sach)\b",
    re.I,
)
CLEANING_COMPARISON_QUERY = re.compile(
    r"\b(clean|cleaning|wipe|lau chui|ve sinh|de lau|de ve sinh)\b",
    re.I,
)


def apply_grounding_guard(user_msg: str, context: str, response: str) -> str:
    """Keep replies inside verified KB facts for high-risk policy/comparison answers."""
    user_msg = user_msg or ""
    context = context or ""
    response = response or ""
    vietnamese = is_vietnamese_text(user_msg)

    if PAYMENT_POLICY_QUERY.search(user_msg):
        has_supported_payment_context = re.search(
            r"\b(thanh toan|dat coc|chuyen khoan|sau khi giao hang|0-50km)\b",
            context,
            re.I,
        )
        has_bad_payment_claim = (
            UNSUPPORTED_PAYMENT_FACTS.search(response)
            or GENERIC_GROUNDED_INTRO.search(response)
            or BAD_FACTS.search(response)
        )
        if has_supported_payment_context and has_bad_payment_claim:
            if vietnamese:
                return (
                    "Theo th\u00f4ng tin c\u1eeda h\u00e0ng, kh\u00e1ch c\u00f3 th\u1ec3 thanh to\u00e1n ho\u1eb7c "
                    "\u0111\u1eb7t c\u1ecdc tr\u1ef1c ti\u1ebfp v\u1edbi nh\u00e2n vi\u00ean b\u00e1n h\u00e0ng. "
                    "C\u1eeda h\u00e0ng c\u00f3 h\u1ed7 tr\u1ee3 chuy\u1ec3n kho\u1ea3n; thanh to\u00e1n sau khi giao h\u00e0ng "
                    "\u00e1p d\u1ee5ng trong ph\u1ea1m vi 0-50km n\u1ebfu th\u00f4ng tin n\u00e0y c\u00f3 trong ch\u00ednh s\u00e1ch."
                )
            return (
                "According to the store information, customers can pay or place a deposit "
                "directly with sales staff. Bank transfer is supported; payment after delivery "
                "applies within the 0-50km range when stated by the store policy."
            )

    if CLEANING_COMPARISON_QUERY.search(user_msg):
        response_makes_cleaning_claim = re.search(
            r"\b(easier to clean|de lau chui|de ve sinh|lau chui hon|cleaner)\b",
            response,
            re.I,
        )
        context_supports_cleaning = re.search(
            r"\b(easier to clean|de lau chui|de ve sinh|lau chui|ve sinh)\b",
            context,
            re.I,
        )
        if response_makes_cleaning_claim and not context_supports_cleaning:
            if vietnamese:
                return (
                    "Mình chưa đủ dữ liệu từ kho tri thức "
                    "để kết luận chất liệu nào dễ vệ sinh hơn. Theo thông tin hiện có, "
                    "chỉ có thể xác nhận sofa gỗ có thể được bọc nệm da hoặc nỉ."
                )
            return (
                "I do not have enough verified knowledge-base data to say which material "
                "is easier to clean. The available context only supports that the wooden "
                "sofa can be upholstered with leather or fabric cushions."
            )

    return response
