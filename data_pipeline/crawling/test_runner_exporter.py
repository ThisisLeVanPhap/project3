import json
import tempfile
import unittest
from pathlib import Path

from data_pipeline.crawling.exporters.jsonl_exporter import JsonlProductExporter
from data_pipeline.crawling.extractors.runner import ProductExtractorRunner
from data_pipeline.crawling.extractors.selector import SelectorProductExtractor


class SelectorProductExtractorTests(unittest.TestCase):
    def test_selector_extracts_basic_product_fields(self):
        html = """
        <html>
          <head>
            <meta property="og:image" content="/images/sofa.jpg">
          </head>
          <body>
            <h1>Sofa go soi</h1>
            <div class="price">2.500.000d</div>
            <div class="description">Sofa phong khach nho</div>
            <span class="stock">Con hang</span>
          </body>
        </html>
        """

        items = SelectorProductExtractor().extract(html, "https://shop.example/products/sofa")

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.product_name, "Sofa go soi")
        self.assertEqual(item.price, 2500000)
        self.assertEqual(item.description, "Sofa phong khach nho")
        self.assertEqual(item.image_urls, ["https://shop.example/images/sofa.jpg"])
        self.assertEqual(item.availability, "Con hang")
        self.assertEqual(item.metadata["extractor"], "selector")
        self.assertEqual(item.metadata["extractor_priority"], 3)


class ProductExtractorRunnerTests(unittest.TestCase):
    def test_runner_prefers_json_ld_before_selector(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"Ten tu JSON-LD","offers":{"price":"3.000.000"}}
        </script>
        <h1>Ten tu selector</h1>
        <div class="price">2.000.000d</div>
        """

        items = ProductExtractorRunner().extract(html, "https://shop.example/p/1")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].product_name, "Ten tu JSON-LD")
        self.assertEqual(items[0].price, 3000000)
        self.assertEqual(items[0].metadata["extractor"], "json_ld")

    def test_runner_falls_back_to_selector(self):
        html = """
        <h1>Ban an go tu nhien</h1>
        <div class="product-price">8,500,000 VND</div>
        """

        items = ProductExtractorRunner().extract(html, "https://shop.example/ban-an")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].product_name, "Ban an go tu nhien")
        self.assertEqual(items[0].price, 8500000)
        self.assertEqual(items[0].metadata["extractor"], "selector")

    def test_runner_dedupes_when_merge_all_true(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"Sofa SFG041","sku":"SFG041","url":"/p/sfg041","offers":{"price":"12.000.000"}}
        </script>
        <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"product":{"name":"Sofa SFG041","sku":"SFG041","url":"/p/sfg041","price":"12.000.000"}}}}
        </script>
        <h1>Sofa SFG041</h1>
        <div class="price">12.000.000d</div>
        """

        items = ProductExtractorRunner(merge_all=True).extract(html, "https://shop.example/p/sfg041")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].product_name, "Sofa SFG041")

    def test_runner_dedupes_json_ld_and_selector_same_page(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"Sofa SFG041","offers":{"price":"12.000.000"}}
        </script>
        <h1>Sofa SFG041</h1>
        <div class="price">12.000.000d</div>
        """

        items = ProductExtractorRunner(merge_all=True).extract(html, "https://shop.example/p/sfg041")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].metadata["extractor"], "json_ld")


class JsonlProductExporterTests(unittest.TestCase):
    def test_exporter_writes_jsonl_lines(self):
        html = """
        <h1>Tu quan ao MDF</h1>
        <div class="price">5.500.000d</div>
        """
        observations = ProductExtractorRunner().extract(html, "https://shop.example/tu-ao")
        out_path = Path(tempfile.mkdtemp(prefix="crawler-jsonl-")) / "products.jsonl"

        stats = JsonlProductExporter().export(observations, out_path)

        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["path"], str(out_path))
        rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_name"], "Tu quan ao MDF")
        self.assertEqual(rows[0]["price"], 5500000)


if __name__ == "__main__":
    unittest.main()
