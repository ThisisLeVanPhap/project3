import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.crawling.adapters.gotrangtri import GoTrangTriAdapter
from data_pipeline.crawling.fetcher import RawPage
from data_pipeline.crawling.job import ProductCrawlJob
from data_pipeline.crawling.normalize import make_content_hash


class FakeFetcher:
    def __init__(self, html: str):
        self.html = html

    def fetch(self, url: str) -> RawPage:
        return RawPage(
            url=url,
            final_url=url,
            status_code=200,
            html=self.html,
            fetched_at=datetime(2026, 5, 30, 0, 0, tzinfo=timezone.utc),
            content_hash=make_content_hash(self.html),
            headers={"Content-Type": "text/html"},
        )

    def save_snapshot(self, raw_page: RawPage) -> RawPage:
        return raw_page


class GoTrangTriAdapterTests(unittest.TestCase):
    def test_build_source_has_expected_config(self):
        output_path = "tmp/gotrangtri.jsonl"
        source = GoTrangTriAdapter().build_source(
            ["https://gotrangtri.vn/shop/ban-sofa-ghs-1/"],
            tenant_id="tenant-a",
            output_path=output_path,
        )

        self.assertEqual(source.name, "gotrangtri")
        self.assertEqual(source.tenant_id, "tenant-a")
        self.assertEqual(source.output_path, output_path)
        self.assertIn("gotrangtri.vn", source.allowed_domains)
        self.assertIn("www.gotrangtri.vn", source.allowed_domains)
        self.assertTrue(source.allowed_domains)

    def test_source_selectors_have_minimum_keys(self):
        source = GoTrangTriAdapter().build_source(["https://gotrangtri.vn/shop/ban-sofa-ghs-1/"])

        for key in ("product_name", "price", "description", "image"):
            self.assertIn(key, source.selectors)
            self.assertTrue(source.selectors[key])

    def test_product_crawl_job_extracts_with_adapter_source(self):
        out_path = Path(tempfile.mkdtemp(prefix="gotrangtri-adapter-")) / "products.jsonl"
        url = "https://gotrangtri.vn/shop/ban-sofa-ban-tra-go-tu-nhien-ghs-4494/"
        source = GoTrangTriAdapter().build_source([url], tenant_id="tenant-a", output_path=str(out_path))
        html = """
        <html>
          <head>
            <meta property="og:image" content="https://gotrangtri.vn/uploads/ghs-4494.jpg">
          </head>
          <body>
            <h1>Bàn sofa, bàn trà gỗ tự nhiên GHS-4494</h1>
            <div class="price">5,100,000 VND</div>
            <div class="description">Chất liệu: Gỗ sồi tự nhiên. Kích thước: 1200 x 600 x 435mm.</div>
            <p class="stock">Tình trạng tồn kho: Còn hàng</p>
          </body>
        </html>
        """

        result = ProductCrawlJob(source, fetcher=FakeFetcher(html)).run()

        self.assertEqual(result.fetched_count, 1)
        self.assertEqual(result.extracted_count, 1)
        rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["tenant_id"], "tenant-a")
        self.assertEqual(rows[0]["product_name"], "Bàn sofa, bàn trà gỗ tự nhiên GHS-4494")
        self.assertEqual(rows[0]["price"], 5100000)
        self.assertEqual(rows[0]["metadata"]["extractor"], "selector")


if __name__ == "__main__":
    unittest.main()
