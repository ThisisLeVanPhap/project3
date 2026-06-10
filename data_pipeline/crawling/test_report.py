import json
import tempfile
import unittest
from pathlib import Path

from data_pipeline.crawling.job import CrawlJobResult
from data_pipeline.crawling.report import build_crawl_report, default_report_path
from data_pipeline.crawling.schema import ProductObservation
from data_pipeline.crawling.source_config import CrawlSource


class CrawlReportTests(unittest.TestCase):
    def test_build_crawl_report_has_main_keys_and_counts(self):
        source = CrawlSource(name="shop", tenant_id="tenant-a", start_urls=["https://shop.example/p/1"])
        result = CrawlJobResult(
            source_name="shop",
            fetched_count=2,
            extracted_count=2,
            failed_count=0,
            skipped_count=1,
            quality_high_count=1,
            quality_medium_count=1,
            output_path="out/products.jsonl",
        )
        products = [
            ProductObservation(
                tenant_id="tenant-a",
                source_url="https://shop.example/p/1",
                product_name="Sofa",
                price="2.500.000d",
                category="Sofa",
                material="Gỗ tự nhiên",
                image_urls=["https://shop.example/sofa.jpg"],
                sku="S1",
                availability="InStock",
                metadata={"extractor": "json_ld", "data_quality": "high"},
            ),
            ProductObservation(
                tenant_id="tenant-a",
                source_url="https://shop.example/p/2",
                product_name="Bàn trà",
                category="Bàn trà",
                metadata={"extractor": "selector", "data_quality": "medium"},
            ),
        ]

        report = build_crawl_report(result, products, source)

        self.assertTrue(report["run_id"])
        self.assertEqual(report["source_name"], "shop")
        self.assertEqual(report["tenant_id"], "tenant-a")
        self.assertEqual(report["counts"]["fetched_count"], 2)
        self.assertEqual(report["counts"]["skipped_count"], 1)
        self.assertEqual(report["field_coverage"]["tenant_id"], 2)
        self.assertEqual(report["field_coverage"]["price"], 1)
        self.assertEqual(report["field_coverage"]["image_urls"], 1)
        self.assertEqual(report["category_distribution"], {"Sofa": 1, "Bàn trà": 1})
        self.assertEqual(report["extractor_distribution"], {"json_ld": 1, "selector": 1})
        self.assertEqual(report["data_quality_distribution"], {"high": 1, "medium": 1})
        self.assertEqual(len(report["sample_products"]), 2)

    def test_default_report_path_is_next_to_jsonl(self):
        self.assertEqual(
            default_report_path("data_pipeline/output/products.jsonl"),
            "data_pipeline\\output\\products.jsonl.report.json",
        )

