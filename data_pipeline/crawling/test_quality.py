import unittest

from data_pipeline.crawling.quality import evaluate_product_quality
from data_pipeline.crawling.schema import ProductObservation


class ProductQualityTests(unittest.TestCase):
    def test_missing_price_or_image_is_medium_and_reports_fields(self):
        item = ProductObservation(
            source_url="https://shop.example/p/sofa",
            product_name="Sofa",
            description="Sofa phong khach",
        )

        quality = evaluate_product_quality(item)

        self.assertEqual(quality.quality, "medium")
        self.assertIn("price", quality.missing_fields)
        self.assertIn("image_urls", quality.missing_fields)

    def test_require_tenant_without_tenant_is_low(self):
        item = ProductObservation(
            source_url="https://shop.example/p/sofa",
            product_name="Sofa",
            price="2.500.000d",
            description="Sofa phong khach",
            image_urls=["https://shop.example/sofa.jpg"],
        )

        quality = evaluate_product_quality(item, require_tenant=True)

        self.assertEqual(quality.quality, "low")
        self.assertIn("tenant_id", quality.missing_fields)

    def test_complete_product_is_high(self):
        item = ProductObservation(
            tenant_id="tenant-a",
            source_url="https://shop.example/p/sofa",
            product_name="Sofa",
            price="2.500.000d",
            description="Sofa phong khach",
            image_urls=["https://shop.example/sofa.jpg"],
        )

        quality = evaluate_product_quality(item, require_tenant=True)

        self.assertEqual(quality.quality, "high")
        self.assertEqual(quality.missing_fields, [])


if __name__ == "__main__":
    unittest.main()
