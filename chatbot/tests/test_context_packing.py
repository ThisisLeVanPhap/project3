import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.context_packing import (  # noqa: E402
    format_grounded_context,
    format_price,
    get_product_source_url,
)
from app.retrievers import RetrievalResult  # noqa: E402
from app.sales_flow import build_sales_prefix  # noqa: E402


def _product(doc_id: str, **metadata):
    base_metadata = {
        "doc_type": "product",
        "product_name": "Rèm sáo gỗ GHO-610",
        "category": "Rèm",
        "price": 700000,
        "currency": "VND",
        "source_url": "https://example.test/rem-sao-go",
    }
    base_metadata.update(metadata)
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=base_metadata.get("product_name") or doc_id,
        text="Rèm sáo gỗ phù hợp cửa sổ phòng khách.",
        source=f"kb://{doc_id}",
        score=1.0,
        metadata=base_metadata,
    )


class ContextPackingTests(unittest.TestCase):
    def test_product_context_contains_structured_fields_and_source_url(self):
        context = format_grounded_context([_product("p1")])

        self.assertIn("[P1]", context)
        self.assertIn("Tên sản phẩm: Rèm sáo gỗ GHO-610", context)
        self.assertIn("Danh mục: Rèm", context)
        self.assertIn("Giá: 700.000 VND", context)
        self.assertIn("Link nguồn: https://example.test/rem-sao-go", context)

    def test_source_url_fallback_order(self):
        self.assertEqual(
            get_product_source_url(_product("p1", source_url="", canonical_url="https://example.test/canonical")),
            "https://example.test/canonical",
        )
        self.assertEqual(
            get_product_source_url(_product("p2", source_url="", canonical_url="", url="https://example.test/url")),
            "https://example.test/url",
        )
        hit = _product("p3", source_url="", canonical_url="", url="")
        self.assertEqual(get_product_source_url(hit), "kb://p3")

    def test_dedupe_by_source_url(self):
        duplicate = _product("p2", product_name="Duplicate Rèm", source_url="https://example.test/rem-sao-go")

        context = format_grounded_context([_product("p1"), duplicate])

        self.assertEqual(context.count("[P1]"), 1)
        self.assertNotIn("[P2]", context)
        self.assertNotIn("Duplicate Rèm", context)

    def test_missing_fields_do_not_print_none(self):
        context = format_grounded_context([
            _product("p1", price=None, material=None, color=None, dimensions=None)
        ])

        self.assertNotIn("None", context)
        self.assertNotIn("Giá:", context)
        self.assertNotIn("Chất liệu:", context)
        self.assertNotIn("Màu sắc:", context)

    def test_non_product_hit_is_formatted(self):
        hit = RetrievalResult(
            doc_id="d1",
            chunk_id="d1#0",
            title="Chính sách đổi trả",
            text="Đổi trả theo điều kiện cửa hàng.",
            source="https://example.test/policy",
            metadata={"doc_type": "policy"},
        )

        context = format_grounded_context([hit])

        self.assertIn("[D1]", context)
        self.assertIn("Tiêu đề: Chính sách đổi trả", context)
        self.assertIn("Link nguồn: https://example.test/policy", context)

    def test_description_is_truncated_safely(self):
        hit = _product("p1")
        hit = hit.model_copy(update={"text": "x" * 200})

        context = format_grounded_context([hit], max_chars_per_product=40)

        self.assertIn("Mô tả ngắn:", context)
        self.assertIn("...", context)
        self.assertLess(len(context), 500)

    def test_format_price_handles_vnd_and_missing_values(self):
        self.assertEqual(format_price(1200000, "VND"), "1.200.000 VND")
        self.assertEqual(format_price(None, "VND"), "")

    def test_sales_prefix_contains_grounded_answer_contract(self):
        prefix = build_sales_prefix("propose", {})

        self.assertIn("GROUNDED PRODUCT ANSWER CONTRACT", prefix)
        self.assertIn("[P#]", prefix)
        self.assertIn("Tên sản phẩm [P#]", prefix)
        self.assertIn("Link nguồn", prefix)
        self.assertIn("Mình chưa thấy thông tin này trong dữ liệu hiện có.", prefix)
        self.assertIn("Trạng thái trên trang sản phẩm: InStock", prefix)
        self.assertIn("Ước tính từ các sản phẩm đang liệt kê.", prefix)


if __name__ == "__main__":
    unittest.main()
