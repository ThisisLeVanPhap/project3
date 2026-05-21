"""Extract product links from already-crawled collection source pages.

The script preserves tenant_id and visibility from the source collection row.
Discovered links must still be reviewed before adding them to source_urls.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = PIPELINE_ROOT / "input" / "source_urls.csv"
DEFAULT_RAW_DIR = PIPELINE_ROOT / "raw" / "pages"
DEFAULT_OUTPUT = PIPELINE_ROOT / "output" / "source_urls.discovered.csv"
SOURCE_COLUMNS = ["tenant_id", "store", "source_type", "category", "visibility", "url", "note"]


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs_dict = {key.lower(): value for key, value in attrs if key}
        href = attrs_dict.get("href")
        if href:
            self.hrefs.append(href)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract product links from raw collection HTML files using an optional link filter."
    )
    parser.add_argument("--sources", default=DEFAULT_SOURCES, type=Path, help="Path to source_urls.csv.")
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR, type=Path, help="Directory containing raw HTML/meta files.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path, help="CSV output for discovered product links.")
    parser.add_argument("--link-pattern", default=None, help="Optional substring filter for product links.")
    return parser.parse_args()


def read_collection_sources(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in SOURCE_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"Missing required CSV columns: {', '.join(missing)}")
        return [
            normalize_row(row)
            for row in reader
            if (row.get("url") or "").strip()
            and (row.get("source_type") or "").strip().lower() == "collection"
        ]


def normalize_row(row):
    normalized = {column: (row.get(column) or "").strip() for column in SOURCE_COLUMNS}
    normalized["source_type"] = normalized["source_type"].lower()
    normalized["visibility"] = normalized["visibility"].lower()
    return normalized


def load_raw_pages(raw_dir):
    pages = []
    for html_path in sorted(raw_dir.glob("*.html")):
        meta_path = html_path.with_suffix(".meta.json")
        metadata = {}
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        pages.append((html_path, metadata, html_path.read_text(encoding="utf-8", errors="replace")))
    return pages


def find_matching_page(collection, pages):
    target_url = (collection.get("url") or "").strip()
    for html_path, metadata, html in pages:
        if (metadata.get("url") or "").strip() == target_url:
            return html_path, metadata, html
    return None


def extract_links(html, base_url, pattern):
    parser = LinkParser()
    parser.feed(html or "")
    pattern = (pattern or "").strip()
    links = []
    seen = set()
    for href in parser.hrefs:
        absolute = urljoin(base_url, href)
        if pattern and pattern not in absolute:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
    return links


def write_output(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    collections = read_collection_sources(args.sources)
    pages = load_raw_pages(args.raw_dir)
    discovered = []

    for collection in collections:
        match = find_matching_page(collection, pages)
        if not match:
            print(f"WARN no raw page found for collection: {collection.get('url')}")
            continue
        _, _, html = match
        links = extract_links(html, collection.get("url"), args.link_pattern)
        for link in links:
            discovered.append(
                {
                    "tenant_id": collection.get("tenant_id") or "",
                    "store": collection.get("store") or "",
                    "source_type": "product",
                    "category": collection.get("category") or "",
                    "visibility": collection.get("visibility") or "",
                    "url": link,
                    "note": f"discovered from {collection.get('url')}",
                }
            )

    write_output(args.output, discovered)
    print(f"Wrote {len(discovered)} discovered link(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
