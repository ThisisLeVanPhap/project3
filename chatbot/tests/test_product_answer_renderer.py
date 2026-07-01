import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.answer_evaluator import evaluate_answer_grounding  # noqa: E402
from app.product_answer_renderer import (
    detect_answer_intent,
    render_comparison_answer,
    render_listing_answer,
    render_missing_or_policy_answer,
    render_no_context_answer,
    render_product_answer,
)


CONTEXT = (
    "[P1]\n"
    "Tên sản phẩm: Rèm cuốn tranh cao cấp GHO-607\n"
    "Danh mục: Rèm\n"
    "Giá: 700.000 VND\n"
    "Chất liệu: Vải\n"
    "Kích thước: 1200 x 600 x 440mm\n"
    "SKU: GHO-607\n"
    "Tình trạng: https://schema.org/InStock\n"
    "Link nguồn: https://example.test/rem-cuon\n\n"
    "[P2]\n"
    "Tên sản phẩm: Rèm sáo gỗ GHO-618\n"
    "Danh mục: Rèm\n"
    "Giá: 1.700.000 VND\n"
    "Chất liệu: Gỗ\n"
    "Link nguồn: https://example.test/rem-sao-go"
)


QUERY_SPEC = {
    "id": "listing_001",
    "query": "Có rèm nào dưới 1 triệu không?",
    "type": "price_constraint",
    "expected_behavior": {
        "must_have_citation": True,
        "must_mention_price": True,
        "should_include_source_link": True,
        "must_not_fabricate_missing_fields": True,
    },
}


class ProductAnswerRendererTests(unittest.TestCase):
    def test_detect_answer_intent(self):
        self.assertEqual(detect_answer_intent("So sánh rèm cuốn và rèm sáo"), "comparison")
        self.assertEqual(detect_answer_intent("Có rèm dưới 1 triệu không?"), "price_constraint")
        self.assertEqual(detect_answer_intent("Sản phẩm này bảo hành không?"), "missing_field")
        self.assertEqual(detect_answer_intent("Tôi muốn mua điện thoại"), "out_of_scope_or_policy")

    def test_listing_answer_contains_required_fields(self):
        answer = render_product_answer("Có rèm nào dưới 1 triệu không?", CONTEXT)

        self.assertIn("Rèm cuốn tranh cao cấp GHO-607 [P1]", answer)
        self.assertIn("Giá: 700.000 VND", answer)
        self.assertIn("Link nguồn: https://example.test/rem-cuon", answer)
        self.assertNotIn("None", answer)

    def test_price_answer_uses_only_context_prices(self):
        answer = render_product_answer("Có rèm dưới 1 triệu không?", CONTEXT)

        self.assertIn("700.000 VND", answer)
        self.assertNotIn("900.000", answer)
        self.assertNotIn("Tổng", answer)

    def test_listing_answer_has_diacritic_cta_and_no_banned_patterns(self):
        answer = render_listing_answer(
            "ghế",
            [{"product_name": "Ghế văn phòng", "pid": "P1", "price": "2.300.000 VND", "category": "Ghế"}],
        )

        banned = [
            "Ban muon",
            "Phu hop vi",
            "khop nhom",
            "san pham",
        ]
        for b in banned:
            self.assertNotIn(b, answer)

        self.assertIn("Bạn muốn mình lọc tiếp", answer)
        self.assertIn("Phù hợp vì:", answer)

    def test_comparison_answer_has_table_citations_and_links(self):
        answer = render_product_answer("So sánh rèm cuốn và rèm sáo", CONTEXT, max_products=2)

        self.assertIn("| Sản phẩm | Giá | Danh mục |", answer)
        self.assertIn("[P1]", answer)
        self.assertIn("[P2]", answer)
        self.assertIn("https://example.test/rem-cuon", answer)
        self.assertIn("https://example.test/rem-sao-go", answer)

    def test_missing_field_fallback_does_not_fabricate_policy(self):
        answer = render_missing_or_policy_answer("Sản phẩm này bảo hành bao lâu?", CONTEXT)

        self.assertIn("Mình chưa thấy thông tin này trong dữ liệu hiện có.", answer)
        self.assertNotIn("12 tháng", answer)
        self.assertNotIn("miễn phí vận chuyển", answer)

    def test_out_of_scope_does_not_recommend_products(self):
        answer = render_product_answer("Tôi muốn mua điện thoại", CONTEXT)

        self.assertIn("Mình chưa thấy thông tin này trong dữ liệu hiện có.", answer)
        self.assertNotIn("Rèm cuốn", answer)

    def test_availability_only_renders_schema_status(self):
        answer = render_product_answer("Có rèm không?", CONTEXT)

        self.assertIn("Trạng thái trên trang sản phẩm: InStock", answer)
        self.assertNotIn("showroom", answer.lower())

    def test_sales_templates_no_banned_patterns_and_diacritic_cta(self):
        """Light wording test for sales_templates user-facing output."""
        from app import sales_templates as st

        banned = ["Ban muon", "Phu hop vi", "khop nhom", "san pham"]

        # render_recommendation_template
        rec = st.render_recommendation_template(
            "ghế",
            [{"product_name": "Ghế văn phòng", "pid": "P1", "price": "2.300.000 VND"}],
        )
        for b in banned:
            self.assertNotIn(b, rec)
        self.assertIn("Bạn muốn mình lọc tiếp", rec)

        # render_missing_info_template
        miss = st.render_missing_info_template(["product_category"])
        for b in banned:
            self.assertNotIn(b, miss)
        self.assertIn("Bạn đang tìm", miss)

    def test_no_context_answer(self):
        answer = render_no_context_answer("Có sofa không?")

        self.assertIn("Mình chưa tìm thấy sản phẩm phù hợp", answer)

    def test_template_output_passes_evaluator(self):
        answer = render_product_answer(QUERY_SPEC["query"], CONTEXT)

        result = evaluate_answer_grounding(QUERY_SPEC, CONTEXT, answer)

        self.assertTrue(result["pass"])


if __name__ == "__main__":
    unittest.main()
