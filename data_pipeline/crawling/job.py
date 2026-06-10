from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

from data_pipeline.crawling.exporters.jsonl_exporter import JsonlProductExporter
from data_pipeline.crawling.enrichment import enrich_product_from_text, html_to_text
from data_pipeline.crawling.extractors.hydration import HydrationProductExtractor
from data_pipeline.crawling.extractors.json_ld import JsonLdProductExtractor
from data_pipeline.crawling.extractors.runner import ProductExtractorRunner
from data_pipeline.crawling.extractors.selector import SelectorProductExtractor
from data_pipeline.crawling.fetcher import HttpFetcher
from data_pipeline.crawling.quality import evaluate_product_quality
from data_pipeline.crawling.report import build_crawl_report, default_report_path, write_crawl_report
from data_pipeline.crawling.schema import ProductObservation
from data_pipeline.crawling.source_config import CrawlSource


@dataclass
class CrawlJobResult:
    source_name: str
    fetched_count: int = 0
    extracted_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    quality_high_count: int = 0
    quality_medium_count: int = 0
    quality_low_count: int = 0
    output_path: str = ""
    report_path: str = ""
    errors: list[dict[str, str]] = field(default_factory=list)


class ProductCrawlJob:
    """Fetch listed product URLs, snapshot raw HTML, extract products, and export JSONL."""

    def __init__(
        self,
        source: CrawlSource,
        fetcher: Optional[HttpFetcher] = None,
        runner: Optional[ProductExtractorRunner] = None,
        exporter: Optional[JsonlProductExporter] = None,
    ):
        self.source = source
        self.fetcher = fetcher or HttpFetcher()
        self.runner = runner or _build_runner(source)
        self.exporter = exporter or JsonlProductExporter()

    def run(self) -> CrawlJobResult:
        result = CrawlJobResult(source_name=self.source.name, output_path=self.source.output_path)
        observations: list[ProductObservation] = []

        for url in self.source.start_urls[: max(0, self.source.max_pages)]:
            if not _is_allowed_domain(url, self.source.allowed_domains):
                result.skipped_count += 1
                result.errors.append({"url": url, "error": "outside_allowed_domains"})
                continue

            try:
                raw_page = self.fetcher.fetch(url)
                result.fetched_count += 1
                raw_page = self.fetcher.save_snapshot(raw_page)
                source_url = raw_page.final_url or raw_page.url
                items = self.runner.extract(raw_page.html, source_url, tenant_id=self.source.tenant_id)
                page_text = html_to_text(raw_page.html)
                for item in items:
                    self._prepare_observation(item, result, page_text)
                observations.extend(items)
                result.extracted_count += len(items)
            except Exception as exc:
                result.failed_count += 1
                result.errors.append({"url": url, "error": str(exc), "type": exc.__class__.__name__})

        self.exporter.export(observations, self.source.output_path, append=False)
        report_path = default_report_path(self.source.output_path)
        report = build_crawl_report(result, observations, self.source)
        result.report_path = write_crawl_report(report, report_path)
        return result

    def _prepare_observation(self, observation: ProductObservation, result: CrawlJobResult, page_text: str = ""):
        if self.source.tenant_id:
            observation.tenant_id = self.source.tenant_id

        enrich_product_from_text(observation, page_text)

        quality = evaluate_product_quality(
            observation,
            require_tenant=bool(self.source.tenant_id),
        )
        observation.metadata = {
            **dict(observation.metadata),
            "data_quality": quality.quality,
            "missing_fields": list(quality.missing_fields),
        }
        if quality.quality == "high":
            result.quality_high_count += 1
        elif quality.quality == "medium":
            result.quality_medium_count += 1
        else:
            result.quality_low_count += 1


def _build_runner(source: CrawlSource) -> ProductExtractorRunner:
    if not source.selectors:
        return ProductExtractorRunner()

    return ProductExtractorRunner(
        extractors=[
            JsonLdProductExtractor(),
            HydrationProductExtractor(),
            SelectorProductExtractor(source.selectors),
        ]
    )


def _is_allowed_domain(url: str, allowed_domains: list[str]) -> bool:
    if not allowed_domains:
        return True

    host = urlsplit(url).netloc.lower()
    if not host:
        return False
    host = host.split("@")[-1].split(":")[0]

    for raw_domain in allowed_domains:
        domain = _normalize_domain(raw_domain)
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False


def _normalize_domain(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "://" in text:
        text = urlsplit(text).netloc
    return text.split("@")[-1].split(":")[0].strip("/")
