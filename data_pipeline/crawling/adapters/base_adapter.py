from abc import ABC, abstractmethod
from typing import Optional

from data_pipeline.crawling.source_config import CrawlSource


class SiteAdapter(ABC):
    """Build crawl sources for a specific furniture website."""

    name: str
    allowed_domains: list[str]
    default_selectors: dict[str, list[str]]

    @abstractmethod
    def build_source(
        self,
        start_urls: list[str],
        tenant_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> CrawlSource:
        raise NotImplementedError
