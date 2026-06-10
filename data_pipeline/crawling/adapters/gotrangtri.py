from typing import Optional

from data_pipeline.crawling.adapters.base_adapter import SiteAdapter
from data_pipeline.crawling.discovery.sitemap import SitemapProductUrlDiscoverer
from data_pipeline.crawling.source_config import CrawlSource


class GoTrangTriAdapter(SiteAdapter):
    """Adapter config for gotrangtri.vn product pages."""

    name = "gotrangtri"
    allowed_domains = ["gotrangtri.vn", "www.gotrangtri.vn"]

    # Inspected product pages show h1 title, visible VND price near the product
    # header, stock text, and product detail paragraphs. Keep generic fallbacks
    # because exact theme classes can change between pages.
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
            ".woocommerce-Price-amount",
            ".amount",
            '[itemprop="price"]',
            'meta[property="product:price:amount"]',
        ],
        "description": [
            ".description",
            ".product-description",
            ".woocommerce-product-details__short-description",
            ".entry-content",
            "article",
            '[itemprop="description"]',
            'meta[name="description"]',
            'meta[property="og:description"]',
        ],
        "image": [
            'meta[property="og:image"]',
            '[itemprop="image"]',
            "img.wp-post-image",
            "img.product-image",
            ".product-image img",
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
            output_path=output_path or "data_pipeline/output/gotrangtri_products.jsonl",
        )

    def discover_product_urls(
        self,
        sitemap_url: str = "https://gotrangtri.vn/sitemap.xml",
        max_urls: int = 100,
    ) -> list[str]:
        return SitemapProductUrlDiscoverer().discover(
            sitemap_url=sitemap_url,
            product_url_patterns=["/shop/"],
            max_urls=max_urls,
        )

    def build_source_from_sitemap(
        self,
        sitemap_url: str = "https://gotrangtri.vn/sitemap.xml",
        max_urls: int = 100,
        tenant_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> CrawlSource:
        return self.build_source(
            self.discover_product_urls(sitemap_url=sitemap_url, max_urls=max_urls),
            tenant_id=tenant_id,
            output_path=output_path,
        )
