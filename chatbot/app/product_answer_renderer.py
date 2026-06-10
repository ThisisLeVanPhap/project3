import re
from typing import Any, Dict, List, Sequence

from .answer_evaluator import extract_context_facts
from .retrievers.text import fold_accents, repair_mojibake


MISSING_FIELD_FALLBACK = (
    "Mình chưa thấy thông tin này trong dữ liệu hiện có. "
    "Bạn nên liên hệ trực tiếp cửa hàng để xác nhận chính sách/chi tiết này."
)
NO_CONTEXT_FALLBACK = "Mình chưa tìm thấy sản phẩm phù hợp trong dữ liệu hiện có."
PRODUCT_KEYWORDS = (
    "sofa", "rèm", "rem", "kệ", "ke", "bàn", "ban", "ghế", "ghe",
    "thảm", "tham", "đèn", "den", "tủ", "tu", "giường", "giuong",
    "tranh", "gương", "guong",
)
POLICY_KEYWORDS = (
    "bảo hành", "bao hanh", "vận chuyển", "van chuyen", "ship",
    "lắp đặt", "lap dat", "đổi trả", "doi tra", "địa chỉ", "dia chi",
    "showroom", "tuyển", "tuyen",
)
OUT_OF_SCOPE_KEYWORDS = (
    "điện thoại", "dien thoai", "phone", "smartphone", "laptop",
    "máy tính", "may tinh",
)


def _clean(value: Any) -> str:
    return repair_mojibake(str(value or "")).strip()


def _norm(value: Any) -> str:
    return fold_accents(_clean(value)).lower()


def detect_answer_intent(query: str) -> str:
    text = _norm(query)
    if any(keyword in text for keyword in OUT_OF_SCOPE_KEYWORDS):
        return "out_of_scope_or_policy"
    if any(keyword in text for keyword in POLICY_KEYWORDS):
        return "missing_field"
    if re.search(r"\b(so sanh|khac nhau|nen chon|vs)\b", text):
        return "comparison"
    if re.search(r"\b(duoi|tren|tu .{0,20} den|khoang|tam|trieu|nghin|k)\b", text):
        return "price_constraint"
    if re.search(r"\b(hop voi|di cung|phoi|kem|bo phong)\b", text):
        return "multi_category_matching"
    if any(keyword in text for keyword in PRODUCT_KEYWORDS):
        return "listing"
    return "unknown"


def _products_from_context(context: str) -> List[Dict[str, Any]]:
    facts = extract_context_facts(context)
    return list(facts.get("products", {}).values())


def _field(product: Dict[str, Any], key: str) -> str:
    return _clean(product.get(key))


def _attribute_line(product: Dict[str, Any]) -> str:
    attrs = []
    for label, key in (
        ("Chất liệu", "material"),
        ("Màu sắc", "color"),
        ("Kích thước", "dimensions"),
        ("SKU", "sku"),
    ):
        value = _field(product, key)
        if value:
            attrs.append(f"{label}: {value}")
    availability = _field(product, "availability")
    if availability:
        if "InStock" in availability:
            attrs.append("Trạng thái trên trang sản phẩm: InStock")
        else:
            attrs.append(f"Tình trạng: {availability}")
    return "; ".join(attrs)


def _product_title(product: Dict[str, Any]) -> str:
    name = _field(product, "product_name") or "Sản phẩm trong dữ liệu hiện có"
    pid = _field(product, "pid")
    return f"{name} [{pid}]" if pid else name


def render_listing_answer(query: str, products: Sequence[Dict[str, Any]], max_products: int = 3) -> str:
    selected = list(products)[: max(1, max_products)]
    if not selected:
        return render_no_context_answer(query)

    lines = ["Mình tìm thấy một số sản phẩm phù hợp trong dữ liệu hiện có:"]
    for idx, product in enumerate(selected, start=1):
        lines.append("")
        lines.append(f"{idx}. {_product_title(product)}")
        price = _field(product, "price")
        category = _field(product, "category")
        attrs = _attribute_line(product)
        source_url = _field(product, "source_url")
        if price:
            lines.append(f"   - Giá: {price}")
        if category:
            lines.append(f"   - Danh mục: {category}")
        if attrs:
            lines.append(f"   - Thuộc tính chính: {attrs}")
        if source_url:
            lines.append(f"   - Link nguồn: {source_url}")
    lines.extend([
        "",
        "Lưu ý: Giá là giá tham khảo theo dữ liệu hiện có, nên xác nhận lại với cửa hàng trước khi mua.",
    ])
    return "\n".join(lines)


def render_comparison_answer(query: str, products: Sequence[Dict[str, Any]], max_products: int = 4) -> str:
    selected = list(products)[: max(1, max_products)]
    if not selected:
        return render_no_context_answer(query)

    lines = [
        "Dưới đây là so sánh dựa trên dữ liệu hiện có:",
        "",
        "| Sản phẩm | Giá | Danh mục | Chất liệu / kích thước | Nguồn |",
        "|---|---:|---|---|---|",
    ]
    for product in selected:
        attrs = []
        for key in ("material", "dimensions"):
            value = _field(product, key)
            if value:
                attrs.append(value)
        source_url = _field(product, "source_url")
        source = f"[Link nguồn]({source_url})" if source_url else ""
        lines.append(
            "| "
            + " | ".join([
                _product_title(product),
                _field(product, "price"),
                _field(product, "category"),
                "; ".join(attrs),
                source,
            ])
            + " |"
        )
    lines.append("")
    lines.append("Gợi ý chọn: nên ưu tiên sản phẩm có giá, danh mục và thuộc tính phù hợp nhất với nhu cầu bạn đã nêu.")
    return "\n".join(lines)


def render_missing_or_policy_answer(query: str, context: str) -> str:
    return MISSING_FIELD_FALLBACK


def render_no_context_answer(query: str) -> str:
    return NO_CONTEXT_FALLBACK


def render_product_answer(query: str, context: str, max_products: int = 3) -> str:
    intent = detect_answer_intent(query)
    if intent in {"missing_field", "out_of_scope_or_policy"}:
        return render_missing_or_policy_answer(query, context)

    products = _products_from_context(context)
    if not products:
        return render_no_context_answer(query)
    if intent == "comparison":
        return render_comparison_answer(query, products, max_products=max(2, min(max_products, 4)))
    return render_listing_answer(query, products, max_products=max_products)
