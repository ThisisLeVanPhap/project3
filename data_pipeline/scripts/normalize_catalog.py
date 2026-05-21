"""Normalize raw product HTML pages into tenant/reference output folders."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from parsers import get_parser  # noqa: E402


DEFAULT_RAW_DIR = PIPELINE_ROOT / "raw" / "pages"
DEFAULT_OUTPUT_ROOT = PIPELINE_ROOT / "output"
TENANT_VISIBILITY = {"tenant_private", "tenant_public"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Normalize raw HTML pages into isolated tenant or public reference catalog files."
    )
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR, type=Path, help="Directory containing .html and .meta.json files.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, type=Path, help="Root output directory.")
    return parser.parse_args()


def iter_raw_pages(raw_dir):
    for html_path in sorted(raw_dir.glob("*.html")):
        meta_path = html_path.with_suffix(".meta.json")
        metadata = {}
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        metadata.setdefault("raw_path", str(html_path))
        html = html_path.read_text(encoding="utf-8", errors="replace")
        yield html_path, metadata, html


def normalize(raw_dir):
    for _, metadata, html in iter_raw_pages(raw_dir):
        parser = get_parser(metadata.get("store"))
        product = parser(html, metadata)
        yield product


def output_path_for(product, output_root):
    visibility = product.get("visibility")
    if visibility == "public_reference":
        if product.get("tenant_id"):
            raise ValueError("public_reference records must not carry tenant_id")
        return output_root / "reference" / "products.clean.jsonl"

    if visibility in TENANT_VISIBILITY:
        tenant_id = product.get("tenant_id")
        if not tenant_id:
            raise ValueError(f"tenant_id is required for {visibility} records")
        return output_root / "tenants" / safe_path_part(tenant_id) / "products.clean.jsonl"

    raise ValueError(f"unknown visibility: {visibility!r}")


def safe_path_part(value):
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in str(value).strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    if not cleaned:
        raise ValueError("empty path segment")
    return cleaned


def write_records(records, output_root):
    handles = {}
    counts = {}
    try:
        for product in records:
            path = output_path_for(product, output_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path not in handles:
                handles[path] = path.open("w", encoding="utf-8")
                counts[path] = 0
            handles[path].write(json.dumps(product, ensure_ascii=False) + "\n")
            counts[path] += 1
    finally:
        for handle in handles.values():
            handle.close()
    return counts


def main():
    args = parse_args()
    counts = write_records(normalize(args.raw_dir), args.output_root)
    total = sum(counts.values())
    print(f"Wrote {total} product record(s).")
    for path, count in sorted(counts.items()):
        print(f"- {path}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
