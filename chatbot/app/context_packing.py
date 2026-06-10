from typing import Any, Dict, List, Optional, Sequence, Set

from .retrievers.schemas import RetrievalResult
from .retrievers.text import repair_mojibake


NO_PRODUCT_CONTEXT = "Không tìm thấy sản phẩm phù hợp trong KB."


def _metadata(hit: Any) -> Dict[str, Any]:
    if isinstance(hit, RetrievalResult):
        metadata = hit.metadata
    elif isinstance(hit, dict):
        metadata = hit.get("metadata") or {}
    else:
        metadata = getattr(hit, "metadata", {}) or {}
    return metadata if isinstance(metadata, dict) else {}


def _field(hit: Any, name: str, default: Any = "") -> Any:
    if isinstance(hit, RetrievalResult):
        return getattr(hit, name, default)
    if isinstance(hit, dict):
        return hit.get(name, default)
    return getattr(hit, name, default)


def _clean(value: Any) -> str:
    if value in (None, ""):
        return ""
    return repair_mojibake(str(value)).strip()


def _truncate(value: str, max_chars: int) -> str:
    value = " ".join((value or "").split())
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 3)].rstrip() + "..."


def get_product_source_url(hit: Any) -> str:
    metadata = _metadata(hit)
    for key in ("source_url", "canonical_url", "url"):
        value = _clean(metadata.get(key))
        if value:
            return value
    return _clean(_field(hit, "source"))


def format_price(value: Any, currency: Optional[str] = "VND") -> str:
    if value in (None, ""):
        return ""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return _clean(value)

    if numeric.is_integer():
        formatted = f"{int(numeric):,}".replace(",", ".")
    else:
        formatted = f"{numeric:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    currency_text = _clean(currency) or "VND"
    return f"{formatted} {currency_text}".strip()


def is_product_hit(hit: Any) -> bool:
    metadata = _metadata(hit)
    if _clean(metadata.get("doc_type")).lower() == "product":
        return True
    return any(metadata.get(key) not in (None, "") for key in ("product_name", "price", "sku"))


def _first_value(*values: Any) -> str:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return ""


def format_product_context_block(hit: Any, idx: int, max_chars_per_product: int = 900) -> str:
    metadata = _metadata(hit)
    currency = metadata.get("currency") or "VND"
    source_url = get_product_source_url(hit)
    title = _first_value(metadata.get("product_name"), _field(hit, "title"))
    description = _first_value(_field(hit, "text"), _field(hit, "content"))

    fields = [
        f"[P{idx}]",
        f"Tên sản phẩm: {title}" if title else "",
        f"Danh mục: {_clean(metadata.get('category'))}" if _clean(metadata.get("category")) else "",
        f"Giá: {format_price(metadata.get('price'), currency)}" if format_price(metadata.get("price"), currency) else "",
        f"Giá gốc: {format_price(metadata.get('original_price'), currency)}" if format_price(metadata.get("original_price"), currency) else "",
        f"Chất liệu: {_clean(metadata.get('material'))}" if _clean(metadata.get("material")) else "",
        f"Màu sắc: {_clean(metadata.get('color'))}" if _clean(metadata.get("color")) else "",
        f"Kích thước: {_clean(metadata.get('dimensions'))}" if _clean(metadata.get("dimensions")) else "",
        f"Thương hiệu: {_clean(metadata.get('brand'))}" if _clean(metadata.get("brand")) else "",
        f"SKU: {_clean(metadata.get('sku'))}" if _clean(metadata.get("sku")) else "",
        f"Tình trạng: {_clean(metadata.get('availability'))}" if _clean(metadata.get("availability")) else "",
        f"Link nguồn: {source_url}" if source_url else "",
        f"Mô tả ngắn: {_truncate(description, max_chars_per_product)}" if description else "",
    ]
    return "\n".join(field for field in fields if field)


def _format_document_context_block(hit: Any, idx: int, max_chars: int) -> str:
    title = _clean(_field(hit, "title")) or "Tài liệu KB"
    source = _clean(_field(hit, "source")) or get_product_source_url(hit)
    text = _truncate(_clean(_field(hit, "text") or _field(hit, "content")), max_chars)
    lines = [f"[D{idx}]", f"Tiêu đề: {title}"]
    if source:
        lines.append(f"Link nguồn: {source}")
    if text:
        lines.append(f"Nội dung: {text}")
    return "\n".join(lines)


def format_grounded_context(
    hits: Sequence[RetrievalResult],
    max_products: int = 4,
    max_chars_per_product: int = 900,
) -> str:
    if not hits:
        return NO_PRODUCT_CONTEXT

    blocks: List[str] = []
    seen_sources: Set[str] = set()
    product_count = 0
    doc_count = 0

    for hit in hits:
        if is_product_hit(hit):
            if product_count >= max_products:
                continue
            source_key = get_product_source_url(hit).lower()
            if source_key and source_key in seen_sources:
                continue
            if source_key:
                seen_sources.add(source_key)
            product_count += 1
            blocks.append(format_product_context_block(hit, product_count, max_chars_per_product))
        else:
            source_key = (get_product_source_url(hit) or _clean(_field(hit, "source"))).lower()
            if source_key and source_key in seen_sources:
                continue
            if source_key:
                seen_sources.add(source_key)
            doc_count += 1
            blocks.append(_format_document_context_block(hit, doc_count, max_chars_per_product))

    return "\n\n".join(block for block in blocks if block) or NO_PRODUCT_CONTEXT
