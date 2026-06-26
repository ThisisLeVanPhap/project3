"""
crawl_and_materialize_dataset.py

Phase X1A: Crawl product URLs from sitemap, materialize into a Product Dataset
folder, run quality audit, optional taxonomy normalize, and output manifest/JSON
for the Java backend to auto-register as a ProductDataset.

Does NOT bind tenant, import General, or build artifact (those are subsequent steps).
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

ROOT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_pipeline.crawling.adapters.gotrangtri import GoTrangTriAdapter
from data_pipeline.crawling.adapters.mhome import MHomeAdapter
from data_pipeline.crawling.adapters.moho import MohoAdapter
from data_pipeline.crawling.discovery.sitemap import SitemapProductUrlDiscoverer
from data_pipeline.crawling.job import ProductCrawlJob
from data_pipeline.crawling.source_config import CrawlSource
from data_pipeline.crawling.dedupe_output import dedupe_product_jsonl
from data_pipeline.crawling.taxonomy_normalize import normalize_dataset_taxonomy
from tools.materialize_product_dataset import materialize_product_dataset


PRODUCT_SITEMAP_PATTERNS = [
    "/shop/", "/product/", "/products/", "/san-pham/",
    "product-sitemap", "sitemap_products", "sitemap-product",
]
NON_PRODUCT_PATTERNS = [
    "/blog/", "/page/", "/collection/", "/category/", "/tag/",
    "/about", "/contact", "/news/", "/tin-tuc/",
]

KNOWN_ADAPTERS: dict[str, Any] = {
    "gotrangtri": GoTrangTriAdapter(),
    "moho": MohoAdapter(),
    "mhome": MHomeAdapter(),
}

PROVIDER_ALIASES: dict[str, str] = {
    "mhomefurniture": "mhome",
    "mhomefurniture.vn": "mhome",
    "moho.com.vn": "moho",
    "gotrangtri.vn": "gotrangtri",
}

DEFAULT_MAX_URLS = 1000
MAX_URLS_LIMIT = 10000


def resolve_provider(source_code: str, root_url: str) -> str:
    code = source_code.strip().lower() if source_code else ""
    if code in KNOWN_ADAPTERS:
        return code
    if code in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[code]
    host = urlsplit(root_url).netloc.lower().removeprefix("www.") if root_url else ""
    if host in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[host]
    if host in ("gotrangtri.vn",):
        return "gotrangtri"
    if host in ("moho.com.vn",):
        return "moho"
    if host in ("mhomefurniture.vn",):
        return "mhome"
    return code if code else host.split(".")[0] if host else ""


def infer_product_patterns(root_url: str) -> list[str]:
    host = urlsplit(root_url).netloc.lower()
    combined = f"{host} {root_url}"
    for pattern_list, provider in [(["/shop/", "/san-pham/"], None)]:
        for p in pattern_list:
            if p in combined:
                return [p]
    return PRODUCT_SITEMAP_PATTERNS[:2]


def infer_allowed_domains(root_url: str) -> list[str]:
    host = urlsplit(root_url).netloc.lower()
    return [host, f"www.{host}"] if not host.startswith("www.") else [host]


def discover_urls(
    sitemap_url: str,
    max_urls: int,
    product_only: bool,
    root_url: str,
) -> list[str]:
    product_patterns = infer_product_patterns(root_url) if product_only else []
    exclude = NON_PRODUCT_PATTERNS if product_only else []
    allowed = infer_allowed_domains(root_url)
    max_urls = min(max_urls or DEFAULT_MAX_URLS, MAX_URLS_LIMIT)
    discoverer = SitemapProductUrlDiscoverer(max_sitemaps=MAX_URLS_LIMIT)
    return discoverer.discover(
        sitemap_url=sitemap_url,
        product_url_patterns=product_patterns,
        max_urls=max_urls,
        allowed_domains=allowed,
        exclude_patterns=exclude,
    )


def build_crawl_source(
    start_urls: list[str],
    provider: str,
    source_code: str,
    tenant_id: Optional[str],
    output_path: str,
) -> CrawlSource:
    adapter = KNOWN_ADAPTERS.get(provider)
    if adapter is not None:
        return adapter.build_source(
            start_urls=start_urls,
            tenant_id=tenant_id,
            output_path=output_path,
        )
    return CrawlSource(
        name=source_code,
        tenant_id=tenant_id,
        start_urls=list(start_urls),
        allowed_domains=infer_allowed_domains(start_urls[0]) if start_urls else [],
        output_path=output_path,
        max_pages=len(start_urls),
    )


def ensure_output_dir(output_dir: str | Path) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def crawl_and_materialize(
    sitemap_url: Optional[str],
    product_urls: Optional[list[str]],
    dataset_id: str,
    source_code: str,
    root_url: str,
    max_urls: int = DEFAULT_MAX_URLS,
    product_only: bool = True,
    run_quality_audit: bool = True,
    run_dedupe: bool = True,
    run_taxonomy_normalize: bool = False,
    output_dataset_dir: Optional[str] = None,
    source_name: Optional[str] = None,
) -> dict[str, Any]:
    max_urls = min(max_urls or DEFAULT_MAX_URLS, MAX_URLS_LIMIT)
    provider = resolve_provider(source_code, root_url)

    # 1. Discover URLs — use adapter's discover if available
    start_urls: list[str] = []
    if sitemap_url:
        adapter = KNOWN_ADAPTERS.get(provider)
        if adapter is not None and hasattr(adapter, 'discover_product_urls'):
            start_urls = adapter.discover_product_urls(
                sitemap_url=sitemap_url,
                max_urls=max_urls,
            )
        else:
            start_urls = discover_urls(sitemap_url, max_urls, product_only, root_url)
    if product_urls:
        existing = set(start_urls)
        for u in product_urls:
            u = u.strip()
            if u and u not in existing:
                existing.add(u)
                start_urls.append(u)
    if not start_urls:
        return {"success": False, "error": "No URLs discovered or provided", "dataset_id": dataset_id}

    # 2. Determine output paths
    if output_dataset_dir:
        dataset_dir = ensure_output_dir(output_dataset_dir)
    else:
        dataset_dir = ensure_output_dir(REPO_ROOT / "data_pipeline" / "output" / "datasets" / dataset_id)
    crawled_output = dataset_dir / "crawl_temp_products.jsonl"
    temp_root = tempfile.mkdtemp(prefix="crawl-temp-")
    temp_output = Path(temp_root) / "products.jsonl"

    # 3. Build crawl source and crawl
    source = build_crawl_source(
        start_urls=start_urls,
        provider=provider,
        source_code=source_code,
        tenant_id=None,
        output_path=str(temp_output),
    )
    crawl_result = ProductCrawlJob(source).run()

    # 4. Dedupe crawled products (if requested)
    dedupe_result = None
    if run_dedupe:
        dedupe_products = Path(temp_root) / "deduped_products.jsonl"
        dedupe_result = dedupe_product_jsonl(str(temp_output), str(dedupe_products))
        temp_output = dedupe_products
        pass

    # 5. Materialize dataset folder
    materialize_result = materialize_product_dataset(
        input_path=temp_output,
        output_dir=dataset_dir,
        dataset_id=dataset_id,
        source=source_code,
        source_url=root_url or sitemap_url,
        overwrite=True,
    )

    # 5. Taxonomy normalize (if requested and applicable)
    taxonomy_result = None
    if run_taxonomy_normalize:
        try:
            taxonomy_result = normalize_dataset_taxonomy(
                dataset_dir=dataset_dir,
                apply=True,
                backup=True,
                source=provider,
            )
        except Exception as exc:
            taxonomy_result = {"error": str(exc), "applied_count": 0, "change_count": 0}

    # Build response
    quality_status = materialize_result.get("quality_status", "pass")
    quality_reasons = materialize_result.get("quality_reasons", [])
    result: dict[str, Any] = {
        "success": True,
        "dataset_id": dataset_id,
        "dataset_dir": str(dataset_dir),
        "manifest_path": str(dataset_dir / "manifest.json"),
        "quality_audit_path": str(dataset_dir / "quality_audit.json"),
        "product_count": materialize_result.get("product_count", 0),
        "rag_chunk_count": materialize_result.get("rag_chunk_count", 0),
        "quality_status": quality_status,
        "quality_reasons": quality_reasons,
        "source_code": source_code,
        "source_url": root_url or sitemap_url or "",
        "provider": provider,
        "crawl": {
            "source_name": crawl_result.source_name,
            "fetched_count": crawl_result.fetched_count,
            "extracted_count": crawl_result.extracted_count,
            "failed_count": crawl_result.failed_count,
            "skipped_count": crawl_result.skipped_count,
            "report_path": crawl_result.report_path,
        },
    }
    if dedupe_result:
        result["dedupe"] = {
            "input_lines": dedupe_result.get("input_lines", 0),
            "output_lines": dedupe_result.get("output_lines", 0),
            "removed_duplicates": dedupe_result.get("removed_duplicates", 0),
        }

    if taxonomy_result:
        result["taxonomy"] = {
            "change_count": taxonomy_result.get("change_count", 0),
            "applied_count": taxonomy_result.get("applied_count", 0),
            "profile_used": taxonomy_result.get("taxonomy_profile_used"),
        }

    if run_quality_audit and quality_status == "fail":
        # Still allow registration — quality gate is advisory
        result["register_dataset"] = True
        result["quality_warning"] = f"Quality audit failed: {'; '.join(quality_reasons)}"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl product URLs from sitemap and materialize into a Product Dataset folder."
    )
    parser.add_argument("--sitemap-url", help="Root sitemap URL for automatic product URL discovery.")
    parser.add_argument("--product-urls", nargs="*", default=[], help="Explicit product URLs (optional, can combine with sitemap).")
    parser.add_argument("--dataset-id", required=True, help="Dataset ID for manifest.json and folder name.")
    parser.add_argument("--source-code", required=True, help="Source code (e.g. gotrangtri, moho).")
    parser.add_argument("--root-url", default="", help="Root URL / source URL of the store.")
    parser.add_argument("--max-urls", type=int, default=DEFAULT_MAX_URLS, help=f"Max URLs to crawl (default {DEFAULT_MAX_URLS}, max {MAX_URLS_LIMIT}).")
    parser.add_argument("--product-only", action="store_true", default=True, help="Filter to product URLs only (default true).")
    parser.add_argument("--run-quality-audit", action="store_true", default=True, help="Run quality audit (default true).")
    parser.add_argument("--run-dedupe", action="store_true", default=True, help="Dedupe crawled products (default true).")
    parser.add_argument("--run-taxonomy-normalize", action="store_true", default=False, help="Run source-aware taxonomy normalize (default false).")
    parser.add_argument("--output-dataset-dir", help="Override output dataset directory.")
    args = parser.parse_args()

    try:
        result = crawl_and_materialize(
            sitemap_url=args.sitemap_url,
            product_urls=args.product_urls,
            dataset_id=args.dataset_id,
            source_code=args.source_code,
            root_url=args.root_url or args.sitemap_url or "",
            max_urls=args.max_urls,
            product_only=args.product_only,
            run_quality_audit=args.run_quality_audit,
            run_dedupe=args.run_dedupe,
            run_taxonomy_normalize=args.run_taxonomy_normalize,
            output_dataset_dir=args.output_dataset_dir,
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
