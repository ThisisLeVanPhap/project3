import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit


QUALITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}
URL_FIELDS = ("source_url", "canonical_url", "url")


def normalize_product_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return text.rstrip("/")
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def get_product_record_key(record: dict[str, Any]) -> Optional[str]:
    for field in ("canonical_url", "source_url", "url"):
        key = normalize_product_url(record.get(field))
        if key:
            return key
    return None


def score_product_record_completeness(record: dict[str, Any]) -> tuple[int, int, int, float]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    quality_rank = QUALITY_RANK.get(str(metadata.get("data_quality") or "").lower(), 0)
    non_empty_fields = sum(1 for value in record.values() if _is_non_empty(value))
    image_count = len(record.get("image_urls") or []) if isinstance(record.get("image_urls"), list) else 0
    observed_ts = _parse_observed_at(record.get("observed_at"))
    return (quality_rank, non_empty_fields, image_count, observed_ts)


def audit_product_jsonl(path: str | Path, sample_limit: int = 10) -> dict[str, Any]:
    records = _read_jsonl_records(path)
    source_keys = [normalize_product_url(record.get("source_url")) for _, record in records if record.get("source_url")]
    canonical_keys = [normalize_product_url(record.get("canonical_url")) for _, record in records if record.get("canonical_url")]
    normalized_keys = [get_product_record_key(record) for _, record in records if get_product_record_key(record)]
    sku_values = [str(record.get("sku") or "").strip() for _, record in records if str(record.get("sku") or "").strip()]
    hash_values = [
        str(record.get("content_hash") or "").strip()
        for _, record in records
        if str(record.get("content_hash") or "").strip()
    ]

    groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for line_no, record in records:
        key = get_product_record_key(record)
        if key:
            groups[key].append((line_no, record))
    duplicate_groups = {key: items for key, items in groups.items() if len(items) > 1}

    return {
        "total_lines": len(records),
        "unique_by_source_url": len(set(source_keys)),
        "unique_by_canonical_url": len(set(canonical_keys)),
        "unique_by_normalized_url": len(set(normalized_keys)),
        "duplicate_by_normalized_url_count": len(duplicate_groups),
        "duplicate_by_sku_count": _duplicate_group_count(sku_values),
        "duplicate_by_content_hash_count": _duplicate_group_count(hash_values),
        "sample_duplicate_groups": _sample_duplicate_groups(duplicate_groups, sample_limit=sample_limit),
        "cause_hints": _classify_duplicate_causes(duplicate_groups),
    }


def dedupe_product_jsonl(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    records = _read_jsonl_records(input_path)
    order: list[str] = []
    selected: dict[str, tuple[int, dict[str, Any]]] = {}
    duplicate_groups: set[str] = set()

    for line_no, record in records:
        key = get_product_record_key(record) or f"__missing_url__:{line_no}"
        if key not in selected:
            order.append(key)
            selected[key] = (line_no, record)
            continue
        duplicate_groups.add(key)
        if _is_better_record(line_no, record, selected[key]):
            selected[key] = (line_no, record)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for key in order:
            _, record = selected[key]
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "input_lines": len(records),
        "output_lines": len(order),
        "removed_duplicates": len(records) - len(order),
        "unique_url_count": len([key for key in order if not key.startswith("__missing_url__:")]),
        "duplicate_groups_count": len(duplicate_groups),
        "output_path": str(output),
    }


def _read_jsonl_records(path: str | Path) -> list[tuple[int, dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            records.append((line_no, json.loads(line)))
    return records


def _is_better_record(line_no: int, record: dict[str, Any], current: tuple[int, dict[str, Any]]) -> bool:
    current_line_no, current_record = current
    score = score_product_record_completeness(record)
    current_score = score_product_record_completeness(current_record)
    if score != current_score:
        return score > current_score
    return line_no < current_line_no


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _parse_observed_at(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _duplicate_group_count(values: list[str]) -> int:
    counts = Counter(values)
    return sum(1 for count in counts.values() if count > 1)


def _sample_duplicate_groups(
    duplicate_groups: dict[str, list[tuple[int, dict[str, Any]]]],
    sample_limit: int,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for key, items in list(duplicate_groups.items())[:sample_limit]:
        samples.append(
            {
                "normalized_url": key,
                "count": len(items),
                "records": [_record_summary(line_no, record) for line_no, record in items[:5]],
            }
        )
    return samples


def _record_summary(line_no: int, record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return {
        "line": line_no,
        "product_name": record.get("product_name"),
        "sku": record.get("sku"),
        "price": record.get("price"),
        "source_url": record.get("source_url"),
        "canonical_url": record.get("canonical_url"),
        "observed_at": record.get("observed_at"),
        "content_hash": record.get("content_hash"),
        "data_quality": metadata.get("data_quality"),
    }


def _classify_duplicate_causes(duplicate_groups: dict[str, list[tuple[int, dict[str, Any]]]]) -> dict[str, int]:
    same_hash = 0
    different_hash = 0
    trailing_slash_variant = 0
    for items in duplicate_groups.values():
        hashes = {str(record.get("content_hash") or "") for _, record in items}
        raw_urls = [
            str(record.get("canonical_url") or record.get("source_url") or record.get("url") or "")
            for _, record in items
        ]
        if len(hashes) == 1:
            same_hash += 1
        else:
            different_hash += 1
        if len(set(raw_urls)) > 1 and len({url.rstrip("/") for url in raw_urls}) == 1:
            trailing_slash_variant += 1
    return {
        "same_normalized_url_same_content_hash_groups": same_hash,
        "same_normalized_url_diff_content_hash_groups": different_hash,
        "trailing_slash_variant_groups": trailing_slash_variant,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and dedupe product JSONL output.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    audit = audit_product_jsonl(args.input)
    print(json.dumps({"audit": audit}, ensure_ascii=False, indent=2))
    if args.audit_only:
        return
    if not args.output:
        raise SystemExit("--output is required unless --audit-only is set")
    report = dedupe_product_jsonl(args.input, args.output)
    print(json.dumps({"dedupe": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
