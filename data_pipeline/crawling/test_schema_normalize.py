import unittest
from datetime import datetime, timezone

from data_pipeline.crawling.normalize import (
    canonicalize_url,
    make_content_hash,
    normalize_price,
)
from data_pipeline.crawling.schema import ProductObservation


class NormalizeTests(unittest.TestCase):
    def test_normalize_price_vietnamese_formats(self):
        self.assertEqual(normalize_price("2.500.000d"), 2500000)
        self.assertEqual(normalize_price("2,500,000 VND"), 2500000)
        self.assertEqual(normalize_price("1.2 trieu"), 1200000)
        self.assertEqual(normalize_price("1.2-1.5 trieu"), 1200000)
        self.assertIsNone(normalize_price("Call 09xx"))
        self.assertIsNone(normalize_price("Lien he"))
        self.assertIsNone(normalize_price(""))
        self.assertIsNone(normalize_price(None))

    def test_canonicalize_url_removes_tracking_and_fragment(self):
        url = "HTTPS://Example.com/Product/ABC/?utm_source=ad&color=oak&fbclid=123#section"
        self.assertEqual(canonicalize_url(url), "https://example.com/Product/ABC?color=oak")

    def test_canonicalize_url_handles_empty_relative_and_fragment(self):
        self.assertIsNone(canonicalize_url(None))
        self.assertIsNone(canonicalize_url(""))
        self.assertEqual(canonicalize_url("/products/sofa?utm_campaign=x&color=oak#top"), "/products/sofa?color=oak")
        self.assertEqual(canonicalize_url("https://shop.example/p/1?b=2&a=1#details"), "https://shop.example/p/1?a=1&b=2")

    def test_make_content_hash_is_stable_for_dict_order(self):
        left = {"name": "Sofa", "price": 2500000, "tags": ["oak", "small"]}
        right = {"tags": ["oak", "small"], "price": 2500000, "name": "Sofa"}
        self.assertEqual(make_content_hash(left), make_content_hash(right))


class ProductObservationTests(unittest.TestCase):
    def test_product_observation_exports_jsonl_dict(self):
        observed_at = datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc)
        item = ProductObservation(
            source_url="https://shop.example/p/sofa?utm_source=test",
            product_name="  Sofa go soi  ",
            price="2.500.000d",
            original_price="3.000.000d",
            currency="d",
            category=" sofa ",
            brand=" CaCo ",
            material=" go soi ",
            color=" nau ",
            dimensions="2m x 0.9m",
            description="Sofa cho phong khach nho",
            image_urls=["/images/sofa.jpg", "https://shop.example/images/sofa.jpg"],
            observed_at=observed_at,
            metadata={
                "source": "unit-test",
                "enriched": True,
                "enrichment_fields": ["material", "color"],
                "data_quality": "high",
                "missing_fields": [],
            },
        )

        row = item.to_jsonl_dict()

        self.assertEqual(row["product_name"], "Sofa go soi")
        self.assertIsNone(row["tenant_id"])
        self.assertEqual(row["price"], 2500000)
        self.assertEqual(row["original_price"], 3000000)
        self.assertEqual(row["currency"], "VND")
        self.assertEqual(row["source_url"], "https://shop.example/p/sofa")
        self.assertIsNone(row["canonical_url"])
        self.assertEqual(row["observed_at"], "2026-05-29T12:00:00+00:00")
        self.assertEqual(row["category"], "sofa")
        self.assertEqual(row["brand"], "CaCo")
        self.assertEqual(row["material"], "go soi")
        self.assertEqual(row["color"], "nau")
        self.assertEqual(row["dimensions"], "2m x 0.9m")
        self.assertEqual(row["description"], "Sofa cho phong khach nho")
        self.assertEqual(row["image_urls"], ["https://shop.example/images/sofa.jpg"])
        self.assertIsNone(row["availability"])
        self.assertIsNone(row["sku"])
        self.assertEqual(row["confidence"], 1.0)
        self.assertEqual(row["metadata"]["source"], "unit-test")
        self.assertTrue(row["metadata"]["enriched"])
        self.assertEqual(row["metadata"]["enrichment_fields"], ["material", "color"])
        self.assertEqual(row["metadata"]["data_quality"], "high")
        self.assertEqual(row["metadata"]["missing_fields"], [])
        self.assertTrue(row["content_hash"])

    def test_product_observation_exports_tenant_id(self):
        item = ProductObservation(
            tenant_id="tenant-a",
            source_url="https://shop.example/p/sofa",
            product_name="Sofa",
        )

        row = item.to_jsonl_dict()

        self.assertEqual(row["tenant_id"], "tenant-a")

    def test_product_observation_clamps_confidence(self):
        base = {
            "source_url": "https://shop.example/p/sofa",
            "product_name": "Sofa",
        }

        self.assertEqual(ProductObservation(**base, confidence=0.7).confidence, 0.7)
        self.assertEqual(ProductObservation(**base, confidence=2).confidence, 1.0)
        self.assertEqual(ProductObservation(**base, confidence=-1).confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
