"""Tests for general_compare response renderer."""

import unittest

from app.general_catalog_provider import BackendCatalogItem
from app.general_compare_renderer import (
    detect_intent,
    render_general_compare,
    render_recommendation,
    render_comparison,
    render_price_sensitive,
    render_generic,
    _map_reasons,
    _price_str,
    _material_str,
    SCORE_REASON_MAP,
)


def _make_item(name: str, price=None, material=None, category=None, source="Gotrangtri",
               source_url=None, score=10.0, reasons=None, currency="VND") -> BackendCatalogItem:
    return BackendCatalogItem(
        name=name,
        source_code="gotrangtri",
        source_name=source,
        category=category,
        material=material,
        price=price,
        currency=currency,
        source_url=source_url or f"https://gotrangtri.vn/shop/{name.lower().replace(' ', '-')}",
        score=score,
        score_reasons=reasons or ["category_match", "price_within_budget"],
    )


class GeneralCompareRendererTests(unittest.TestCase):

    # --- Intent detection ---

    def test_detect_recommendation_intent(self):
        self.assertEqual("recommendation", detect_intent("gợi ý sofa vải"))
        self.assertEqual("recommendation", detect_intent("tư vấn giúp mình chọn tủ"))
        self.assertEqual("recommendation", detect_intent("nên mua bàn làm việc nào"))
        self.assertEqual("recommendation", detect_intent("chọn giường ngủ 1m6"))

    def test_detect_compare_intent(self):
        self.assertEqual("compare", detect_intent("so sánh sofa và bàn trà"))
        self.assertEqual("compare", detect_intent("sofa khác nhau thế nào"))

    def test_detect_price_sensitive_intent(self):
        self.assertEqual("price_sensitive", detect_intent("tủ dưới 5 triệu"))
        self.assertEqual("price_sensitive", detect_intent("giá tốt"))

    def test_detect_generic_intent(self):
        self.assertEqual("generic", detect_intent("bàn gỗ"))
        self.assertEqual("generic", detect_intent("kệ tivi"))

    # --- Score reasons mapping ---

    def test_map_reasons_to_vietnamese(self):
        reasons = ["category_match", "price_within_budget", "unknown_reason"]
        mapped = _map_reasons(reasons)
        self.assertIn("đúng loại sản phẩm cần tìm", mapped)
        self.assertIn("nằm trong ngân sách", mapped)
        self.assertIn("unknown_reason", mapped)  # unknown keys pass through

    def test_all_reasons_have_mapping(self):
        expected_keys = {
            "category_match", "material_match", "price_within_budget",
            "price_above_minimum", "price_missing", "text_match",
            "source_match", "has_image",
        }
        self.assertEqual(expected_keys, set(SCORE_REASON_MAP.keys()))

    # --- Format helpers ---

    def test_price_str_with_price(self):
        self.assertEqual("10.000.000 VND", _price_str(10000000, "VND"))
        self.assertEqual("5.500.000 VND", _price_str(5500000, "VND"))

    def test_price_str_null_returns_fallback(self):
        self.assertEqual("chưa có giá", _price_str(None, "VND"))

    def test_material_str_with_material(self):
        self.assertEqual("vải", _material_str("vải"))

    def test_material_str_null_returns_fallback(self):
        self.assertEqual("chưa rõ chất liệu", _material_str(None))

    # --- Render recommendation ---

    def test_render_recommendation_has_items(self):
        items = [
            _make_item("Sofa vải SFG041", price=6500000, material="vải", category="Sofa"),
            _make_item("Sofa da SFG042", price=8900000, material="da", category="Sofa"),
        ]
        text = render_recommendation("gợi ý sofa vải", items)
        self.assertIn("Sofa vải SFG041", text)
        self.assertIn("Sofa da SFG042", text)
        self.assertIn("6.500.000", text)
        self.assertIn("8.900.000", text)
        self.assertIn("vải", text)
        self.assertIn("Nếu ưu tiên giá thấp", text)

    def test_render_recommendation_no_price_no_material(self):
        items = [
            _make_item("Sản phẩm X", price=None, material=None, category=None),
        ]
        text = render_recommendation("test", items)
        self.assertIn("Sản phẩm X", text)
        self.assertIn("chưa có giá", text)
        # Should not crash

    def test_render_recommendation_empty_items(self):
        text = render_recommendation("test", [])
        self.assertIn("chưa có đủ dữ liệu", text)

    # --- Render comparison ---

    def test_render_comparison_has_compare_format(self):
        items = [
            _make_item("Sofa SFG041", price=6500000, material="vải", category="Sofa"),
            _make_item("Sofa SFG042", price=8900000, material="da", category="Sofa"),
            _make_item("Bàn trà GHS100", price=1200000, material="gỗ", category="Bàn trà"),
        ]
        text = render_comparison("so sánh sofa", items)
        self.assertIn("So sánh nhanh", text)
        self.assertIn("Điểm mạnh", text)
        self.assertIn("Nếu ưu tiên giá thấp", text)

    # --- Render price-sensitive ---

    def test_render_price_sensitive_has_budget_context(self):
        items = [
            _make_item("Sofa SFG041", price=3500000, material="vải"),
            _make_item("Sofa SFG042", price=5500000, material="vải"),
        ]
        text = render_price_sensitive("tủ dưới 5 triệu", items)
        self.assertIn("ngân sách", text)
        self.assertIn("3.500.000", text)

    # --- Render generic ---

    def test_render_generic_no_special_intent(self):
        items = [_make_item("Kệ tivi GHS200", price=2500000)]
        text = render_generic("kệ tivi", items)
        self.assertIn("Kệ tivi GHS200", text)
        self.assertIn("2.500.000", text)

    # --- Main entry point ---

    def test_render_general_compare_empty(self):
        text = render_general_compare("test", [])
        self.assertIn("chưa có đủ dữ liệu", text)

    def test_render_general_compare_with_items(self):
        items = [_make_item("Sofa vải", price=6500000)]
        text = render_general_compare("gợi ý sofa", items)
        self.assertIn("Sofa vải", text)
        self.assertIn("6.500.000", text)

    def test_render_general_compare_preserves_backend_order(self):
        items = [
            _make_item("A", price=100000, score=20),
            _make_item("B", price=200000, score=15),
            _make_item("C", price=300000, score=10),
        ]
        text = render_general_compare("test", items)
        idx_a = text.index("A") if "A" in text else -1
        idx_b = text.index("B") if "B" in text else -1
        idx_c = text.index("C") if "C" in text else -1
        self.assertTrue(idx_a >= 0)
        self.assertTrue(idx_b > idx_a)
        self.assertTrue(idx_c > idx_b)

    # --- Side effect guards ---

    def test_no_phone_asking_in_response(self):
        items = [_make_item("Sofa", price=5000000)]
        text = render_general_compare("gợi ý sofa", items)
        self.assertNotIn("số điện thoại", text.lower())
        self.assertNotIn("phone", text.lower())

    def test_no_lead_creation_language(self):
        items = [_make_item("Sofa", price=5000000)]
        text = render_general_compare("gợi ý sofa", items)
        self.assertNotIn("đặt hàng", text.lower())
        self.assertNotIn("purchase request", text.lower())
        self.assertNotIn("liên hệ nhân viên", text.lower())


if __name__ == "__main__":
    unittest.main()
