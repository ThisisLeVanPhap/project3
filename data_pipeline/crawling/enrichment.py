import re
import unicodedata
from typing import Optional

from bs4 import BeautifulSoup

from data_pipeline.crawling.normalize import normalize_text
from data_pipeline.crawling.schema import ProductObservation


ATTRIBUTE_KEYS = {
    "chat lieu": "material",
    "vat lieu": "material",
    "material": "material",
    "kich thuoc": "dimensions",
    "size": "dimensions",
    "dimensions": "dimensions",
    "mau sac": "color",
    "mau": "color",
    "color": "color",
    "danh muc": "category",
    "category": "category",
}

SPEC_KEY_PATTERN = (
    r"Chất liệu|Vật liệu|Material|"
    r"Kích thước(?:\s*\([^)]*\))?|Size|Dimensions|"
    r"Màu sắc|Màu|Color|"
    r"Danh mục|Category|"
    r"Bảo hành|Phụ kiện|Thời gian nhận hàng|Thời gian giao hàng|Giao hàng|Xuất xứ"
)

SECTION_STOP_PATTERN = (
    r"Đặc điểm|Ưu điểm|Lý do|Thông tin|Giới thiệu|Tag liên quan|"
    r"Đánh Giá|Đánh giá|Nhận xét|Bình luận"
)

FIELD_MAX_LENGTH = {
    "material": 200,
    "color": 120,
    "dimensions": 120,
    "category": 80,
}

MATERIAL_KEYWORDS = (
    ("vải polyester", "Vải polyester"),
    ("vải", "Vải"),
    ("gỗ tự nhiên", "Gỗ tự nhiên"),
    ("gỗ công nghiệp", "Gỗ công nghiệp"),
    ("mdf", "MDF"),
    ("mfc", "MFC"),
    ("gỗ sồi", "Gỗ sồi"),
    ("gỗ óc chó", "Gỗ óc chó"),
    ("kim loại", "Kim loại"),
    ("nỉ", "Nỉ"),
    ("kính", "Kính"),
)

CATEGORY_KEYWORDS = (
    ("bàn ghế ăn", "Bàn ăn"),
    ("bộ bàn ăn", "Bàn ăn"),
    ("bàn ăn", "Bàn ăn"),
    ("bàn trà", "Bàn trà"),
    ("bàn sofa", "Bàn trà"),
    ("ghế sofa", "Sofa"),
    ("sofa", "Sofa"),
    ("ghế", "Ghế"),
    ("giường tầng", "Giường"),
    ("giường", "Giường"),
    ("kệ tivi", "Kệ"),
    ("kệ để sách", "Kệ"),
    ("kệ", "Kệ"),
    ("tủ quần áo", "Tủ"),
    ("tủ", "Tủ"),
    ("rèm lá dọc", "Rèm"),
    ("rèm cuốn", "Rèm"),
    ("rèm sáo", "Rèm"),
    ("rèm cửa", "Rèm"),
    ("rèm", "Rèm"),
    ("mành", "Rèm"),
    ("đèn trang trí", "Đèn"),
    ("đèn ngủ", "Đèn"),
    ("đèn bàn", "Đèn"),
    ("đèn thả", "Đèn"),
    ("đèn", "Đèn"),
    ("thảm", "Thảm"),
    ("tranh treo tường", "Tranh"),
    ("tranh", "Tranh"),
    ("gương", "Gương"),
    ("lọ hoa", "Đồ trang trí"),
    ("bình hoa", "Đồ trang trí"),
    ("bình", "Đồ trang trí"),
    ("đồng hồ", "Đồ trang trí"),
    ("đồ trang trí", "Đồ trang trí"),
    ("trang trí", "Đồ trang trí"),
    ("decor", "Đồ trang trí"),
)


def extract_attribute_value_pairs(text: str) -> dict[str, str]:
    """Extract simple Vietnamese furniture spec values into normalized fields."""
    normalized = _clean_text(text)
    if not normalized:
        return {}

    pairs: dict[str, str] = {}
    for key, value in _iter_key_value_candidates(normalized):
        field = ATTRIBUTE_KEYS.get(_strip_accents_ascii(key))
        clean_value = _clean_field_value(field, value) if field else None
        if field and clean_value and field not in pairs:
            pairs[field] = clean_value
    return pairs


def infer_material(text: str) -> Optional[str]:
    normalized = _strip_accents_ascii(_clean_text(text))
    if re.search(r"\bda\s+(?:that|cong nghiep|pu|bo)\b", normalized):
        if "cong nghiep" in normalized:
            return "Da công nghiệp"
        if "pu" in normalized:
            return "Da PU"
        if "bo" in normalized:
            return "Da bò"
        return "Da thật"
    if re.search(r"\b(?:chat lieu da|boc da|sofa\b.*\bda)\b", normalized):
        return "Da"
    for keyword, label in MATERIAL_KEYWORDS:
        if re.search(rf"\b{re.escape(_strip_accents_ascii(keyword))}\b", normalized):
            return label
    return None


def infer_dimensions(text: str) -> Optional[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return None

    patterns = (
        r"\b(?:D\s*)?\d+(?:[.,]\d+)?\s*(?:m|cm|mm)?\s*x\s*(?:R\s*)?\d+(?:[.,]\d+)?\s*(?:m|cm|mm)?\s*x\s*(?:C\s*)?\d+(?:[.,]\d+)?\s*(?:m|cm|mm)\b",
        r"\b\d+(?:[.,]\d+)?\s*m\s*x\s*\d+(?:[.,]\d+)?\s*cm\b",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return normalize_text(match.group(0))
    return None


def infer_category(product_name: str, text: str = "") -> Optional[str]:
    """Infer category from product_name only.

    The text argument is kept for backward compatibility but intentionally not
    used, because full page text often contains related products and tags.
    """
    haystack = _strip_accents_ascii(product_name or "")
    for keyword, category in CATEGORY_KEYWORDS:
        if re.search(rf"\b{re.escape(_strip_accents_ascii(keyword))}\b", haystack):
            return category
    return None


def enrich_product_from_text(observation: ProductObservation, text: str) -> ProductObservation:
    """Fill missing furniture fields from text without overwriting extractor output."""
    combined_text = "\n".join(part for part in (observation.description, text) if part)
    trusted_text = "\n".join(part for part in (observation.product_name, observation.description) if part)
    pairs = extract_attribute_value_pairs(combined_text)
    enriched_fields: list[str] = []

    for field in ("material", "dimensions", "color"):
        if not getattr(observation, field) and pairs.get(field):
            setattr(observation, field, pairs[field])
            enriched_fields.append(field)

    if not observation.material:
        material = infer_material(trusted_text)
        if material:
            observation.material = material
            enriched_fields.append("material")

    if not observation.dimensions:
        dimensions = infer_dimensions(combined_text)
        if dimensions:
            observation.dimensions = dimensions
            enriched_fields.append("dimensions")

    if not observation.category:
        category = pairs.get("category") or infer_category(observation.product_name)
        if category:
            observation.category = category
            enriched_fields.append("category")

    if enriched_fields:
        observation.metadata = {
            **dict(observation.metadata),
            "enriched": True,
            "enrichment_fields": enriched_fields,
            "enrichment_method": "rule_based_text",
        }
    return observation


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return normalize_text(soup.get_text("\n", strip=True)) or ""


def _iter_key_value_candidates(text: str):
    pattern = re.compile(
        rf"(?P<key>{SPEC_KEY_PATTERN})\s*:\s*"
        rf"(?P<value>.*?)"
        rf"(?=\s+(?:{SPEC_KEY_PATTERN})\s*:|\s+(?:{SECTION_STOP_PATTERN})\b|$)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        yield match.group("key"), match.group("value")


def _clean_field_value(field: Optional[str], value: str) -> Optional[str]:
    cleaned = normalize_text(value)
    if not cleaned:
        return None
    cleaned = cleaned.strip(" .;:-")

    max_length = FIELD_MAX_LENGTH.get(field or "", 160)
    if len(cleaned) > max_length:
        first_sentence = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0]
        cleaned = first_sentence if len(first_sentence) <= max_length else cleaned[:max_length].rstrip(" ,.;:-")
    return cleaned or None


def _clean_text(text: str) -> str:
    return normalize_text(text) or ""


def _strip_accents_ascii(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text or "")
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D").lower()
