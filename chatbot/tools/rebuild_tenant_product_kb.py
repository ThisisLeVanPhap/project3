import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_pipeline.crawling.adapters.gotrangtri import GoTrangTriAdapter
from data_pipeline.crawling.discovery.sitemap import SitemapProductUrlDiscoverer
from data_pipeline.crawling.job import ProductCrawlJob
from data_pipeline.crawling.source_config import CrawlSource
from tools.import_dataset import import_dataset
from tools.materialize_product_dataset import materialize_product_dataset


DEFAULT_CRAWL_LIMIT = 100_000_000


def load_source_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Source manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_urls(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def infer_provider(manifest: dict[str, Any]) -> str | None:
    provider = str(manifest.get("provider") or "").strip().lower()
    if provider:
        return provider
    source_url = str(manifest.get("sourceUrl") or manifest.get("source_url") or "").strip().lower()
    sitemap_url = str(manifest.get("sitemapUrl") or manifest.get("sitemap_url") or "").strip().lower()
    combined = f"{source_url} {sitemap_url}"
    if "gotrangtri.vn" in combined:
        return "gotrangtri"
    host = urlsplit(sitemap_url or source_url).netloc.lower().split(":")[0]
    return host.removeprefix("www.") or None


def domain_from_url(url: str | None) -> str | None:
    host = urlsplit(str(url or "").strip()).netloc.lower().split(":")[0]
    return host.removeprefix("www.") or None


def build_generic_sitemap_source(
    sitemap_url: str,
    provider: str | None,
    tenant_code: str,
    crawled_output_path: Path,
    max_urls: int = DEFAULT_CRAWL_LIMIT,
) -> CrawlSource:
    domain = domain_from_url(sitemap_url)
    urls = SitemapProductUrlDiscoverer(max_sitemaps=DEFAULT_CRAWL_LIMIT).discover(
        sitemap_url=sitemap_url,
        max_urls=max_urls,
        allowed_domains=[domain] if domain else [],
    )
    return CrawlSource(
        name=provider or domain or tenant_code,
        tenant_id=tenant_code,
        start_urls=urls,
        allowed_domains=[domain] if domain else [],
        output_path=str(crawled_output_path),
        max_pages=len(urls),
    )


def build_source(manifest: dict[str, Any], tenant_code: str, crawled_output_path: Path) -> CrawlSource:
    mode = str(manifest.get("mode") or "PRODUCT_URL_LIST").strip().upper()
    provider = infer_provider(manifest)
    urls = normalize_urls(manifest.get("urls"))
    sitemap_url = str(manifest.get("sitemapUrl") or manifest.get("sitemap_url") or "").strip() or None

    if provider == "gotrangtri":
        adapter = GoTrangTriAdapter()
        if mode == "SITEMAP":
            return adapter.build_source_from_sitemap(
                sitemap_url=sitemap_url or "https://gotrangtri.vn/sitemap.xml",
                max_urls=DEFAULT_CRAWL_LIMIT,
                tenant_id=tenant_code,
                output_path=str(crawled_output_path),
            )
        return adapter.build_source(
            urls,
            tenant_id=tenant_code,
            output_path=str(crawled_output_path),
        )

    if mode == "SITEMAP":
        if not sitemap_url:
            raise ValueError("Sitemap URL is required")
        return build_generic_sitemap_source(
            sitemap_url=sitemap_url,
            provider=provider,
            tenant_code=tenant_code,
            crawled_output_path=crawled_output_path,
            max_urls=DEFAULT_CRAWL_LIMIT,
        )
    if not urls:
        raise ValueError("No product URLs found in source manifest")
    return CrawlSource(
        name=provider or tenant_code,
        tenant_id=tenant_code,
        start_urls=urls,
        output_path=str(crawled_output_path),
        max_pages=len(urls),
    )


def rebuild_tenant_product_kb(
    tenant_code: str,
    source_manifest_path: Path,
    kb_base: Path,
    version_tag: str,
    dataset_id: str | None = None,
) -> dict[str, Any]:
    tenant_code = tenant_code.strip()
    source_manifest_path = source_manifest_path.resolve()
    kb_base = kb_base.resolve()
    manifest = load_source_manifest(source_manifest_path)
    dataset_id = (dataset_id or f"{tenant_code}-{version_tag}").strip()

    tenant_root = kb_base / tenant_code
    version_dir = tenant_root / "versions" / version_tag
    version_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tenant-product-kb-") as tmp_dir:
        temp_root = Path(tmp_dir)
        crawled_output_path = temp_root / "products.jsonl"
        dataset_dir = temp_root / "dataset"

        source = build_source(manifest, tenant_code, crawled_output_path)
        if not source.start_urls:
            raise ValueError("No URLs available to crawl")
        source.max_pages = max(1, len(source.start_urls))

        crawl_result = ProductCrawlJob(source).run()
        materialize_result = materialize_product_dataset(
            input_path=crawled_output_path,
            output_dir=dataset_dir,
            dataset_id=dataset_id,
            source=source.name,
            source_url=str(manifest.get("sitemapUrl") or manifest.get("sitemap_url") or manifest.get("sourceUrl") or manifest.get("source_url") or (source.start_urls[0] if source.start_urls else "")),
            version=version_tag,
            overwrite=True,
        )
        import_result = import_dataset(dataset_dir, tenant_code, kb_base, version_tag)

    return {
        "success": True,
        "tenant_code": tenant_code,
        "version_tag": version_tag,
        "kb_dir": str(version_dir),
        "dataset_id": dataset_id,
        "source_manifest_path": str(source_manifest_path),
        "source_type": "PRODUCT_DATASET",
        "product_count": materialize_result.get("product_count"),
        "rag_chunk_count": materialize_result.get("rag_chunk_count"),
        "chunk_count": import_result.get("chunk_count"),
        "quality_status": import_result.get("quality_status") or materialize_result.get("quality_status"),
        "quality_reasons": import_result.get("quality_reasons") or materialize_result.get("quality_reasons") or [],
        "quality_audit_path": import_result.get("quality_audit_path") or materialize_result.get("quality_audit_path"),
        "source_url_snapshot": manifest,
        "crawl": {
            "source_name": crawl_result.source_name,
            "fetched_count": crawl_result.fetched_count,
            "extracted_count": crawl_result.extracted_count,
            "failed_count": crawl_result.failed_count,
            "skipped_count": crawl_result.skipped_count,
            "report_path": crawl_result.report_path,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild a tenant product KB from source manifest using data_pipeline.")
    parser.add_argument("--tenant-code", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--kb-base", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument("--dataset-id")
    args = parser.parse_args()

    try:
        result = rebuild_tenant_product_kb(
            tenant_code=args.tenant_code,
            source_manifest_path=Path(args.source_manifest),
            kb_base=Path(args.kb_base),
            version_tag=args.version_tag.strip(),
            dataset_id=args.dataset_id,
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
