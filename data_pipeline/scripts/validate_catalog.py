"""Validate a products.clean.jsonl file and write catalog_report.md."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PIPELINE_ROOT / "output" / "reference" / "products.clean.jsonl"
DEFAULT_REPORT = PIPELINE_ROOT / "output" / "reference" / "catalog_report.md"
ALLOWED_VISIBILITY = {"tenant_private", "tenant_public", "public_reference"}
REQUIRED_FIELDS = [
    "tenant_id",
    "store",
    "category",
    "source_type",
    "visibility",
    "source_url",
    "product_id",
    "name",
    "brand",
    "sku",
    "price",
    "currency",
    "sale_price",
    "availability",
    "description",
    "attributes",
    "images",
    "crawled_at",
    "raw_path",
]
IMPORTANT_FIELDS = ["store", "category", "source_url", "name", "price", "currency"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate clean product JSONL and produce a markdown catalog report."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, type=Path, help="Path to products.clean.jsonl.")
    parser.add_argument("--report", default=DEFAULT_REPORT, type=Path, help="Path to catalog_report.md.")
    return parser.parse_args()


def read_jsonl(path):
    records = []
    errors = []
    if not path.exists():
        return records, [f"Input file not found: {path}"]

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {line_number}: invalid JSON ({exc})")
                continue
            if not isinstance(record, dict):
                errors.append(f"Line {line_number}: record is not a JSON object")
                continue
            records.append((line_number, record))
    return records, errors


def validate_records(records, input_path):
    errors = []
    warnings = []
    store_counts = Counter()
    category_counts = Counter()
    visibility_counts = Counter()
    null_counts = Counter()
    urls = Counter()

    for line_number, record in records:
        missing_fields = [field for field in REQUIRED_FIELDS if field not in record]
        if missing_fields:
            errors.append(f"Line {line_number}: missing fields: {', '.join(missing_fields)}")

        for field in IMPORTANT_FIELDS:
            if is_missing(record.get(field)):
                null_counts[field] += 1

        visibility = record.get("visibility")
        visibility_counts[visibility or "null"] += 1
        validate_visibility(line_number, record, input_path, errors)

        store_counts[record.get("store") or "null"] += 1
        category_counts[record.get("category") or "null"] += 1
        source_url = record.get("source_url")
        if source_url:
            urls[source_url] += 1

        if record.get("price") is not None and not isinstance(record.get("price"), (int, float)):
            warnings.append(f"Line {line_number}: price is not numeric")
        if record.get("images") is not None and not isinstance(record.get("images"), list):
            warnings.append(f"Line {line_number}: images is not a list")
        if record.get("attributes") is not None and not isinstance(record.get("attributes"), dict):
            warnings.append(f"Line {line_number}: attributes is not an object")

    duplicate_urls = {url: count for url, count in urls.items() if count > 1}
    for url, count in duplicate_urls.items():
        warnings.append(f"Duplicate source_url appears {count} times: {url}")

    return {
        "errors": errors,
        "warnings": warnings,
        "store_counts": store_counts,
        "category_counts": category_counts,
        "visibility_counts": visibility_counts,
        "null_counts": null_counts,
        "duplicate_urls": duplicate_urls,
    }


def validate_visibility(line_number, record, input_path, errors):
    visibility = record.get("visibility")
    tenant_id = record.get("tenant_id")
    if visibility not in ALLOWED_VISIBILITY:
        errors.append(f"Line {line_number}: invalid visibility: {visibility!r}")
        return

    if visibility in {"tenant_private", "tenant_public"} and is_missing(tenant_id):
        errors.append(f"Line {line_number}: tenant_id is required for {visibility}")
    if visibility == "public_reference" and not is_missing(tenant_id):
        errors.append(f"Line {line_number}: tenant_id must be null for public_reference")

    parts = [part.lower() for part in input_path.parts]
    if "reference" in parts and visibility != "public_reference":
        errors.append(f"Line {line_number}: reference output may only contain public_reference")
    if "tenants" in parts:
        if visibility == "public_reference":
            errors.append(f"Line {line_number}: tenant output must not contain public_reference")
        tenant_from_path = tenant_id_from_path(input_path)
        if tenant_from_path and safe_path_part(tenant_id or "") != tenant_from_path:
            errors.append(f"Line {line_number}: tenant_id does not match tenant output folder")


def tenant_id_from_path(path):
    parts = [part.lower() for part in path.parts]
    if "tenants" not in parts:
        return None
    index = parts.index("tenants")
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def safe_path_part(value):
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in str(value).strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned


def is_missing(value):
    return value is None or value == "" or value == [] or value == {}


def markdown_table(counter, key_label, value_label):
    if not counter:
        return "_No data._\n"
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items()):
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines) + "\n"


def write_report(path, input_path, records, result, read_errors):
    path.parent.mkdir(parents=True, exist_ok=True)
    total = len(records)
    lines = [
        "# Catalog Report",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Input: `{input_path}`",
        f"- Total records: {total}",
        f"- Errors: {len(read_errors) + len(result['errors'])}",
        f"- Warnings: {len(result['warnings'])}",
        "",
        "## Missing Important Fields",
        "",
        markdown_table(result["null_counts"], "field", "missing_records"),
        "## Records By Visibility",
        "",
        markdown_table(result["visibility_counts"], "visibility", "records"),
        "## Records By Store",
        "",
        markdown_table(result["store_counts"], "store", "records"),
        "## Records By Category",
        "",
        markdown_table(result["category_counts"], "category", "records"),
        "## Errors",
        "",
    ]
    all_errors = read_errors + result["errors"]
    lines.extend(format_list(all_errors))
    lines.extend(["", "## Warnings", ""])
    lines.extend(format_list(result["warnings"]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_list(items):
    if not items:
        return ["_None._"]
    return [f"- {item}" for item in items]


def main():
    args = parse_args()
    records, read_errors = read_jsonl(args.input)
    result = validate_records(records, args.input)
    write_report(args.report, args.input, records, result, read_errors)
    print(f"Wrote catalog report to {args.report}")
    return 1 if read_errors or result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
