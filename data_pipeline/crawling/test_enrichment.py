import json
import tempfile
import unittest
from pathlib import Path

from data_pipeline.crawling.enrichment import (
    enrich_product_from_text,
    extract_attribute_value_pairs,
    infer_category,
    infer_dimensions,
    infer_material,
)
from data_pipeline.crawling.job import ProductCrawlJob
from data_pipeline.crawling.schema import ProductObservation
from data_pipeline.crawling.source_config import CrawlSource
from data_pipeline.crawling.test_job import FakeFetcher


class EnrichmentRuleTests(unittest.TestCase):
    def test_extracts_material_pair(self):
        pairs = extract_attribute_value_pairs("Chất liệu: Gỗ tự nhiên")

        self.assertEqual(pairs["material"], "Gỗ tự nhiên")

    def test_extracts_dimensions_pair(self):
        pairs = extract_attribute_value_pairs("Kích thước: 120 x 60 x 45 cm")

        self.assertEqual(pairs["dimensions"], "120 x 60 x 45 cm")

    def test_infers_material_from_keywords(self):
        self.assertEqual(infer_material("Sản phẩm làm từ MDF phủ melamine"), "MDF")

    def test_infers_dimensions_pattern(self):
        self.assertEqual(infer_dimensions("Kích thước D120 x R60 x C45 cm"), "D120 x R60 x C45 cm")

    def test_infers_category_from_product_name(self):
        cases = {
            "Sofa văng da GHS-854": "Sofa",
            "Bộ sofa Gỗ sồi tự nhiên GHS-898": "Sofa",
            "Bàn ăn tròn GHS-4345": "Bàn ăn",
            "Bàn ghế ăn GHS-4364": "Bàn ăn",
            "Giường tầng MDF GHS-9244": "Giường",
            "Kệ tivi GHS-3617": "Kệ",
            "Tủ quần áo bé GHS-52234": "Tủ",
            "Bàn sofa, bàn trà gỗ tự nhiên GHS-4494": "Bàn trà",
            "Rèm nhà tắm nhập khẩu GHO-613": "Rèm",
            "Rèm sáo gỗ nhập khẩu cao cấp GHO-610": "Rèm",
            "Rèm cửa văn phòng cao cấp GHO-606": "Rèm",
            "Đèn trang trí phòng khách ABC": "Đèn",
            "Thảm trải sàn phòng khách ABC": "Thảm",
            "Tranh treo tường nghệ thuật ABC": "Tranh",
            "Gương trang trí ABC": "Gương",
            "Bình hoa trang trí ABC": "Đồ trang trí",
        }

        for product_name, expected in cases.items():
            with self.subTest(product_name=product_name):
                self.assertEqual(infer_category(product_name), expected)

    def test_infer_category_ignores_raw_text_noise(self):
        category = infer_category("Sofa văng da GHS-854", "sản phẩm liên quan bàn trà kệ tivi")

        self.assertEqual(category, "Sofa")

    def test_value_boundaries_stop_at_next_spec_key(self):
        pairs = extract_attribute_value_pairs(
            "Màu sắc: xanh Thời gian nhận hàng: 7 ngày "
            "Chất liệu: gỗ công nghiệp Bảo hành: 12 tháng"
        )

        self.assertEqual(pairs["color"], "xanh")
        self.assertEqual(pairs["material"], "gỗ công nghiệp")

    def test_material_and_dimensions_are_split(self):
        pairs = extract_attribute_value_pairs("Chất liệu: gỗ MDF Kích thước: 120 x 60 x 40cm")

        self.assertEqual(pairs["material"], "gỗ MDF")
        self.assertEqual(pairs["dimensions"], "120 x 60 x 40cm")

    def test_material_pair_supports_fabric(self):
        pairs = extract_attribute_value_pairs("Chất liệu: vải polyester Kích thước: 120 x 200cm")

        self.assertEqual(pairs["material"], "vải polyester")
        self.assertEqual(pairs["dimensions"], "120 x 200cm")

    def test_material_does_not_infer_da_from_unrelated_raw_html(self):
        item = ProductObservation(
            source_url="https://shop.example/p/rem",
            product_name="Rèm cửa giá rẻ GHO-609",
            description="Rèm cửa cho văn phòng",
        )

        enrich_product_from_text(item, "đây là đoạn unrelated có chữ da trong HTML")

        self.assertIsNone(item.material)
        self.assertEqual(item.category, "Rèm")

    def test_material_infers_safe_leather_phrases(self):
        self.assertEqual(infer_material("Sofa văng da GHS-854"), "Da")
        self.assertEqual(infer_material("Sofa bọc da công nghiệp cao cấp"), "Da công nghiệp")

    def test_long_material_is_limited_safely(self):
        text = "Chất liệu: " + ("gỗ MDF " * 80) + " Bảo hành: 12 tháng"

        pairs = extract_attribute_value_pairs(text)

        self.assertLessEqual(len(pairs["material"]), 200)
        self.assertNotIn("Bảo hành", pairs["material"])

    def test_enrich_only_fills_missing_fields(self):
        item = ProductObservation(
            source_url="https://shop.example/p/1",
            product_name="Bàn trà GHS-1",
            material="Gỗ sồi",
        )
        enrich_product_from_text(
            item,
            "Chất liệu: MDF\nKích thước: 120 x 60 x 45 cm\nMàu sắc: nâu",
        )

        self.assertEqual(item.material, "Gỗ sồi")
        self.assertEqual(item.dimensions, "120 x 60 x 45 cm")
        self.assertEqual(item.color, "nâu")
        self.assertEqual(item.category, "Bàn trà")
        self.assertTrue(item.metadata["enriched"])
        self.assertNotIn("material", item.metadata["enrichment_fields"])


class EnrichmentJobTests(unittest.TestCase):
    def test_job_exports_enriched_product_fields(self):
        out_path = Path(tempfile.mkdtemp(prefix="crawler-enrichment-")) / "products.jsonl"
        url = "https://shop.example/p/1"
        html = """
        <html>
          <body>
            <h1>Bàn sofa, bàn trà gỗ tự nhiên GHS-4494</h1>
            <div class="price">5.900.000d</div>
            <div class="description">Bàn trà cho phòng khách.</div>
            <section>
              Chất liệu: Gỗ sồi tự nhiên
              Kích thước (D x R x C): 120 x 60 x 45 cm
            </section>
          </body>
        </html>
        """
        source = CrawlSource(
            name="shop-example",
            tenant_id="tenant-a",
            start_urls=[url],
            output_path=str(out_path),
        )

        result = ProductCrawlJob(source, fetcher=FakeFetcher({url: html})).run()

        self.assertEqual(result.extracted_count, 1)
        row = json.loads(out_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(row["category"], "Bàn trà")
        self.assertEqual(row["material"], "Gỗ sồi tự nhiên")
        self.assertEqual(row["dimensions"], "120 x 60 x 45 cm")
        self.assertTrue(row["metadata"]["enriched"])
        self.assertEqual(row["metadata"]["enrichment_method"], "rule_based_text")
        self.assertEqual(row["metadata"]["data_quality"], "medium")


if __name__ == "__main__":
    unittest.main()
