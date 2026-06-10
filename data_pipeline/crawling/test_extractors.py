import unittest

from data_pipeline.crawling.extractors.hydration import HydrationProductExtractor, MAX_JSON_SCAN_CHARS
from data_pipeline.crawling.extractors.json_ld import JsonLdProductExtractor


class JsonLdProductExtractorTests(unittest.TestCase):
    def test_extracts_single_product_with_offer(self):
        html = """
        <html><head>
          <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Sofa gỗ sồi SFG041",
            "description": "Sofa phòng khách nhỏ",
            "image": ["/images/sfg041.jpg"],
            "brand": {"name": "CaCo"},
            "sku": "SFG041",
            "category": "sofa",
            "url": "/products/sfg041",
            "offers": {
              "@type": "Offer",
              "price": "12.500.000₫",
              "priceCurrency": "VND",
              "availability": "https://schema.org/InStock"
            }
          }
          </script>
        </head></html>
        """

        items = JsonLdProductExtractor().extract(html, "https://shop.example/catalog")

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.product_name, "Sofa gỗ sồi SFG041")
        self.assertEqual(item.price, 12500000)
        self.assertEqual(item.currency, "VND")
        self.assertEqual(item.brand, "CaCo")
        self.assertEqual(item.sku, "SFG041")
        self.assertEqual(item.category, "sofa")
        self.assertEqual(item.canonical_url, "https://shop.example/products/sfg041")
        self.assertEqual(item.image_urls, ["https://shop.example/images/sfg041.jpg"])
        self.assertEqual(item.metadata["extractor"], "json_ld")
        self.assertEqual(item.metadata["extractor_priority"], 1)

    def test_extracts_product_from_graph(self):
        html = """
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {"@type": "BreadcrumbList", "name": "Breadcrumb"},
            {
              "@type": ["Thing", "Product"],
              "name": "Bàn ăn gỗ tự nhiên",
              "offers": {"lowPrice": "8.500.000", "priceCurrency": "VND"}
            }
          ]
        }
        </script>
        """

        items = JsonLdProductExtractor().extract(html, "https://shop.example/ban-an")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].product_name, "Bàn ăn gỗ tự nhiên")
        self.assertEqual(items[0].price, 8500000)

    def test_invalid_json_ld_does_not_crash(self):
        html = """
        <script type="application/ld+json">{ bad json</script>
        <script type="application/ld+json">
        {"@type":"Product","name":"Tủ quần áo","offers":{"price":"5,000,000 VND"}}
        </script>
        """

        items = JsonLdProductExtractor().extract(html, "https://shop.example/tu")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].product_name, "Tủ quần áo")


class HydrationProductExtractorTests(unittest.TestCase):
    def test_extracts_next_data_product(self):
        html = """
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "product": {
                "name": "Giường ngủ MDF",
                "price": "6.800.000đ",
                "sku": "GIUONG-1M6-01",
                "category": "giường",
                "material": "MDF phủ Melamine",
                "url": "/giuong/giuong-1m6-01",
                "images": [{"url": "/img/giuong.jpg"}]
              }
            }
          }
        }
        </script>
        """

        items = HydrationProductExtractor().extract(html, "https://shop.example/products")

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.product_name, "Giường ngủ MDF")
        self.assertEqual(item.price, 6800000)
        self.assertEqual(item.sku, "GIUONG-1M6-01")
        self.assertEqual(item.category, "giường")
        self.assertEqual(item.material, "MDF phủ Melamine")
        self.assertEqual(item.canonical_url, "https://shop.example/giuong/giuong-1m6-01")
        self.assertEqual(item.image_urls, ["https://shop.example/img/giuong.jpg"])
        self.assertEqual(item.metadata["extractor"], "hydration")
        self.assertEqual(item.metadata["extractor_priority"], 2)

    def test_no_product_returns_empty_list(self):
        html = """
        <script>
        window.__INITIAL_STATE__ = {"page": {"title": "Homepage"}, "items": [{"name": "Only name"}]};
        </script>
        """

        items = HydrationProductExtractor().extract(html, "https://shop.example")

        self.assertEqual(items, [])

    def test_large_malformed_hydration_script_does_not_crash(self):
        html = (
            "<script>window.__INITIAL_STATE__ = {"
            + '"items": [' + '{"name":"Sofa"},' * 1000
            + (" " * MAX_JSON_SCAN_CHARS)
            + "</script>"
        )

        items = HydrationProductExtractor().extract(html, "https://shop.example")

        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
