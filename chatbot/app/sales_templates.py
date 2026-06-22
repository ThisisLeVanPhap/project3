from typing import Any, Dict, List, Sequence

from .retrievers.text import repair_mojibake


def clean(value: Any) -> str:
    return repair_mojibake(str(value or "")).strip()


def product_title(product: Dict[str, Any]) -> str:
    name = clean(product.get("product_name")) or "San pham trong du lieu hien co"
    pid = clean(product.get("pid"))
    return f"{name} [{pid}]" if pid else name


def product_reason(product: Dict[str, Any], query: str) -> str:
    category = clean(product.get("category"))
    material = clean(product.get("material"))
    parts: List[str] = []
    if category:
        parts.append(f"khop nhom {category}")
    if material:
        parts.append(f"co chat lieu {material}")
    if not parts:
        parts.append("khop voi ket qua tim kiem trong KB")
    return ", ".join(parts)


def render_recommendation_template(query: str, products: Sequence[Dict[str, Any]], max_products: int = 3, include_cta: bool = True) -> str:
    selected = list(products)[: max(1, max_products)]
    if not selected:
        return render_no_products_found_template()

    lines = ["Minh tim thay mot vai san pham phu hop:"]
    for idx, product in enumerate(selected, start=1):
        title = product_title(product)
        price = clean(product.get("price"))
        lines.append("")
        lines.append(f"{idx}. {title}" + (f" - {price}" if price else ""))
        lines.append(f"   Phu hop vi: {product_reason(product, query)}")
        sku = clean(product.get("sku"))
        source_url = clean(product.get("source_url"))
        if sku:
            lines.append(f"   SKU: {sku}")
        if source_url:
            lines.append(f"   Link: {source_url}")
    if include_cta:
        lines.append("")
        lines.append("Ban muon minh loc tiep theo khoang gia, kich thuoc hay chat lieu khong?")
    return "\n".join(lines)


def render_missing_info_template(missing_fields: Sequence[str] | None = None) -> str:
    questions = {
        "product_category": "Ban dang tim loai san pham nao?",
        "price_range": "Khoang gia mong muon khoang bao nhieu?",
        "material": "Ban uu tien chat lieu nao?",
        "delivery_area": "Ban muon nhan hang o khu vuc nao?",
        "phone": "Ban gui giup minh so dien thoai lien he nhe.",
        "address": "Ban gui giup minh khu vuc hoac dia chi nhan hang nhe.",
    }
    selected = list(missing_fields or ["product_category", "price_range"])[:2]
    lines = ["Minh co the tu van ky hon, nhung can them mot chut thong tin:"]
    for field in selected:
        question = questions.get(field)
        if question:
            lines.append(f"- {question}")
    return "\n".join(lines)


def render_no_products_found_template() -> str:
    return (
        "Minh chua tim thay san pham khop hoan toan. Ban co the noi ro hon ve loai san pham, "
        "chat lieu hoac khoang gia de minh loc lai khong?"
    )


def render_comparison_template(query: str, products: Sequence[Dict[str, Any]], max_products: int = 2) -> str:
    selected = list(products)[: max(2, max_products)]
    if len(selected) < 2:
        return "Ban muon so sanh nhung san pham nao? Ban co the noi ten, SKU hoac chon P1/P2 trong cac mau vua xem."
    lines = ["So sanh nhanh cac san pham ban quan tam:"]
    for product in selected:
        details = []
        for key in ("price", "material", "dimensions", "category"):
            value = clean(product.get(key))
            if value:
                details.append(value)
        reason = product_reason(product, query)
        lines.append(f"- {product_title(product)}: {', '.join(details) if details else 'chua co them thuoc tinh'}, phu hop vi {reason}.")
    lines.append("")
    lines.append("Ban nghieng ve lua chon nao hon?")
    return "\n".join(lines)


def render_cta_collect_info_template() -> str:
    return (
        "Neu ban muon, minh co the luu lai nhu cau de shop lien he tu van/chot don. "
        "Ban gui giup minh so dien thoai va khu vuc nhan hang nhe."
    )


def render_handoff_confirmation_template() -> str:
    return "Minh da ghi nhan nhu cau cua ban. Shop se lien he de tu van/chot don theo thong tin ban cung cap."


def render_off_topic_redirect_template() -> str:
    return "Minh chuyen ho tro tu van san pham noi that. Ban dang quan tam san pham nao de minh ho tro tot hon?"
