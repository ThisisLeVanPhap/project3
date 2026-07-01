from typing import Any, Dict, List, Sequence

from .retrievers.text import repair_mojibake


def clean(value: Any) -> str:
    return repair_mojibake(str(value or "")).strip()


def product_title(product: Dict[str, Any]) -> str:
    name = clean(product.get("product_name")) or "Sản phẩm trong dữ liệu hiện có"
    pid = clean(product.get("pid"))
    return f"{name} [{pid}]" if pid else name


def product_reason(product: Dict[str, Any], query: str) -> str:
    category = clean(product.get("category"))
    material = clean(product.get("material"))
    parts: List[str] = []
    if category:
        parts.append(f"khớp với nhóm {category}")
    if material:
        parts.append(f"có chất liệu {material}")
    if not parts:
        parts.append("khớp với kết quả tìm kiếm trong KB")
    return ", ".join(parts)


def render_recommendation_template(query: str, products: Sequence[Dict[str, Any]], max_products: int = 3, include_cta: bool = True) -> str:
    selected = list(products)[: max(1, max_products)]
    if not selected:
        return render_no_products_found_template()

    lines = ["Mình tìm thấy một vài sản phẩm phù hợp:"]
    for idx, product in enumerate(selected, start=1):
        title = product_title(product)
        price = clean(product.get("price"))
        lines.append("")
        lines.append(f"{idx}. {title}" + (f" - {price}" if price else ""))
        lines.append(f"   Phù hợp vì: {product_reason(product, query)}")
        sku = clean(product.get("sku"))
        source_url = clean(product.get("source_url"))
        if sku:
            lines.append(f"   SKU: {sku}")
        if source_url:
            lines.append(f"   Link: {source_url}")
    if include_cta:
        lines.append("")
        lines.append("Bạn muốn mình lọc tiếp theo khoảng giá, kích thước hay chất liệu không?")
    return "\n".join(lines)


def render_missing_info_template(missing_fields: Sequence[str] | None = None) -> str:
    questions = {
        "product_category": "Bạn đang tìm loại sản phẩm nào?",
        "price_range": "Khoảng giá mong muốn khoảng bao nhiêu?",
        "material": "Bạn ưu tiên chất liệu nào?",
        "delivery_area": "Bạn muốn nhận hàng ở khu vực nào?",
        "phone": "Bạn gửi giúp mình số điện thoại liên hệ nhé.",
        "address": "Bạn gửi giúp mình khu vực hoặc địa chỉ nhận hàng nhé.",
    }
    selected = list(missing_fields or ["product_category", "price_range"])[:2]
    lines = ["Mình có thể tư vấn kỹ hơn, nhưng cần thêm một chút thông tin:"]
    for field in selected:
        question = questions.get(field)
        if question:
            lines.append(f"- {question}")
    return "\n".join(lines)


def render_no_products_found_template() -> str:
    return (
        "Mình chưa tìm thấy sản phẩm khớp hoàn toàn. Bạn có thể nói rõ hơn về loại sản phẩm, "
        "chất liệu hoặc khoảng giá để mình lọc lại không?"
    )


def render_comparison_template(query: str, products: Sequence[Dict[str, Any]], max_products: int = 2) -> str:
    selected = list(products)[: max(2, max_products)]
    if len(selected) < 2:
        return "Bạn muốn so sánh những sản phẩm nào? Bạn có thể nói tên, SKU hoặc chọn P1/P2 trong các mẫu vừa xem."
    lines = ["So sánh nhanh các sản phẩm bạn quan tâm:"]
    for product in selected:
        details = []
        for key in ("price", "material", "dimensions", "category"):
            value = clean(product.get(key))
            if value:
                details.append(value)
        reason = product_reason(product, query)
        lines.append(f"- {product_title(product)}: {', '.join(details) if details else 'chưa có thêm thuộc tính'}, phù hợp vì {reason}.")
    lines.append("")
    lines.append("Bạn nghiêng về lựa chọn nào hơn?")
    return "\n".join(lines)


def render_cta_collect_info_template() -> str:
    return (
        "Nếu bạn muốn, mình có thể lưu lại nhu cầu để shop liên hệ tư vấn/chốt đơn. "
        "Bạn gửi giúp mình số điện thoại và khu vực nhận hàng nhé."
    )


def render_handoff_confirmation_template() -> str:
    return "Mình đã ghi nhận nhu cầu của bạn. Shop sẽ liên hệ để tư vấn/chốt đơn theo thông tin bạn cung cấp."


def render_off_topic_redirect_template() -> str:
    return "Mình chuyên hỗ trợ tư vấn sản phẩm nội thất. Bạn đang quan tâm sản phẩm nào để mình hỗ trợ tốt hơn?"
