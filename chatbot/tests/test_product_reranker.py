import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.product_reranker import analyze_product_query, rerank_product_results
from app.retrievers import RetrievalResult


def _product(
    doc_id: str,
    category: str,
    price: float,
    score: float,
    text: str = "",
    material: str = "",
) -> RetrievalResult:
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=doc_id,
        text=text or doc_id,
        source=f"https://example.test/{doc_id}",
        score=score,
        metadata={
            "doc_type": "product",
            "category": category,
            "price": price,
            "material": material,
            "canonical_url": f"https://example.test/{doc_id}",
        },
    )


def _doc(doc_id: str) -> RetrievalResult:
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=doc_id,
        text=doc_id,
        source=f"https://example.test/{doc_id}",
        score=50.0,
        metadata={"doc_type": "policy"},
    )


class ProductRerankerTests(unittest.TestCase):
    def test_price_rerank_promotes_item_under_max_price(self):
        hits = [
            _product("expensive-rug", "Thảm", 3_000_000, 100.0),
            _product("cheap-rug", "Thảm", 1_000_000, 1.0),
        ]

        reranked = rerank_product_results(hits, "Có thảm dưới 2 triệu không?", k=2)

        self.assertEqual(reranked[0].doc_id, "cheap-rug")

    def test_range_price_rerank_promotes_item_inside_range(self):
        hits = [
            _product("premium-table", "Bàn trà", 5_000_000, 100.0),
            _product("range-table", "Bàn trà", 2_000_000, 1.0),
        ]

        reranked = rerank_product_results(hits, "Có bàn trà từ 1 đến 3 triệu không?", k=2)

        self.assertEqual(reranked[0].doc_id, "range-table")

    def test_multi_category_coverage_includes_low_score_category_candidate(self):
        hits = [
            _product("table-1", "Bàn trà", 2_000_000, 100.0),
            _product("table-2", "Bàn trà", 2_500_000, 90.0),
            _product("shelf-1", "Kệ", 4_000_000, 1.0),
        ]

        reranked = rerank_product_results(hits, "Có bàn trà nào hợp với kệ tivi không?", k=2)

        self.assertEqual({hit.metadata["category"] for hit in reranked}, {"Bàn trà", "Kệ"})

    def test_material_boost_promotes_matching_material_or_text(self):
        hits = [
            _product("metal-shelf", "Kệ", 3_000_000, 100.0, text="ke tivi kim loai"),
            _product("wood-shelf", "Kệ", 3_500_000, 1.0, text="ke tivi go tu nhien", material="gỗ"),
        ]

        reranked = rerank_product_results(hits, "Có kệ tivi gỗ không?", k=2)

        self.assertEqual(reranked[0].doc_id, "wood-shelf")

    def test_non_product_docs_do_not_crash_and_follow_products(self):
        hits = [
            _doc("policy"),
            _product("cheap-rug", "Thảm", 1_000_000, 1.0),
        ]

        reranked = rerank_product_results(hits, "Có thảm dưới 2 triệu không?", k=2)

        self.assertEqual([hit.doc_id for hit in reranked], ["cheap-rug", "policy"])

    def test_price_fallback_returns_results_when_no_item_satisfies_price(self):
        hits = [
            _product("expensive-rug", "Thảm", 3_000_000, 100.0),
            _product("premium-rug", "Thảm", 4_000_000, 90.0),
        ]

        reranked = rerank_product_results(hits, "Có thảm dưới 2 triệu không?", k=2)

        self.assertEqual(len(reranked), 2)
        self.assertEqual({hit.doc_id for hit in reranked}, {"expensive-rug", "premium-rug"})

    def test_query_analysis_detects_material_and_room_style_terms(self):
        analysis = analyze_product_query("Tôi cần đồ decor nhỏ gọn cho căn hộ")

        self.assertIn("decor", analysis.room_style_terms)
        self.assertIn("nho gon", analysis.room_style_terms)
        self.assertTrue(analysis.has_complex_intent)


if __name__ == "__main__":
    unittest.main()
