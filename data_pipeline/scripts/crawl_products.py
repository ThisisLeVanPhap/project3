"""Fetch source pages listed in input/source_urls.csv.

The default mode is dry-run. Pass --execute to perform HTTP requests.
This crawler does not call any LLM or chatbot runtime API.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PIPELINE_ROOT / "input" / "source_urls.csv"
DEFAULT_OUTPUT_DIR = PIPELINE_ROOT / "raw" / "pages"
REQUIRED_COLUMNS = ["tenant_id", "store", "source_type", "category", "visibility", "url", "note"]
ALLOWED_VISIBILITY = {"tenant_private", "tenant_public", "public_reference"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Crawl catalog source URLs into raw HTML files without calling any LLM API."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, type=Path, help="Path to source_urls.csv.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, type=Path, help="Raw page output directory.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of rows to process.")
    parser.add_argument("--execute", action="store_true", help="Actually fetch URLs. Default is dry-run.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds.")
    parser.add_argument("--user-agent", default="CatalogDataPipeline/0.1", help="HTTP User-Agent header.")
    return parser.parse_args()


def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_header(reader.fieldnames or [])
        rows = [normalize_row(row) for row in reader if (row.get("url") or "").strip()]
        validate_rows(rows)
        return rows


def validate_header(fieldnames):
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise SystemExit(f"Missing required CSV columns: {', '.join(missing)}")


def normalize_row(row):
    normalized = {column: (row.get(column) or "").strip() for column in REQUIRED_COLUMNS}
    normalized["visibility"] = normalized["visibility"].lower()
    normalized["source_type"] = normalized["source_type"].lower()
    return normalized


def validate_rows(rows):
    errors = []
    for index, row in enumerate(rows, start=2):
        visibility = row.get("visibility")
        if visibility not in ALLOWED_VISIBILITY:
            errors.append(
                f"line {index}: visibility must be one of {', '.join(sorted(ALLOWED_VISIBILITY))}"
            )
        if visibility in {"tenant_private", "tenant_public"} and not row.get("tenant_id"):
            errors.append(f"line {index}: tenant_id is required for {visibility}")
        if visibility == "public_reference" and row.get("tenant_id"):
            errors.append(f"line {index}: tenant_id must be empty for public_reference")
    if errors:
        raise SystemExit("\n".join(errors))


def page_stem(row, index):
    visibility = clean_part(row.get("visibility") or "unknown")
    tenant = clean_part(row.get("tenant_id") or "public")
    store = clean_part(row.get("store") or "unknown")
    category = clean_part(row.get("category") or "uncategorized")
    digest = hashlib.sha1((row.get("url") or "").encode("utf-8")).hexdigest()[:12]
    return f"{index:05d}_{visibility}_{tenant}_{store}_{category}_{digest}"


def clean_part(value):
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:60] or "unknown"


def fetch_url(url, timeout, user_agent):
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return {
            "status": response.status,
            "headers": dict(response.headers.items()),
            "html": body.decode(charset, errors="replace"),
        }


def write_raw(output_dir, stem, row, fetch_result):
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{stem}.html"
    meta_path = output_dir / f"{stem}.meta.json"

    html_path.write_text(fetch_result["html"], encoding="utf-8")
    metadata = {
        "tenant_id": row.get("tenant_id") or None,
        "store": row.get("store") or None,
        "source_type": row.get("source_type") or None,
        "category": row.get("category") or None,
        "visibility": row.get("visibility") or None,
        "url": row.get("url") or None,
        "note": row.get("note") or None,
        "status": fetch_result.get("status"),
        "headers": fetch_result.get("headers", {}),
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "raw_path": str(html_path),
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return html_path, meta_path


def main():
    args = parse_args()
    rows = read_rows(args.input)
    if args.limit is not None:
        rows = rows[: args.limit]

    if not args.execute:
        print(f"Dry-run: {len(rows)} source URL(s) would be crawled.")
        print("Pass --execute to fetch pages. Use --limit for cautious batches.")
        return 0

    successes = 0
    failures = 0
    for index, row in enumerate(rows, start=1):
        url = (row.get("url") or "").strip()
        stem = page_stem(row, index)
        try:
            result = fetch_url(url, timeout=args.timeout, user_agent=args.user_agent)
            html_path, _ = write_raw(args.output_dir, stem, row, result)
            successes += 1
            print(f"OK {url} -> {html_path}")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            failures += 1
            print(f"ERROR {url}: {exc}")

    print(f"Done. successes={successes} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
