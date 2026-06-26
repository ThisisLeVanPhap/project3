from typing import Optional

from data_pipeline.crawling.adapters.base_adapter import SiteAdapter
from data_pipeline.crawling.discovery.sitemap import SitemapProductUrlDiscoverer
from data_pipeline.crawling.source_config import CrawlSource


class MHomeAdapter(SiteAdapter):
    """Adapter config for mhomefurniture.vn product pages (WordPress/WooCommerce)."""

    name = "mhome"
    allowed_domains = ["mhomefurniture.vn", "www.mhomefurniture.vn"]

    default_selectors = {}

    def build_source(
        self,
        start_urls: list[str],
        tenant_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> CrawlSource:
        return CrawlSource(
            name=self.name,
            tenant_id=tenant_id,
            start_urls=list(start_urls),
            allowed_domains=list(self.allowed_domains),
            output_path=output_path or "data_pipeline/output/mhome_products.jsonl",
            max_pages=len(start_urls),
        )

    def discover_product_urls(
        self,
        sitemap_url: str = "https://mhomefurniture.vn/product-sitemap.xml",
        max_urls: int = 1000,
    ) -> list[str]:
        return SitemapProductUrlDiscoverer().discover(
            sitemap_url=sitemap_url,
            product_url_patterns=[],
            max_urls=max_urls,
            allowed_domains=list(self.allowed_domains),
        )

    def build_source_from_sitemap(
        self,
        sitemap_url: str = "https://mhomefurniture.vn/product-sitemap.xml",
        max_urls: int = 1000,
        tenant_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> CrawlSource:
        return self.build_source(
            self.discover_product_urls(sitemap_url=sitemap_url, max_urls=max_urls),
            tenant_id=tenant_id,
            output_path=output_path,
        )
