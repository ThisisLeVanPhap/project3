"""
general_compare_renderer — renderer cho mode GENERAL_COMPARE.

- Intent detection (recommendation / compare / price-sensitive / generic)
- Template response tiếng Việt, không phụ thuộc LLM.
- scoreReasons map sang tiếng Việt.
"""

import re
from typing import List, Optional

from .general_catalog_provider import BackendCatalogItem

# Intent patterns
RECOMMEND_PATTERN = re.compile(
    r"\b(gợi ý|gợi|tư vấn|nên mua|chọn|chon|phù hợp|phu hop|"
    r"recommend|suggest|advise|which|pick)\b",
    re.I,
)
COMPARE_PATTERN = re.compile(
    r"\b(so sánh|so sanh|khác nhau|khac nhau|"
    r"compare|comparison|vs|versus|difference|"
    r"nên chọn|nen chon|hay|hoặc|or)\b",
    re.I,
)
PRICE_PATTERN = re.compile(
    r"\b(dưới|duoi|dươi|duới|trên|tren|"
    r"tầm|tam|khoảng|khoang|"
    r"giá tốt|gia tot|rẻ|re|ngân sách|ngan sach|"
    r"budget|cheap|under|affordable|"
    r"triệu|trieu|tr|vnd|₫|đồng)\b",
    re.I,
)

# Map score reason keys to Vietnamese
SCORE_REASON_MAP = {
    "category_match": "đúng loại sản phẩm cần tìm",
    "material_match": "khớp chất liệu mong muốn",
    "price_within_budget": "nằm trong ngân sách",
    "price_above_minimum": "đáp ứng mức giá tối thiểu",
    "price_missing": "chưa có thông tin giá",
    "text_match": "mô tả/tên có liên quan đến yêu cầu",
    "source_match": "đúng nguồn được yêu cầu",
    "has_image": "có hình ảnh sản phẩm",
}

DEFAULT_MAX_ITEMS = 3


def detect_intent(query: str) -> str:
    """Phân loại ý định cho general_compare query."""
    if not query:
        return "generic"
    if COMPARE_PATTERN.search(query):
        return "compare"
    if RECOMMEND_PATTERN.search(query):
        return "recommendation"
    if PRICE_PATTERN.search(query):
        return "price_sensitive"
    return "generic"


def _map_reasons(reasons: List[str]) -> List[str]:
    """Map scoreReasons tiếng Anh sang tiếng Việt."""
    mapped = []
    for r in reasons:
        vi = SCORE_REASON_MAP.get(r.strip().lower())
        mapped.append(vi if vi else r)
    return mapped


def _price_str(price: Optional[float], currency: Optional[str]) -> str:
    if price is None:
        return "chưa có giá"
    c = currency or "VND"
    return f"{price:,.0f} {c}".replace(",", ".")


def _material_str(material: Optional[str]) -> str:
    if material:
        return material
    return "chưa rõ chất liệu"


def _category_str(category: Optional[str]) -> str:
    if category:
        return category
    return "chưa rõ danh mục"


def render_recommendation(query: str, items: List[BackendCatalogItem], max_items: int = DEFAULT_MAX_ITEMS) -> str:
    """Render gợi ý sản phẩm dạng recommendation."""
    if not items:
        return _no_data_message()

    top = items[:max_items]
    lines = ["Mình tìm trong dữ liệu sản phẩm công khai và thấy các lựa chọn phù hợp nhất là:"]
    lines.append("")

    for i, item in enumerate(top, 1):
        lines.append(f"{i}. {item.name}")
        lines.append(f"   Giá: {_price_str(item.price, item.currency)}")
        if item.material:
            lines.append(f"   Chất liệu: {item.material}")
        if item.category:
            lines.append(f"   Danh mục: {item.category}")
        if item.source_name:
            lines.append(f"   Nguồn: {item.source_name}")
        if item.score_reasons:
            reasons = _map_reasons(item.score_reasons)
            lines.append(f"   Vì sao phù hợp: {'; '.join(reasons)}")
        if item.source_url:
            lines.append(f"   Xem thêm: {item.source_url}")
        lines.append("")

    # Recommendation summary
    best = top[0]
    lines.append("—" * 30)
    if best.price is not None:
        low_price = min((i.price for i in top if i.price is not None), default=None)
        if best.price == low_price:
            lines.append("Nếu ưu tiên giá thấp: chọn " + best.name)
        if best.material and top[-1].material != best.material:
            lines.append(f"Nếu ưu tiên chất liệu '{best.material}': chọn " + best.name)
    lines.append(f"Nếu muốn cân nhắc thêm: tham khảo thêm các lựa chọn trên.")

    lines.append("")
    lines.append("Mình luôn cập nhật từ dữ liệu công khai. Bạn cho mình biết thêm nhu cầu để mình tìm chính xác hơn nhé.")
    return "\n".join(lines)


def render_comparison(query: str, items: List[BackendCatalogItem], max_items: int = DEFAULT_MAX_ITEMS) -> str:
    """Render so sánh sản phẩm dạng compare."""
    if not items:
        return _no_data_message()

    top = items[:max_items]
    lines = ["So sánh nhanh các lựa chọn nổi bật:"]
    lines.append("")

    for i, item in enumerate(top, 1):
        lines.append(f"{i}. {item.name}")
        lines.append(f"   Giá: {_price_str(item.price, item.currency)}")
        if item.material:
            lines.append(f"   Chất liệu: {item.material}")
        if item.category:
            lines.append(f"   Danh mục: {item.category}")
        if item.dimensions_text:
            lines.append(f"   Kích thước: {item.dimensions_text}")
        if item.source_name:
            lines.append(f"   Nguồn: {item.source_name}")
        if item.score_reasons:
            strengths = _map_reasons([r for r in item.score_reasons if "missing" not in r])
            if strengths:
                lines.append(f"   Điểm mạnh: {'; '.join(strengths)}")
        if item.source_url:
            lines.append(f"   Xem thêm: {item.source_url}")
        lines.append("")

    # Summarize
    lines.append("—" * 30)
    if len(top) >= 2:
        best_price = min((i for i in top if i.price is not None), key=lambda x: x.price, default=None)
        if best_price:
            lines.append(f"Nếu ưu tiên giá thấp: chọn {best_price.name}")
        best_material = [i for i in top if i.material]
        if best_material:
            lines.append(f"Nếu ưu tiên chất liệu rõ ràng: chọn {best_material[0].name}")
    lines.append(f"Nếu muốn cân bằng: tham khảo thêm các lựa chọn trên và chọn theo nhu cầu cụ thể.")

    lines.append("")
    lines.append("Các thông tin trên dựa trên dữ liệu sản phẩm công khai hiện có.")
    return "\n".join(lines)


def render_price_sensitive(query: str, items: List[BackendCatalogItem], max_items: int = DEFAULT_MAX_ITEMS) -> str:
    """Render gợi ý ưu tiên ngân sách."""
    # Sort by price ascending for budget-friendly view, but preserve original relevance
    if not items:
        return _no_data_message()

    top = items[:max_items]
    lines = ["Dựa trên dữ liệu giá công khai, mình tìm thấy các lựa chọn phù hợp ngân sách:"]
    lines.append("")

    for i, item in enumerate(top, 1):
        lines.append(f"{i}. {item.name}")
        lines.append(f"   Giá: {_price_str(item.price, item.currency)}")
        if item.material:
            lines.append(f"   Chất liệu: {item.material}")
        if item.source_name:
            lines.append(f"   Nguồn: {item.source_name}")
        if item.score_reasons:
            reasons = _map_reasons(item.score_reasons)
            lines.append(f"   Vì sao phù hợp: {'; '.join(reasons)}")
        if item.source_url:
            lines.append(f"   Xem thêm: {item.source_url}")
        lines.append("")

    lines.append("—" * 30)
    lines.append("Thông tin giá mang tính tham khảo tại thời điểm thu thập. Vui lòng kiểm tra lại giá tại cửa hàng trước khi quyết định.")
    return "\n".join(lines)


def render_generic(query: str, items: List[BackendCatalogItem], max_items: int = DEFAULT_MAX_ITEMS) -> str:
    """Render generic search results."""
    if not items:
        return _no_data_message()

    top = items[:max_items]
    lines = ["Mình tìm thấy các sản phẩm sau từ dữ liệu công khai:"]
    lines.append("")

    for i, item in enumerate(top, 1):
        lines.append(f"{i}. {item.name}")
        lines.append(f"   Giá: {_price_str(item.price, item.currency)}")
        if item.material:
            lines.append(f"   Chất liệu: {item.material}")
        if item.category:
            lines.append(f"   Danh mục: {item.category}")
        if item.source_name:
            lines.append(f"   Nguồn: {item.source_name}")
        if item.source_url:
            lines.append(f"   Xem thêm: {item.source_url}")
        lines.append("")

    lines.append("Bạn muốn tìm hiểu thêm về sản phẩm nào, hay muốn so sánh giữa các lựa chọn trên?")
    return "\n".join(lines)


def _no_data_message() -> str:
    return (
        "Hiện mình chưa có đủ dữ liệu sản phẩm công khai phù hợp với yêu cầu này. "
        "Bạn có thể thử nới ngân sách, mô tả loại sản phẩm cụ thể hơn, hoặc dùng từ khóa khác nhé."
    )


def render_general_compare(query: str, items: List[BackendCatalogItem], max_items: int = DEFAULT_MAX_ITEMS) -> str:
    """Main entry point: detect intent and render."""
    if not items:
        return _no_data_message()

    intent = detect_intent(query)
    if intent == "compare":
        return render_comparison(query, items, max_items)
    elif intent == "recommendation":
        return render_recommendation(query, items, max_items)
    elif intent == "price_sensitive":
        return render_price_sensitive(query, items, max_items)
    else:
        return render_generic(query, items, max_items)
