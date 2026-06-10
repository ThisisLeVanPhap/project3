import argparse
import json
from pathlib import Path
from typing import Any, Optional

from data_pipeline.crawling.normalize import make_content_hash, normalize_text


def build_product_rag_document(product: dict[str, Any]) -> dict[str, Any]:
    """Convert one product row into a RAG-compatible single chunk/document."""
    tenant_id = product.get("tenant_id")
    source_url = product.get("canonical_url") or product.get("source_url") or ""
    product_name = normalize_text(product.get("product_name")) or "Sản phẩm"
    category = normalize_text(product.get("category"))
    title = f"{product_name} - {category}" if category else product_name
    doc_id = _stable_id(product)
    content = _build_content(product)
    metadata = _build_metadata(product)

    return {
        "doc_id": doc_id,
        "chunk_id": f"{doc_id}#chunk-0",
        "title": title,
        "text": content,
        "content": content,
        "source": source_url,
        "url": source_url,
        "shop": tenant_id or product.get("brand") or "product",
        "tenant_id": tenant_id,
        "metadata": metadata,
    }


def convert_product_jsonl_to_rag_jsonl(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    input_file = Path(input_path)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with input_file.open("r", encoding="utf-8") as source, output_file.open("w", encoding="utf-8") as target:
        for line in source:
            if not line.strip():
                continue
            product = json.loads(line)
            target.write(json.dumps(build_product_rag_document(product), ensure_ascii=False) + "\n")
            count += 1

    return {"input_path": str(input_file), "output_path": str(output_file), "count": count}


def _build_content(product: dict[str, Any]) -> str:
    lines: list[str] = []
    _add_line(lines, "Sản phẩm", product.get("product_name"))
    _add_line(lines, "Danh mục", product.get("category"))
    _add_price_line(lines, "Giá tham khảo", product.get("price"), product.get("currency"))
    _add_price_line(lines, "Giá gốc", product.get("original_price"), product.get("currency"))
    _add_line(lines, "Thương hiệu", product.get("brand"))
    _add_line(lines, "Mã sản phẩm/SKU", product.get("sku"))
    _add_line(lines, "Chất liệu", product.get("material"))
    _add_line(lines, "Màu sắc", product.get("color"))
    _add_line(lines, "Kích thước", product.get("dimensions"))
    _add_line(lines, "Tình trạng", product.get("availability"))
    _add_line(lines, "Mô tả", product.get("description"))
    _add_line(lines, "Nguồn dữ liệu", product.get("canonical_url") or product.get("source_url"))
    return "\n".join(lines)


def _build_metadata(product: dict[str, Any]) -> dict[str, Any]:
    product_metadata = dict(product.get("metadata") or {})
    return {
        "tenant_id": product.get("tenant_id"),
        "doc_type": "product",
        "product_name": product.get("product_name"),
        "sku": product.get("sku"),
        "category": product.get("category"),
        "price": product.get("price"),
        "original_price": product.get("original_price"),
        "currency": product.get("currency"),
        "brand": product.get("brand"),
        "material": product.get("material"),
        "color": product.get("color"),
        "dimensions": product.get("dimensions"),
        "availability": product.get("availability"),
        "image_urls": list(product.get("image_urls") or []),
        "source_url": product.get("source_url"),
        "canonical_url": product.get("canonical_url"),
        "observed_at": product.get("observed_at"),
        "data_quality": product_metadata.get("data_quality"),
        "extractor": product_metadata.get("extractor"),
        "content_hash": product.get("content_hash"),
        "confidence": product.get("confidence"),
    }


def _stable_id(product: dict[str, Any]) -> str:
    base = product.get("content_hash") or product.get("canonical_url") or product.get("source_url") or product.get("product_name")
    return f"product-{make_content_hash(base)[:16]}"


def _add_line(lines: list[str], label: str, value: Any):
    text = normalize_text(value)
    if text:
        lines.append(f"{label}: {text}.")


def _add_price_line(lines: list[str], label: str, value: Any, currency: Optional[str]):
    if value is None or value == "":
        return
    lines.append(f"{label}: {_format_price(value)} {currency or 'VND'}.")


def _format_price(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}".replace(",", ".")
    return f"{number:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def main(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser(description="Convert product JSONL into RAG-compatible product chunks JSONL.")
    parser.add_argument("--input", required=True, help="Input product JSONL path.")
    parser.add_argument("--output", required=True, help="Output product chunks JSONL path.")
    args = parser.parse_args(argv)

    stats = convert_product_jsonl_to_rag_jsonl(args.input, args.output)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
