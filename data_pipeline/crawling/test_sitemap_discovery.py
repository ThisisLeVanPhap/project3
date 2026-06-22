import unittest

from data_pipeline.crawling.discovery.sitemap import SitemapDiscoveryError, SitemapProductUrlDiscoverer


class FakeSitemapFetcher:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.requested_urls: list[str] = []

    def __call__(self, url: str) -> str:
        self.requested_urls.append(url)
        if url not in self.pages:
            raise RuntimeError(f"missing fake sitemap: {url}")
        return self.pages[url]


class SitemapProductUrlDiscovererTests(unittest.TestCase):
    def test_urlset_discovers_product_urls_only(self):
        fetcher = FakeSitemapFetcher({
            "https://shop.example/sitemap.xml": """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://shop.example/shop/sofa-1/</loc></url>
              <url><loc>https://shop.example/shop/</loc></url>
              <url><loc>https://shop.example/blog/post/</loc></url>
              <url><loc>https://shop.example/shop/ban-tra-1/</loc></url>
            </urlset>
            """
        })

        urls = SitemapProductUrlDiscoverer(fetcher=fetcher).discover(
            "https://shop.example/sitemap.xml",
            product_url_patterns=["/shop/"],
        )

        self.assertEqual(urls, [
            "https://shop.example/shop/sofa-1/",
            "https://shop.example/shop/ban-tra-1/",
        ])

    def test_sitemap_index_reads_child_sitemaps(self):
        fetcher = FakeSitemapFetcher({
            "https://shop.example/sitemap.xml": """
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <sitemap><loc>https://shop.example/product-sitemap.xml</loc></sitemap>
              <sitemap><loc>https://shop.example/post-sitemap.xml</loc></sitemap>
            </sitemapindex>
            """,
            "https://shop.example/product-sitemap.xml": """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://shop.example/shop/sofa-1/</loc></url>
            </urlset>
            """,
            "https://shop.example/post-sitemap.xml": """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://shop.example/blog/post/</loc></url>
            </urlset>
            """,
        })

        urls = SitemapProductUrlDiscoverer(fetcher=fetcher).discover(
            "https://shop.example/sitemap.xml",
            product_url_patterns=["/shop/"],
        )

        self.assertEqual(urls, ["https://shop.example/shop/sofa-1/"])

    def test_product_sitemap_without_patterns_discovers_all_urls(self):
        fetcher = FakeSitemapFetcher({
            "https://shop.example/sitemap_products_1.xml": """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://shop.example/products/sofa-1</loc></url>
              <url><loc>https://shop.example/products/table-1</loc></url>
            </urlset>
            """
        })

        urls = SitemapProductUrlDiscoverer(fetcher=fetcher).discover(
            "https://shop.example/sitemap_products_1.xml",
            allowed_domains=["shop.example"],
        )

        self.assertEqual(urls, [
            "https://shop.example/products/sofa-1",
            "https://shop.example/products/table-1",
        ])

    def test_dedupe_and_max_urls(self):
        fetcher = FakeSitemapFetcher({
            "https://shop.example/sitemap.xml": """
            <urlset>
              <url><loc>https://shop.example/shop/sofa-1/</loc></url>
              <url><loc>https://shop.example/shop/sofa-1/</loc></url>
              <url><loc>https://shop.example/shop/sofa-2/</loc></url>
              <url><loc>https://shop.example/shop/sofa-3/</loc></url>
            </urlset>
            """
        })

        urls = SitemapProductUrlDiscoverer(fetcher=fetcher).discover(
            "https://shop.example/sitemap.xml",
            product_url_patterns=["/shop/"],
            max_urls=2,
        )

        self.assertEqual(urls, [
            "https://shop.example/shop/sofa-1/",
            "https://shop.example/shop/sofa-2/",
        ])

    def test_malformed_xml_raises_clear_error(self):
        fetcher = FakeSitemapFetcher({"https://shop.example/sitemap.xml": "<urlset><url>"})

        with self.assertRaises(SitemapDiscoveryError):
            SitemapProductUrlDiscoverer(fetcher=fetcher).discover(
                "https://shop.example/sitemap.xml",
                product_url_patterns=["/shop/"],
            )

    def test_max_sitemaps_limits_index_traversal(self):
        fetcher = FakeSitemapFetcher({
            "https://shop.example/sitemap.xml": """
            <sitemapindex>
              <sitemap><loc>https://shop.example/one.xml</loc></sitemap>
              <sitemap><loc>https://shop.example/two.xml</loc></sitemap>
            </sitemapindex>
            """,
            "https://shop.example/one.xml": """
            <urlset><url><loc>https://shop.example/shop/one/</loc></url></urlset>
            """,
            "https://shop.example/two.xml": """
            <urlset><url><loc>https://shop.example/shop/two/</loc></url></urlset>
            """,
        })

        urls = SitemapProductUrlDiscoverer(fetcher=fetcher, max_sitemaps=2).discover(
            "https://shop.example/sitemap.xml",
            product_url_patterns=["/shop/"],
        )

        self.assertEqual(urls, ["https://shop.example/shop/one/"])


if __name__ == "__main__":
    unittest.main()
