import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

MOJIBAKE_RE = re.compile(r"(RÃ|Ã|á»|áº|Ä|Æ|�|cá»|gá»|tháº|sáº|ná»)")
FAIL = "fail"
WARN = "warn"
PASS = "pass"


def has_mojibake(value: Any) -> bool:
    return bool(value and MOJIBAKE_RE.search(str(value)))


def audit_product_dataset(dataset_dir: str | Path, output_path: str | Path | None = None, write_report: bool = True) -> dict[str, Any]:
    dataset_path = Path(dataset_dir)
    manifest_path = dataset_path / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest.json not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))

    catalog_path = _manifest_file(dataset_path, manifest, "catalog", "catalog.jsonl")
    rag_path = _manifest_file(dataset_path, manifest, "rag_products", "rag_products.jsonl")
    catalog_rows = _read_jsonl(catalog_path) if catalog_path.is_file() else []
    rag_rows = _read_jsonl(rag_path) if rag_path.is_file() else []

    product_manifest = _int_or_none(manifest.get("product_count"))
    rag_manifest = _int_or_none(manifest.get("rag_chunk_count"))
    product_actual = len(catalog_rows) if catalog_rows else None
    rag_actual = len(rag_rows)
    products_for_quality = catalog_rows or [_catalog_like_from_rag(row) for row in rag_rows]

    duplicate_url_count = _duplicate_url_count(products_for_quality)
    title_mojibake = sum(1 for row in products_for_quality if has_mojibake(row.get("product_name")))
    rag_title_mojibake = sum(1 for row in rag_rows if has_mojibake(row.get("title")))
    rag_text_mojibake = sum(1 for row in rag_rows if has_mojibake(row.get("text")) or has_mojibake(row.get("content")))
    suspicious = [item for item in (_suspicious_category(row) for row in products_for_quality) if item]
    crawl_report_row_count = _crawl_report_row_count(dataset_path / "crawl_report.json")
    stale_report = crawl_report_row_count is not None and crawl_report_row_count not in {product_actual, rag_actual}

    price_count = _count_non_empty(products_for_quality, "price")
    material_count = _count_non_empty(products_for_quality, "material")
    dimensions_count = _count_non_empty(products_for_quality, "dimensions")
    denominator = len(products_for_quality) or 0
    duplicate_ratio = duplicate_url_count / denominator if denominator else 0.0
    suspicious_ratio = len(suspicious) / denominator if denominator else 0.0

    reasons: list[str] = []
    warnings: list[str] = []
    if product_actual is not None and product_manifest is not None and product_manifest != product_actual:
        reasons.append(f"manifest product_count {product_manifest} != catalog rows {product_actual}")
    if rag_manifest is not None and rag_manifest != rag_actual:
        reasons.append(f"manifest rag_chunk_count {rag_manifest} != rag rows {rag_actual}")
    if title_mojibake:
        reasons.append(f"product title mojibake count {title_mojibake}")
    if rag_title_mojibake:
        reasons.append(f"RAG title mojibake count {rag_title_mojibake}")
    if duplicate_ratio > 0.02:
        reasons.append(f"duplicate URL ratio {duplicate_ratio:.2%} > 2%")
    if denominator and price_count / denominator < 0.80:
        reasons.append(f"price coverage {price_count / denominator:.2%} < 80%")

    if rag_text_mojibake:
        warnings.append(f"RAG text mojibake count {rag_text_mojibake}")
    if stale_report:
        warnings.append(f"crawl_report row_count {crawl_report_row_count} does not match dataset rows")
    if denominator and material_count / denominator < 0.50:
        warnings.append(f"material coverage {material_count / denominator:.2%} < 50%")
    if denominator and dimensions_count / denominator < 0.50:
        warnings.append(f"dimensions coverage {dimensions_count / denominator:.2%} < 50%")
    if suspicious_ratio > 0.05:
        warnings.append(f"suspicious category ratio {suspicious_ratio:.2%} > 5%")
    if product_actual is None:
        warnings.append("catalog.jsonl not found; product coverage uses rag metadata")

    status = FAIL if reasons else (WARN if warnings else PASS)
    report = {
        "dataset_id": manifest.get("dataset_id") or dataset_path.name,
        "product_count_manifest": product_manifest,
        "product_count_actual": product_actual,
        "rag_chunk_count_manifest": rag_manifest,
        "rag_chunk_count_actual": rag_actual,
        "title_mojibake_count": title_mojibake,
        "rag_title_mojibake_count": rag_title_mojibake,
        "rag_text_mojibake_count": rag_text_mojibake,
        "price_count": price_count,
        "price_coverage": _coverage(price_count, denominator),
        "material_count": material_count,
        "material_coverage": _coverage(material_count, denominator),
        "dimensions_count": dimensions_count,
        "dimensions_coverage": _coverage(dimensions_count, denominator),
        "duplicate_url_count": duplicate_url_count,
        "duplicate_url_ratio": duplicate_ratio,
        "suspicious_category_count": len(suspicious),
        "suspicious_category_ratio": suspicious_ratio,
        "stale_report": stale_report,
        "crawl_report_row_count": crawl_report_row_count,
        "sample_bad_rows": _sample_bad_rows(products_for_quality, rag_rows, suspicious),
        "status": status,
        "reasons": reasons + warnings,
        "fail_reasons": reasons,
        "warnings": warnings,
    }
    if write_report:
        target = Path(output_path) if output_path else dataset_path / "quality_audit.json"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["quality_audit_path"] = str(target)
    return report


def _manifest_file(dataset_dir: Path, manifest: dict[str, Any], key: str, fallback: str) -> Path:
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    return dataset_dir / str(files.get(key) or fallback)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _catalog_like_from_rag(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return {
        "product_name": metadata.get("product_name") or row.get("title"),
        "price": metadata.get("price"),
        "material": metadata.get("material"),
        "dimensions": metadata.get("dimensions"),
        "category": metadata.get("category"),
        "source_url": metadata.get("source_url") or metadata.get("canonical_url") or row.get("url") or row.get("source"),
    }


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _count_non_empty(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if row.get(field) not in (None, "", [], {}))


def _coverage(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def _normalize_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return text.rstrip("/")
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def _row_url(row: dict[str, Any]) -> str:
    return str(row.get("canonical_url") or row.get("source_url") or row.get("url") or "")


def _duplicate_url_count(rows: list[dict[str, Any]]) -> int:
    keys = [_normalize_url(_row_url(row)) for row in rows if _normalize_url(_row_url(row))]
    counts = Counter(keys)
    return sum(count - 1 for count in counts.values() if count > 1)


def _crawl_report_row_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    value = report.get("row_count")
    if isinstance(value, int):
        return value
    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    extracted = counts.get("extracted_count")
    return extracted if isinstance(extracted, int) else None


def _fold(value: Any) -> str:
    text = str(value or "").lower()
    replacements = {
        "ủ": "u", "ũ": "u", "ụ": "u", "ư": "u", "ứ": "u", "ừ": "u", "ử": "u", "ữ": "u", "ự": "u",
        "ù": "u", "ú": "u", "ô": "o", "ố": "o", "ồ": "o", "ổ": "o", "ỗ": "o", "ộ": "o", "ơ": "o", "ớ": "o", "ờ": "o", "ở": "o", "ỡ": "o", "ợ": "o", "ò": "o", "ó": "o", "ỏ": "o", "õ": "o", "ọ": "o",
        "à": "a", "á": "a", "ả": "a", "ã": "a", "ạ": "a", "ă": "a", "ắ": "a", "ằ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a", "â": "a", "ấ": "a", "ầ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
        "è": "e", "é": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e", "ê": "e", "ế": "e", "ề": "e", "ể": "e", "ễ": "e", "ệ": "e",
        "ì": "i", "í": "i", "ỉ": "i", "ĩ": "i", "ị": "i", "ỳ": "y", "ý": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y", "đ": "d",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _suspicious_category(row: dict[str, Any]) -> dict[str, Any] | None:
    category = str(row.get("category") or "").strip()
    title = str(row.get("product_name") or "")
    url = _row_url(row)
    title_folded = _fold(title)
    url_folded = _fold(url)
    rules = [
        (_has_tu_signal(title, url_folded), "Tủ"),
        ("sofa" in title_folded or "sofa" in url_folded, "Sofa"),
        ("giuong" in title_folded or "giuong" in url_folded, "Giường"),
        (_has_rem_signal(title_folded, url_folded), "Rèm"),
        ("ban lam viec" in title_folded or "ban-lam-viec" in url_folded, "Bàn làm việc"),
        (_has_ke_signal(title, url_folded), "Kệ"),
    ]
    for matched, expected in rules:
        if matched and category != expected:
            return {
                "title": row.get("product_name"),
                "category": category,
                "expected_category": expected,
                "url": url,
            }
    return None


def _has_tu_signal(title: str, url_folded: str) -> bool:
    title_lower = title.lower()
    slug = _slug(url_folded)
    return (
        re.search(r"\btủ\b", title_lower) is not None
        or slug.startswith("tu-")
        or "-tu-quan-ao" in slug
        or "-tu-de-do" in slug
        or "-tu-bep" in slug
    )


def _has_rem_signal(title_folded: str, url_folded: str) -> bool:
    slug = _slug(url_folded)
    return re.search(r"\brem\b", title_folded) is not None or slug.startswith("rem-") or "-rem-" in slug


def _has_ke_signal(title: str, url_folded: str) -> bool:
    title_lower = title.lower()
    slug = _slug(url_folded)
    return re.search(r"\bkệ\b", title_lower) is not None or slug.startswith("ke-")


def _slug(url_folded: str) -> str:
    return urlsplit(url_folded).path.strip("/").split("/")[-1]


def _sample_bad_rows(products: list[dict[str, Any]], rag_rows: list[dict[str, Any]], suspicious: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for row in products:
        if has_mojibake(row.get("product_name")):
            samples.append({"type": "title_mojibake", "title": row.get("product_name"), "url": _row_url(row)})
            if len(samples) >= 20:
                return samples
    for row in rag_rows:
        if has_mojibake(row.get("title")) or has_mojibake(row.get("text")) or has_mojibake(row.get("content")):
            samples.append({"type": "rag_mojibake", "title": row.get("title"), "url": row.get("url") or row.get("source")})
            if len(samples) >= 20:
                return samples
    for item in suspicious[:20 - len(samples)]:
        samples.append({"type": "suspicious_category", **item})
    return samples
