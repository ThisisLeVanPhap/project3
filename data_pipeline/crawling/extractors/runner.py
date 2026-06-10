from typing import Optional

from data_pipeline.crawling.extractors.base import BaseProductExtractor
from data_pipeline.crawling.extractors.hydration import HydrationProductExtractor
from data_pipeline.crawling.extractors.json_ld import JsonLdProductExtractor
from data_pipeline.crawling.extractors.selector import SelectorProductExtractor
from data_pipeline.crawling.schema import ProductObservation


class ProductExtractorRunner:
    """Run product extractors in priority order with light dedupe."""

    def __init__(
        self,
        extractors: Optional[list[BaseProductExtractor]] = None,
        merge_all: bool = False,
    ):
        self.extractors = extractors or [
            JsonLdProductExtractor(),
            HydrationProductExtractor(),
            SelectorProductExtractor(),
        ]
        self.merge_all = merge_all

    def extract(
        self,
        html: str,
        source_url: str,
        tenant_id: Optional[str] = None,
    ) -> list[ProductObservation]:
        all_items: list[ProductObservation] = []
        for extractor in self.extractors:
            try:
                items = extractor.extract(html, source_url, tenant_id)
            except Exception:
                items = []
            if not items:
                continue
            if not self.merge_all:
                return _dedupe(items)
            all_items.extend(items)
        return _dedupe(all_items)


def _dedupe(items: list[ProductObservation]) -> list[ProductObservation]:
    result: list[ProductObservation] = []
    seen: set[str] = set()
    for item in items:
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_key(item: ProductObservation) -> str:
    if item.canonical_url:
        return f"url:{item.canonical_url}"
    if item.sku:
        return f"sku:{item.sku}"
    if item.product_name and item.price is not None and item.source_url:
        return f"fallback:{item.product_name}|{item.price}|{item.source_url}"
    if item.content_hash:
        return f"hash:{item.content_hash}"
    return f"id:{id(item)}"
