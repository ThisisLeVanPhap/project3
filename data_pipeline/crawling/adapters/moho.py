from typing import Optional

from data_pipeline.crawling.adapters.base_adapter import SiteAdapter
from data_pipeline.crawling.discovery.sitemap import SitemapProductUrlDiscoverer
from data_pipeline.crawling.source_config import CrawlSource


class MohoAdapter(SiteAdapter):
    """Adapter config for moho.com.vn product pages (Haravan platform)."""

    name = "moho"
    allowed_domains = ["moho.com.vn", "www.moho.com.vn"]

    # Haravan platform — class names are auto-generated and unstable.
    # Rely on JSON-LD structured data (JsonLdProductExtractor) and generic
    # hydration fallbacks. CSS selectors are best-effort only.
    default_selectors = {
        "product_name": [
            "h1",
            ".product-title",
            ".product-name",
            '[itemprop="name"]',
            'meta[property="og:title"]',
        ],
        "price": [
            ".price",
            ".product-price",
            ".current-price",
            '[itemprop="price"]',
            'meta[property="product:price:amount"]',
        ],
        "description": [
            '[itemprop="description"]',
            'meta[name="description"]',
            'meta[property="og:description"]',
            "#description_product",
            ".product-description",
        ],
        "image": [
            'meta[property="og:image"]',
            '[itemprop="image"]',
            ".product-img img",
            ".gallery img",
        ],
        "availability": [
            '[itemprop="availability"]',
            ".stock",
            ".availability",
        ],
    }

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
            selectors={key: list(value) for key, value in self.default_selectors.items()},
            output_path=output_path or "data_pipeline/output/moho_products.jsonl",
            max_pages=len(start_urls),
        )

    def discover_product_urls(
        self,
        sitemap_url: str = "https://moho.com.vn/sitemap.xml",
        max_urls: int = 1000,
    ) -> list[str]:
        return SitemapProductUrlDiscoverer().discover(
            sitemap_url=sitemap_url,
            product_url_patterns=["/products/"],
            max_urls=max_urls,
        )

    def build_source_from_sitemap(
        self,
        sitemap_url: str = "https://moho.com.vn/sitemap.xml",
        max_urls: int = 1000,
        tenant_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> CrawlSource:
        return self.build_source(
            self.discover_product_urls(sitemap_url=sitemap_url, max_urls=max_urls),
            tenant_id=tenant_id,
            output_path=output_path,
        )
