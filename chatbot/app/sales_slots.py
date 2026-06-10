import re
import unicodedata
from typing import Any, Dict, List

try:
    from .sales_flow import extract_slots as extract_sales_flow_slots
except ImportError:  # pragma: no cover - direct script imports
    from app.sales_flow import extract_slots as extract_sales_flow_slots


PHONE_RE = re.compile(r"(?<!\d)(0[35789](?:[\s.\-]?\d){8}|\+?84(?:[\s.\-]?\d){9})(?!\d)")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
QUANTITY_WITH_UNIT_RE = re.compile(r"\b(\d{1,3})\s*(?:cái|cai|bộ|bo|chiếc|chiec|sp|sản phẩm|san pham)\b", re.I)
QUANTITY_WITH_VERB_RE = re.compile(r"\b(?:lấy|lay|mua|đặt|dat|order)\s+(\d{1,3})(?!\s*(?:k|000|\.|,|mẫu|mau|p\d))\b", re.I)
PURCHASE_RE = re.compile(r"\b(mua|đặt|dat|lấy|lay|chốt|chot|tư vấn mua|tu van mua|muốn lấy|muon lay|order|buy|purchase)\b", re.I)
HANDOFF_RE = re.compile(r"\b(gặp nhân viên|gap nhan vien|tư vấn viên|tu van vien|gọi tôi|goi toi|liên hệ tôi|lien he toi|nhân viên|nhan vien|human|agent|staff)\b", re.I)
CANCEL_RE = re.compile(r"\b(thôi|thoi|không mua nữa|khong mua nua|hủy|huy|để sau|de sau|cancel|nevermind)\b", re.I)
CONFIRM_RE = re.compile(r"\b(xác nhận|xac nhan|đúng rồi|dung roi|gửi đi|gui di|gửi cho cửa hàng|gui cho cua hang|ok gửi|ok gui|đồng ý|dong y|chốt gửi|chot gui|yes|oke|ok)\b", re.I)
CONFIRM_REJECT_RE = re.compile(r"\b(hủy|huy|thôi|thoi|không gửi|khong gui|để sau|de sau|sửa lại|sua lai|chưa|chua)\b", re.I)
SHIP_RE = re.compile(r"\b(ship|giao hàng|giao hang|vận chuyển|van chuyen|tồn kho|ton kho|còn hàng|con hang|available|stock)\b", re.I)
PRODUCT_INQUIRY_RE = re.compile(r"\b(giá|gia|bao nhiêu|bao nhieu|mẫu|mau|sản phẩm|san pham|sofa|bàn|ban|ghế|ghe|tủ|tu|giường|giuong|kệ|ke|so sánh|so sanh|ship|giao hàng|giao hang)\b", re.I)
OUT_OF_SCOPE_RE = re.compile(r"\b(thời tiết|thoi tiet|bóng đá|bong da|chứng khoán|chung khoan|nấu ăn|nau an|du lịch|du lich|điện thoại|dien thoai|phone|smartphone|laptop|máy tính|may tinh|politics|weather|football)\b", re.I)
BUDGET_RE = re.compile(r"\b(?:ngân sách|ngan sach|tầm giá|tam gia|khoảng|khoang|dưới|duoi|budget)\s*([0-9]+(?:[.,][0-9]+)?)\s*(triệu|trieu|tr|k|nghìn|nghin|vnd|vnđ|usd|\$)?\b", re.I)
PRODUCT_REFERENCE_RE = re.compile(
    r"\b(p\s*\d+|mau\s*(?:thu\s*)?\d+|mau\s*thu\s*(?:mot|hai|ba|bon|tu|nam)|san pham\s*(?:thu\s*)?\d+|cai\s*(?:dau|cuoi))\b",
    re.I,
)
PRODUCT_REFERENCE_QUESTION_RE = re.compile(
    r"\b(co\s+khong|gia|bao nhieu|chat lieu|kich thuoc|mau sac|mau khac|so sanh|khac gi|con hang|dat khong|dat hon|xem ky|chi tiet|thong tin)\b",
    re.I,
)

CITY_PATTERNS = {
    "ha_noi": re.compile(r"\b(hà nội|ha noi|hn)\b", re.I),
    "hcm": re.compile(r"\b(hồ chí minh|ho chi minh|hcm|tp hcm|sài gòn|sai gon)\b", re.I),
    "da_nang": re.compile(r"\b(đà nẵng|da nang)\b", re.I),
    "province": re.compile(r"\b(tỉnh|tinh)\s+([a-zA-ZÀ-ỹ\s]{2,30})", re.I),
}


def repair_mojibake(text: str) -> str:
    value = text or ""
    if not any(marker in value for marker in ("Ã", "Â", "Ä", "Æ", "Å", "áº", "á»")):
        return value
    for _ in range(2):
        changed = False
        for encoding in ("latin1", "cp1252"):
            try:
                candidate = value.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if candidate != value:
                value = candidate
                changed = True
                break
        if not changed:
            break
    return value


def fold_text(text: Any) -> str:
    value = repair_mojibake(str(text or "")).replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()


def clean_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("84") and len(digits) == 11:
        return "0" + digits[2:]
    return digits


def extract_phone(text: str) -> str:
    match = PHONE_RE.search(repair_mojibake(text or ""))
    return clean_phone(match.group(0)) if match else ""


def extract_quantity(text: str) -> int | None:
    without_phone = PHONE_RE.sub(" ", repair_mojibake(text or ""))
    folded = PHONE_RE.sub(" ", fold_text(without_phone))
    for candidate in (without_phone, folded):
        match = QUANTITY_WITH_UNIT_RE.search(candidate)
        if match:
            return int(match.group(1))
        match = QUANTITY_WITH_VERB_RE.search(candidate)
        if match:
            return int(match.group(1))
    return None


def extract_location(text: str) -> str:
    raw = repair_mojibake(text or "")
    folded = fold_text(raw)
    if CITY_PATTERNS["ha_noi"].search(raw) or re.search(r"\b(ha noi|hn)\b", folded):
        return "Hà Nội"
    if CITY_PATTERNS["hcm"].search(raw) or re.search(r"\b(ho chi minh|hcm|tp hcm|sai gon)\b", folded):
        return "HCM"
    if CITY_PATTERNS["da_nang"].search(raw) or re.search(r"\bda nang\b", folded):
        return "Đà Nẵng"
    province = CITY_PATTERNS["province"].search(raw)
    if province:
        return province.group(0).strip()
    return ""


def detect_intents(text: str) -> List[str]:
    raw = repair_mojibake(text or "")
    folded = fold_text(raw)
    intents: List[str] = []
    if OUT_OF_SCOPE_RE.search(raw) or OUT_OF_SCOPE_RE.search(folded):
        return ["out_of_scope"]
    if CANCEL_RE.search(raw) or re.search(r"\b(thoi|khong mua nua|huy|de sau|cancel)\b", folded):
        intents.append("cancel")
    if HANDOFF_RE.search(raw) or re.search(r"\b(gap nhan vien|tu van vien|goi toi|lien he toi|nhan vien|human|agent|staff)\b", folded):
        intents.append("handoff_request")
    if PURCHASE_RE.search(raw) or re.search(r"\b(mua|lay|chot|order|buy|purchase|muon lay|dat hang|toi dat|dat mua|dat cai|dat mau)\b", folded):
        intents.append("purchase_intent")
    if extract_phone(raw) or EMAIL_RE.search(raw):
        intents.append("contact_provided")
    if PRODUCT_INQUIRY_RE.search(raw) or PRODUCT_INQUIRY_RE.search(folded):
        intents.append("product_inquiry")
    if not intents:
        intents.append("unknown")
    return intents


def detect_confirmation_intent(message: str) -> str | None:
    raw = repair_mojibake(message or "")
    folded = fold_text(raw)
    if CONFIRM_REJECT_RE.search(raw) or CONFIRM_REJECT_RE.search(folded):
        return "reject"
    if CONFIRM_RE.search(raw) or CONFIRM_RE.search(folded):
        return "confirm"
    return None


def has_product_reference(message: str) -> bool:
    return PRODUCT_REFERENCE_RE.search(fold_text(message or "")) is not None


def is_product_reference_question(message: str) -> bool:
    folded = fold_text(message or "")
    if PRODUCT_REFERENCE_RE.search(folded) is None:
        return False
    return "?" in (message or "") or PRODUCT_REFERENCE_QUESTION_RE.search(folded) is not None


def classify_primary_intent(intents: List[str]) -> str:
    for candidate in ("cancel", "handoff_request", "contact_provided", "purchase_intent", "out_of_scope", "product_inquiry"):
        if candidate in intents:
            return candidate
    return "unknown"


def extract_sales_slots(message: str) -> Dict[str, Any]:
    raw = repair_mojibake(message or "")
    folded = fold_text(raw)
    intents = detect_intents(raw)
    slots: Dict[str, Any] = {
        "intents": intents,
        "intent": classify_primary_intent(intents),
        "confirmation_intent": detect_confirmation_intent(raw),
        "has_ship_or_stock_question": bool(SHIP_RE.search(raw) or SHIP_RE.search(folded)),
        "has_product_reference": has_product_reference(raw),
        "is_product_reference_question": is_product_reference_question(raw),
    }

    phone = extract_phone(raw)
    if phone:
        slots["phone"] = phone
    email = EMAIL_RE.search(raw)
    if email:
        slots["email"] = email.group(0)
    quantity = extract_quantity(raw)
    if quantity is not None:
        slots["quantity"] = quantity
    location = extract_location(raw)
    if location:
        slots["location"] = location
        slots["address"] = raw.strip()

    budget = BUDGET_RE.search(raw) or BUDGET_RE.search(folded)
    if budget:
        slots["budget"] = " ".join(part for part in budget.groups() if part).strip()

    try:
        base_slots = extract_sales_flow_slots(raw)
    except Exception:
        base_slots = {}
    for key in ("budget_text", "budget_usd", "style", "color", "material", "space", "product_type"):
        if key in base_slots and key not in slots:
            slots[key] = base_slots[key]
    if "budget_text" in slots and "budget" not in slots:
        slots["budget"] = slots["budget_text"]
    if "budget_usd" in slots and "budget" not in slots:
        slots["budget"] = slots["budget_usd"]

    missing = []
    if "purchase_intent" in intents and not (phone or email) and "handoff_request" not in intents:
        missing.append("contact")
    slots["missing_fields"] = missing
    return slots


def score_lead(slots: Dict[str, Any], has_selected_product: bool = False) -> tuple[float, str]:
    intents = slots.get("intents") or []
    score = 0.0
    if slots.get("phone") or slots.get("email"):
        score += 3
    if "purchase_intent" in intents:
        score += 2
    if has_selected_product:
        score += 2
    if slots.get("quantity"):
        score += 1
    if slots.get("address") or slots.get("location"):
        score += 1
    if slots.get("has_ship_or_stock_question"):
        score += 1
    if slots.get("budget") or slots.get("budget_text") or slots.get("budget_usd"):
        score += 1
    if "cancel" in intents:
        score -= 3
    score = max(0.0, min(10.0, score))
    if score <= 2:
        status = "cold"
    elif score <= 6:
        status = "warm"
    else:
        status = "hot"
    return score, status
