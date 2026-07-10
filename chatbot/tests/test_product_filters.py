import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.product_filters import (
    apply_price_constraint,
    diversify_by_category,
    filter_by_category,
    parse_price_constraint,
    parse_product_categories,
)
from app.retrievers.schemas import RetrievalResult


def _result(doc_id: str, price=None, category=None):
    metadata = {"doc_type": "product"}
    if price is not None:
        metadata["price"] = price
    if category is not None:
        metadata["category"] = category
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=doc_id,
        text=doc_id,
        source=f"kb://{doc_id}",
        metadata=metadata,
    )


class ProductFilterTests(unittest.TestCase):
    def test_parse_under_one_million(self):
        constraint = parse_price_constraint("Có rèm nào dưới 1 triệu không?")
        self.assertEqual(constraint.max_price, 1_000_000)
        self.assertIsNone(constraint.min_price)

    def test_parse_under_500k(self):
        constraint = parse_price_constraint("đèn trang trí dưới 500k")
        self.assertEqual(constraint.max_price, 500_000)

    def test_parse_between_one_and_two_million(self):
        constraint = parse_price_constraint("sofa từ 1 đến 2 triệu")
        self.assertEqual(constraint.min_price, 1_000_000)
        self.assertEqual(constraint.max_price, 2_000_000)

    def test_parse_above_five_million(self):
        constraint = parse_price_constraint("bàn ăn trên 5 triệu")
        self.assertEqual(constraint.min_price, 5_000_000)

    def test_parse_around_one_million(self):
        constraint = parse_price_constraint("tầm 1 triệu")
        self.assertEqual(constraint.target_price, 1_000_000)

    def test_parse_cheapest_sort(self):
        constraint = parse_price_constraint("rèm rẻ nhất")
        self.assertEqual(constraint.sort, "asc")

    def test_apply_price_constraint_filters_products_under_one_million(self):
        results = [_result("expensive", 1_400_000), _result("ok", 700_000), _result("unknown")]
        constraint = parse_price_constraint("rèm dưới 1 triệu")

        filtered = apply_price_constraint(results, constraint)

        self.assertEqual([hit.doc_id for hit in filtered], ["ok", "unknown"])
        self.assertLessEqual(filtered[0].metadata["price"], 1_000_000)

    def test_apply_price_constraint_falls_back_when_filter_empty(self):
        results = [_result("expensive", 1_400_000), _result("premium", 2_000_000)]
        constraint = parse_price_constraint("rèm dưới 500k")

        filtered = apply_price_constraint(results, constraint)

        self.assertEqual(filtered, results)

    def test_parse_product_categories_keeps_rem_and_den(self):
        categories = parse_product_categories("rem hoac den trang tri duoi 1 trieu")

        self.assertIn("Rèm", categories)
        self.assertIn("Đèn", categories)
        self.assertLess(categories.index("Rèm"), categories.index("Đèn"))

    def test_parse_product_categories_does_not_read_den_from_den_preposition(self):
        categories = parse_product_categories("t dang nghi den viec mua noi that cho nha moi")

        self.assertNotIn("Đèn", categories)

        lamp_categories = parse_product_categories("t muon mua den trang tri cho phong khach")
        self.assertIn("Đèn", lamp_categories)

    def test_parse_product_categories_distinguishes_sofa_and_chair(self):
        categories = parse_product_categories("so sanh sofa va ghe thu gian")

        self.assertIn("Sofa", categories)
        self.assertIn("Ghế", categories)

    def test_parse_product_categories_matches_ban_tra_and_ke_tivi(self):
        categories = parse_product_categories("ban tra hop voi ke tivi")

        self.assertEqual(categories, ["Bàn trà", "Kệ"])

    def test_parse_product_categories_matches_work_desk(self):
        categories = parse_product_categories("toi muon ban lam viec nho gon")

        self.assertIn("Bàn làm việc", categories)
        self.assertNotIn("Bàn ăn", categories)

    def test_parse_product_categories_matches_study_desk_alias(self):
        categories = parse_product_categories("ban hoc cho tre em")

        self.assertEqual(categories, ["Bàn làm việc"])

    def test_parse_product_categories_ke_sach_and_work_desk(self):
        categories = parse_product_categories("ke sach va ban lam viec")

        self.assertIn("Kệ", categories)
        self.assertIn("Bàn làm việc", categories)

    def test_parse_product_categories_maps_decor_to_decoration(self):
        categories = parse_product_categories("do decor phong khach")

        self.assertIn("Đồ trang trí", categories)

    def test_filter_by_category_keeps_only_matching(self):
        results = [
            _result("ghe-1", price=700_000, category="Ghế"),
            _result("den-1", price=600_000, category="Đèn"),
            _result("vach-1", price=500_000, category="Đồ trang trí"),
        ]
        filtered = filter_by_category(results, "Ghế")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].doc_id, "ghe-1")

    def test_filter_by_category_empty_when_no_match(self):
        results = [
            _result("den-1", price=600_000, category="Đèn"),
            _result("vach-1", price=500_000, category="Đồ trang trí"),
        ]
        filtered = filter_by_category(results, "Ghế")
        self.assertEqual(len(filtered), 0)

    def test_filter_by_category_does_not_pad_count(self):
        results = [
            _result("ghe-1", price=700_000, category="Ghế"),
            _result("ghe-2", price=800_000, category="Ghế"),
            _result("den-1", price=600_000, category="Đèn"),
        ]
        filtered = filter_by_category(results, "Ghế")
        self.assertEqual(len(filtered), 2)
        self.assertNotIn("den-1", [r.doc_id for r in filtered])

    def test_filter_by_category_matches_by_product_name_too(self):
        results = [
            RetrievalResult(
                doc_id="ghe-vp", chunk_id="ghe-vp#0", title="Ghế văn phòng Ergo",
                text="Ghế văn phòng Ergo", source="kb://ghe-vp", score=10.0,
                metadata={"doc_type": "product", "product_name": "Ghế văn phòng Ergo", "category": "Ghế"},
            ),
            RetrievalResult(
                doc_id="den-tha", chunk_id="den-tha#0", title="Đèn thả trần",
                text="Đèn thả trần", source="kb://den-tha", score=9.0,
                metadata={"doc_type": "product", "product_name": "Đèn thả trần", "category": "Đèn"},
            ),
        ]
        filtered = filter_by_category(results, "Ghế")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].doc_id, "ghe-vp")


class DiversifyTests(unittest.TestCase):
    def test_diversify_by_category_includes_requested_categories(self):
        results = [
            _result("rem-1", 700_000, "Rèm"),
            _result("rem-2", 800_000, "Rèm"),
            _result("den-1", 600_000, "Đèn"),
            _result("den-2", 500_000, "Đèn"),
        ]

        diversified = diversify_by_category(results, ["Rèm", "Đèn"], k=3)

        self.assertEqual(diversified[0].doc_id, "rem-1")
        self.assertIn("den-1", [hit.doc_id for hit in diversified[:3]])


if __name__ == "__main__":
    unittest.main()
