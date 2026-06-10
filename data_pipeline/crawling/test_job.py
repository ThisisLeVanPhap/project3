import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.crawling.fetcher import RawPage
from data_pipeline.crawling.job import ProductCrawlJob
from data_pipeline.crawling.normalize import make_content_hash
from data_pipeline.crawling.source_config import CrawlSource


class FakeFetcher:
    def __init__(self, pages=None, failures=None):
        self.pages = pages or {}
        self.failures = failures or {}
        self.fetched_urls = []
        self.snapshot_urls = []

    def fetch(self, url: str) -> RawPage:
        self.fetched_urls.append(url)
        if url in self.failures:
            raise self.failures[url]
        html = self.pages[url]
        return RawPage(
            url=url,
            final_url=url,
            status_code=200,
            html=html,
            fetched_at=datetime(2026, 5, 30, 0, 0, tzinfo=timezone.utc),
            content_hash=make_content_hash(html),
            headers={"Content-Type": "text/html"},
        )

    def save_snapshot(self, raw_page: RawPage) -> RawPage:
        self.snapshot_urls.append(raw_page.url)
        return raw_page


def _product_html(name: str, price: str = "2.500.000d") -> str:
    return f"""
    <html>
      <body>
        <h1>{name}</h1>
        <div class="price">{price}</div>
        <div class="description">Noi that phong khach</div>
      </body>
    </html>
    """


class ProductCrawlJobTests(unittest.TestCase):
    def test_job_fetches_extracts_and_exports_two_urls(self):
        out_path = Path(tempfile.mkdtemp(prefix="crawler-job-")) / "products.jsonl"
        urls = ["https://shop.example/p/1", "https://shop.example/p/2"]
        source = CrawlSource(
            name="shop-example",
            tenant_id="tenant-demo",
            start_urls=urls,
            allowed_domains=["shop.example"],
            output_path=str(out_path),
        )
        fetcher = FakeFetcher({
            urls[0]: _product_html("Sofa SFG041"),
            urls[1]: _product_html("Ban an BA001", "8.500.000d"),
        })

        result = ProductCrawlJob(source, fetcher=fetcher).run()

        self.assertEqual(result.fetched_count, 2)
        self.assertEqual(result.extracted_count, 2)
        self.assertEqual(result.failed_count, 0)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(result.output_path, str(out_path))
        self.assertTrue(result.report_path)
        self.assertTrue(Path(result.report_path).exists())
        rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["product_name"], "Sofa SFG041")
        self.assertEqual(rows[0]["tenant_id"], "tenant-demo")
        self.assertEqual(rows[0]["metadata"]["extractor"], "selector")
        self.assertEqual(rows[0]["metadata"]["data_quality"], "medium")
        report = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
        self.assertEqual(report["counts"]["fetched_count"], 2)
        self.assertEqual(report["field_coverage"]["tenant_id"], 2)
        self.assertEqual(report["data_quality_distribution"], {"medium": 2})

    def test_url_outside_allowed_domains_is_skipped(self):
        out_path = Path(tempfile.mkdtemp(prefix="crawler-job-")) / "products.jsonl"
        source = CrawlSource(
            name="shop-example",
            start_urls=["https://other.example/p/1", "https://shop.example/p/1"],
            allowed_domains=["shop.example"],
            output_path=str(out_path),
        )
        fetcher = FakeFetcher({"https://shop.example/p/1": _product_html("Sofa")})

        result = ProductCrawlJob(source, fetcher=fetcher).run()

        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.fetched_count, 1)
        self.assertEqual(fetcher.fetched_urls, ["https://shop.example/p/1"])
        self.assertEqual(result.errors[0]["error"], "outside_allowed_domains")

    def test_fetch_error_does_not_stop_remaining_urls(self):
        out_path = Path(tempfile.mkdtemp(prefix="crawler-job-")) / "products.jsonl"
        bad_url = "https://shop.example/p/bad"
        good_url = "https://shop.example/p/good"
        source = CrawlSource(
            name="shop-example",
            start_urls=[bad_url, good_url],
            allowed_domains=["shop.example"],
            output_path=str(out_path),
        )
        fetcher = FakeFetcher(
            pages={good_url: _product_html("Tu quan ao MDF")},
            failures={bad_url: RuntimeError("temporary fetch failure")},
        )

        result = ProductCrawlJob(source, fetcher=fetcher).run()

        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.fetched_count, 1)
        self.assertEqual(result.extracted_count, 1)
        self.assertEqual(result.errors[0]["url"], bad_url)
        rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_name"], "Tu quan ao MDF")

    def test_tenant_id_is_passed_to_product_observation(self):
        out_path = Path(tempfile.mkdtemp(prefix="crawler-job-")) / "products.jsonl"
        url = "https://shop.example/p/1"
        source = CrawlSource(
            name="shop-example",
            tenant_id="tenant-caco",
            start_urls=[url],
            output_path=str(out_path),
        )
        fetcher = FakeFetcher({url: _product_html("Sofa tenant")})

        ProductCrawlJob(source, fetcher=fetcher).run()

        rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["tenant_id"], "tenant-caco")
        self.assertEqual(rows[0]["metadata"]["extractor"], "selector")

    def test_two_tenants_same_url_write_separate_tenant_ids(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="crawler-job-tenant-"))
        url = "https://shop.example/p/shared"
        fetcher = FakeFetcher({url: _product_html("Shared Sofa")})

        source_a = CrawlSource(
            name="tenant-a-source",
            tenant_id="tenant-a",
            start_urls=[url],
            output_path=str(temp_dir / "tenant-a.jsonl"),
        )
        source_b = CrawlSource(
            name="tenant-b-source",
            tenant_id="tenant-b",
            start_urls=[url],
            output_path=str(temp_dir / "tenant-b.jsonl"),
        )

        ProductCrawlJob(source_a, fetcher=fetcher).run()
        ProductCrawlJob(source_b, fetcher=fetcher).run()

        row_a = json.loads((temp_dir / "tenant-a.jsonl").read_text(encoding="utf-8").splitlines()[0])
        row_b = json.loads((temp_dir / "tenant-b.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(row_a["tenant_id"], "tenant-a")
        self.assertEqual(row_b["tenant_id"], "tenant-b")


if __name__ == "__main__":
    unittest.main()
