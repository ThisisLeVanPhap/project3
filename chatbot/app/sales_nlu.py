import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol

from .product_filters import parse_price_constraint, parse_product_categories
from .retrievers.text import fold_accents, repair_mojibake


PHONE_RE = re.compile(r"(?<!\d)(0[35789](?:[\s.\-]?\d){8}|\+?84(?:[\s.\-]?\d){9})(?!\d)")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)


DISCOVERY = "DISCOVERY"
RECOMMENDATION = "RECOMMENDATION"
COMPARE = "COMPARE"
PRODUCT_DETAIL = "PRODUCT_DETAIL"
BUY_INTENT = "BUY_INTENT"
PROVIDE_CONTACT = "PROVIDE_CONTACT"
PROVIDE_ADDRESS = "PROVIDE_ADDRESS"
ASK_SHIPPING = "ASK_SHIPPING"
ASK_PAYMENT = "ASK_PAYMENT"
OFF_TOPIC = "OFF_TOPIC"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class NLUResult:
    intent: str
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    source: str = "fallback"


class NLUAdapter(Protocol):
    def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> Optional[NLUResult]:
        ...


class NoOpMLIntentAdapter:
    def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> Optional[NLUResult]:
        return NLUResult(intent=UNKNOWN, confidence=0.0, entities={}, source="ml")


class DeterministicLLMFallbackAdapter:
    def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> Optional[NLUResult]:
        return NLUResult(intent=UNKNOWN, confidence=0.1, entities={}, source="fallback")


def _norm(text: Any) -> str:
    return fold_accents(repair_mojibake(str(text or ""))).lower()


def _extract_phone(text: str) -> str:
    match = PHONE_RE.search(repair_mojibake(text or ""))
    if not match:
        return ""
    digits = re.sub(r"\D", "", match.group(0))
    if digits.startswith("84") and len(digits) == 11:
        return "0" + digits[2:]
    return digits


def _first_category(text: str) -> str:
    categories = parse_product_categories(text)
    return categories[0] if categories else ""


def _extract_entities(text: str) -> Dict[str, Any]:
    normalized = _norm(text)
    entities: Dict[str, Any] = {}

    category = _first_category(text)
    if category:
        entities["product_category"] = category

    price = parse_price_constraint(text)
    if price.min_price is not None:
        entities["price_min"] = price.min_price
    if price.max_price is not None:
        entities["price_max"] = price.max_price
    if price.target_price is not None:
        entities["price_target"] = price.target_price

    material_patterns = (
        ("go cong nghiep", ("go cong nghiep", "mdf", "mfc", "hdf")),
        ("go tu nhien", ("go tu nhien",)),
        ("go", ("go", "wood")),
        ("da", ("da", "leather")),
        ("vai", ("vai", "fabric", "ni")),
        ("kim loai", ("kim loai", "sat", "thep", "metal", "steel")),
        ("kinh", ("kinh", "glass")),
    )
    for material, patterns in material_patterns:
        if any(pattern in normalized for pattern in patterns):
            entities["material"] = material
            break

    phone = _extract_phone(text)
    if phone:
        entities["phone"] = phone
    email = EMAIL_RE.search(repair_mojibake(text or ""))
    if email:
        entities["email"] = email.group(0)

    qty = re.search(r"\b(?:lay|mua|dat|order)?\s*(\d{1,3})\s*(?:cai|bo|chiec|sp|san pham)\b", normalized)
    if qty:
        entities["quantity"] = int(qty.group(1))

    if re.search(r"\b(ha noi|hn|ho chi minh|hcm|sai gon|da nang|quan|huyen|phuong|duong|so nha|tinh)\b", normalized):
        entities["delivery_area"] = repair_mojibake(text or "").strip()
        entities["address"] = repair_mojibake(text or "").strip()

    if re.search(r"\b(hom nay|ngay mai|tuan nay|cuoi tuan|thang nay|gap|som|sau nay)\b", normalized):
        entities["purchase_timing"] = repair_mojibake(text or "").strip()

    size = re.search(r"\b(\d{2,4}\s*(?:x|[*])\s*\d{2,4}(?:\s*(?:x|[*])\s*\d{2,4})?\s*(?:cm|mm|m)?)\b", normalized)
    if size:
        entities["size"] = size.group(1)

    for style in ("hien dai", "toi gian", "co dien", "bac au", "industrial", "modern", "minimal", "classic"):
        if style in normalized:
            entities["style"] = style
            break

    return entities


def _rule_classify(text: str) -> Optional[NLUResult]:
    normalized = _norm(text)
    entities = _extract_entities(text)

    if re.search(r"\b(thoi tiet|bong da|chung khoan|nau an|du lich|dien thoai|laptop|politics|weather|football)\b", normalized):
        return NLUResult(OFF_TOPIC, 0.95, entities, "rule")
    if entities.get("phone") or entities.get("email"):
        return NLUResult(PROVIDE_CONTACT, 0.95, entities, "rule")
    if entities.get("address") or entities.get("delivery_area"):
        return NLUResult(PROVIDE_ADDRESS, 0.85, entities, "rule")
    if re.search(r"\b(so sanh|cai nao tot hon|khac gi|khac nhau| vs |compare)\b", f" {normalized} "):
        return NLUResult(COMPARE, 0.92, entities, "rule")
    if re.search(r"\b(ship|giao hang|van chuyen|bao lau|phi giao|con hang|ton kho)\b", normalized):
        return NLUResult(ASK_SHIPPING, 0.9, entities, "rule")
    if re.search(r"\b(thanh toan|tra gop|chuyen khoan|cod|payment)\b", normalized):
        return NLUResult(ASK_PAYMENT, 0.9, entities, "rule")
    if re.search(r"\b(mua|dat hang|dat mua|chot|lay cai|lay mau|toi lay|order|buy|purchase)\b", normalized):
        return NLUResult(BUY_INTENT, 0.9, entities, "rule")
    if re.search(r"\b(chi tiet|kich thuoc|chat lieu|mau sac|gia bao nhieu|bao nhieu)\b", normalized):
        return NLUResult(PRODUCT_DETAIL, 0.78, entities, "rule")
    if re.search(r"\b(tu van|goi y|tim|mau|san pham|co .+ khong|can)\b", normalized) or entities.get("product_category") or entities.get("material"):
        intent = RECOMMENDATION if re.search(r"\b(tu van|goi y|phu hop|nen chon)\b", normalized) else DISCOVERY
        return NLUResult(intent, 0.82, entities, "rule")
    return None


def classify_sales_nlu(
    text: str,
    context: Optional[Dict[str, Any]] = None,
    ml_adapter: Optional[NLUAdapter] = None,
    llm_adapter: Optional[NLUAdapter] = None,
) -> NLUResult:
    rule = _rule_classify(text)
    if rule is not None:
        return rule

    ml = (ml_adapter or NoOpMLIntentAdapter()).classify(text, context)
    if ml and ml.confidence >= 0.55:
        return ml

    fallback = (llm_adapter or DeterministicLLMFallbackAdapter()).classify(text, context)
    if fallback:
        return fallback
    return NLUResult(UNKNOWN, 0.0, {}, "fallback")
