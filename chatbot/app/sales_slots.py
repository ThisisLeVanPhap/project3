import re
import unicodedata
from typing import Any, Dict, List

try:
    from .product_filters import parse_price_constraint, parse_product_categories
    from .sales_flow import extract_slots as extract_sales_flow_slots
    from .sales_nlu import classify_sales_nlu
except ImportError:  # pragma: no cover - direct script imports
    from app.product_filters import parse_price_constraint, parse_product_categories
    from app.sales_flow import extract_slots as extract_sales_flow_slots
    from app.sales_nlu import classify_sales_nlu


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
    r"\b(p\s*\d+|mau\s*(?:thu\s*)?\d+|mau\s*thu\s*(?:mot|hai|ba|bon|tu|nam)|san pham\s*(?:thu\s*)?\d+|cai\s*(?:dau|cuoi)|[a-z]{2,6}-\d{2,8})\b",
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
    is_topic_change = re.search(r"\b(thoi\s+)?(doi|chuyen)\s+sang\b", folded) is not None
    is_topic_change = is_topic_change or bool(
        re.search(r"\bthoi\b.*\b(sofa|ban|ghe|tu|giuong|ke|den|tham|tranh|guong|rem)\b", folded)
        and re.search(r"\b(hon|thich|hoi|xem|tham khao|mau)\b", folded)
    )
    is_soft_thoi = _is_soft_thoi_particle(folded)
    if not is_topic_change and not is_soft_thoi and (
        CANCEL_RE.search(raw) or re.search(r"\b(thoi|khong mua nua|huy|de sau|cancel)\b", folded)
    ):
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


def _is_soft_thoi_particle(folded: str) -> bool:
    """Return True when "thoi" means "just/only", not cancel/reject."""
    value = re.sub(r"\s+", " ", folded or "").strip()
    if not re.search(r"\bthoi\b", value):
        return False
    explicit_reject = re.search(
        r"\b(?:thoi\s*)?(?:khong\s+(?:mua|lay|can|dat|gui)|huy|de\s+sau|bo\s+di|khoi|cancel|nevermind)\b",
        value,
    )
    if explicit_reject:
        return False
    if re.search(r"\b\d+(?:[.,]\d+)?\s*(?:m|met)?\s*[x*]\s*\d+(?:[.,]\d+)?\s*m?\s*thoi\b", value):
        return True
    if re.search(
        r"\b\d+(?:[.,]\d+)?\s*(?:m2|m|met|met vuong|trieu|tr|nghin|k|cai|bo|chiec|san pham)\s*thoi\b",
        value,
    ):
        return True
    if re.search(r"\b(?:chi|co|chac|tam|khoang|quanh|do|uoc chung)\b.{0,50}\bthoi\b", value):
        return True
    return False


def detect_confirmation_intent(message: str) -> str | None:
    raw = repair_mojibake(message or "")
    folded = fold_text(raw)
    if not _is_soft_thoi_particle(folded) and (CONFIRM_REJECT_RE.search(raw) or CONFIRM_REJECT_RE.search(folded)):
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


SKU_REF_RE = re.compile(r"\b([A-Za-z]{2,6}[-_][A-Za-z0-9]{2,8})\b")
DIM_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(?:m|mét)?\s*[x*]\s*(\d+(?:[.,]\d+)?)\s*m?\b",
    re.I,
)
AREA_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(m²|m2|sqm|mét\s+vuông|m2|mét vuông)\b",
    re.I,
)


def _extract_dimensions(text: str) -> dict | None:
    """Extract room dimensions: 3m x 5m -> {raw, width_m, length_m}; 15m2 -> {raw, area_m2}."""
    m = DIM_RE.search(text)
    if m:
        try:
            w = float(m.group(1).replace(",", "."))
            l = float(m.group(2).replace(",", "."))
            return {"raw": m.group(0), "width_m": w, "length_m": l}
        except ValueError:
            pass
    m2 = AREA_RE.search(text)
    if m2:
        try:
            a = float(m2.group(1).replace(",", "."))
            return {"raw": m2.group(0), "area_m2": a}
        except ValueError:
            pass
    return None


def extract_sku_reference(text: str) -> str | None:
    """Extract SKU/product code reference (e.g. GHO-239, GHS-42048, ABC-1234)."""
    match = SKU_REF_RE.search(repair_mojibake(text or ""))
    if match:
        raw = match.group(1)
        # Normalize: uppercase the alpha part, keep digits/hyphen as-is
        parts = raw.rsplit("-", 1) if "-" in raw else raw.rsplit("_", 1)
        if len(parts) == 2:
            return f"{parts[0].upper()}-{parts[1]}"
        return raw.upper()
    return None


def classify_primary_intent(intents: List[str]) -> str:
    for candidate in ("cancel", "handoff_request", "contact_provided", "purchase_intent", "out_of_scope", "product_inquiry"):
        if candidate in intents:
            return candidate
    return "unknown"


def extract_sales_slots(message: str) -> Dict[str, Any]:
    raw = repair_mojibake(message or "")
    folded = fold_text(raw)
    intents = detect_intents(raw)
    nlu = classify_sales_nlu(raw)
    slots: Dict[str, Any] = {
        "intents": intents,
        "intent": classify_primary_intent(intents),
        "nlu_intent": nlu.intent,
        "nlu_confidence": nlu.confidence,
        "nlu_source": nlu.source,
        "confirmation_intent": detect_confirmation_intent(raw),
        "has_ship_or_stock_question": bool(SHIP_RE.search(raw) or SHIP_RE.search(folded)),
        "has_product_reference": has_product_reference(raw),
        "is_product_reference_question": is_product_reference_question(raw),
    }
    slots.update({k: v for k, v in nlu.entities.items() if v not in (None, "")})

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
        slots["delivery_area"] = location
        slots["address"] = raw.strip()

    budget_match = BUDGET_RE.search(raw) or BUDGET_RE.search(folded)
    if budget_match:
        # Phase 9: ignore "khoảng 3m x 5m" false positive (dimension, not budget)
        budget_raw = budget_match.group(0)
        _, is_dim = raw.lower(), bool(re.search(r'\b\d+\s*m\s*x\s*\d+\s*m?\b', raw, re.I))
        if not is_dim:
            slots["budget"] = " ".join(part for part in budget_match.groups() if part).strip()
    # Phase 9: match "5 triệu trở xuống", "5tr tro xuong", "<= 5 triệu" etc.
    if not slots.get("budget"):
        tro_xuong = re.search(r'\b(\d+(?:[\.,]\d+)?)\s*(triệu|tr|nghìn)\s*trở\s*xuống\b', raw, re.I)
        if not tro_xuong:
            tro_xuong = re.search(r'\b(\d+(?:[\.,]\d+)?)\s*(triệu|tr|nghìn)\s*tro\s*xuong\b', folded, re.I)
        if tro_xuong:
            amount = tro_xuong.group(1) + " " + tro_xuong.group(2)
            slots["budget"] = amount.strip()
        else:
            lteq = re.search(r'(?:<=|≤|le)\s*(\d+(?:[\.,]\d+)?)\s*(triệu|tr|nghìn)\b', raw, re.I)
            if not lteq:
                lteq = re.search(r'(?:<=|≤|le)\s*(\d+(?:[\.,]\d+)?)\s*(triệu|tr|nghìn)\b', raw, re.I)
            if not lteq:
                lteq = re.search(r'(?:<=|≤|le)\s*(\d+(?:[\.,]\d+)?)\s*(trieu|tr|nghin)\b', raw, re.I)
            if not lteq:
                lteq = re.search(r'(?:<=|≤|le)\s*(\d+(?:[\.,]\d+)?)\s*(trieu|tr|nghin)\b', folded, re.I)
            if lteq:
                amount = lteq.group(1) + " " + lteq.group(2)
                slots["budget"] = amount.strip()
            else:
                tro_xuong2 = re.search(r'(\d+(?:[\.,]\d+)?)\s*(trieu|tr|nghin)\s*tro\s*xuong\b', folded, re.I)
                if tro_xuong2:
                    amount = tro_xuong2.group(1) + " " + tro_xuong2.group(2)
                    slots["budget"] = amount.strip()
    if not slots.get("budget"):
        approx = re.search(r'\b(?:tren\s+duoi|quanh|tam|khoang)\s*(\d+(?:[\.,]\d+)?)\s*(trieu|tr|nghin)\b', folded, re.I)
        if approx:
            slots["budget"] = (approx.group(1) + " " + approx.group(2)).strip()

    # Phase 10F: lower-bound budget ("hơn 10 triệu", "trên 10 triệu", "phải hơn X")
    if not slots.get("budget"):
        lower = re.search(r'(?:hon|hon hon|tren|trên|phai hon|phai hon hon)\s*(\d+(?:[\.,]\d+)?)\s*(trieu|tr|nghin)\b', folded, re.I)
        if not lower:
            lower = re.search(r'(?:tu|từ)\s*(\d+(?:[\.,]\d+)?)\s*(trieu|tr|nghin)\s*tro\s*len\b', folded, re.I)
        if lower:
            amount = lower.group(1) + " " + lower.group(2)
            slots["budget"] = amount.strip()
            slots["budget_min"] = amount.strip()

    # Phase 9B: extract room dimensions/area
    _dim = _extract_dimensions(raw)
    if _dim:
        slots["room_size"] = _dim["raw"]
        if "width_m" in _dim:
            slots["width_m"] = _dim["width_m"]
        if "length_m" in _dim:
            slots["length_m"] = _dim["length_m"]
        if "area_m2" in _dim:
            slots["area_m2"] = _dim["area_m2"]

    _is_from_budget = bool(
        re.search(r'\btu\s*\d+(?:[\.,]\d+)?\s*(trieu|tr|nghin)\s*tro\s*len\b', folded, re.I)
        or re.search(r'\btu\s*\d+(?:[\.,]\d+)?\s*(trieu|tr|nghin)\b', folded, re.I)
    )
    categories = parse_product_categories(raw)
    if _is_from_budget and categories and fold_text(categories[0]) == "tu":
        categories = []
    if categories:
        slots["product_category"] = categories[0]
        slots.setdefault("product_type", categories[0])
    if re.search(r"\bghe\s+(?:thu\s*gian|em|mem|boc\s*nem|boc\s*vai|boc\s*da)\b", folded):
        slots["product_category"] = "Ghế"
        slots["product_type"] = "Ghế thư giãn"
        slots["product_subtype"] = "Ghế thư giãn"
    if re.search(r"\b(bo me|ba me|nguoi gia|nguoi lon tuoi|ong ba|elderly|senior)\b", folded):
        slots["health_need"] = "elder_friendly"
        constraints = list(slots.get("constraints") or [])
        if "elder_friendly" not in constraints:
            constraints.append("elder_friendly")
        slots["constraints"] = constraints

    # Phase 6B: extract explicit SKU reference (e.g. GHO-239, GHS-42048)
    sku_ref = extract_sku_reference(raw)
    if sku_ref:
        slots["product_sku_ref"] = sku_ref

    price = parse_price_constraint(raw)
    # Phase 9B: prevent dimension false positive ("3m x 5m" -> price_target=3,000,000)
    _dim_fp = bool(re.search(r"\b\d+\s*m\s*x\s*\d+\s*m?\b", raw, re.I))
    if price.min_price is not None and not _dim_fp:
        slots["price_min"] = price.min_price
    if price.max_price is not None and not _dim_fp:
        slots["price_max"] = price.max_price
    if price.target_price is not None and not _dim_fp:
        slots["price_target"] = price.target_price

    try:
        base_slots = extract_sales_flow_slots(raw)
    except Exception:
        base_slots = {}
    for key in (
        "budget_text", "budget_usd", "style", "color", "material", "space", "product_type", "size",
        "room", "constraints", "pets", "kids", "children", "back_pain", "health_need", "easy_clean", "objection_type",
    ):
        if key in base_slots and key not in slots:
            slots[key] = base_slots[key]
    # Phase 9: skip budget_text false positive from dimension like "3m x 5m" or area "15m2"
    _is_meas_pattern = bool(re.search(r"\b\d+\s*m\s*x\s*\d+\s*m?\b", raw, re.I)
                            or re.search(r"\b\d+\s*(m²|m2|sqm|mét\s+vuông)\b", raw, re.I)
                            or re.search(r"\b\d+\s*x\s*\d+\s*m?\b", raw, re.I))
    if _is_meas_pattern:
        slots.pop("budget_text", None)
        slots.pop("budget", None)
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
