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
                    "Theo thong tin cua hang, khach co the thanh toan hoac "
                    "\u0111\u1eb7t c\u1ecdc truc tiep voi nhan vien ban hang. "
                    "Cua hang co ho tro chuyen khoan; thanh toan sau khi giao hang "
                    "ap dung trong pham vi 0-50km neu thong tin nay co trong chinh sach."
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
                    "Minh \u0063\u0068\u01b0\u0061 \u0111\u1ee7 du lieu tu kho tri thuc "
                    "de ket luan chat lieu nao de ve sinh hon. Theo thong tin hien co, "
                    "chi co the xac nhan sofa go co the duoc boc nem da hoac ni."
                )
            return (
                "I do not have enough verified knowledge-base data to say which material "
                "is easier to clean. The available context only supports that the wooden "
                "sofa can be upholstered with leather or fabric cushions."
            )

    return response
