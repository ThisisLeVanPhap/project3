import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.retrieval_service import search_hits
from app.retrievers import RetrievalResult


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query: str, k: int = 4):
        self.calls.append({"query": query, "k": k})
        return self.hits[:k]


def _product(doc_id: str, price: int, category: str = "Rèm") -> RetrievalResult:
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=doc_id,
        text=doc_id,
        source=f"kb://{doc_id}",
        score=10.0,
        metadata={"doc_type": "product", "price": price, "category": category},
    )


def _doc(doc_id: str) -> RetrievalResult:
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=doc_id,
        text=doc_id,
        source=f"kb://{doc_id}",
        score=10.0,
        metadata={"doc_type": "policy"},
    )


class ProductFilterIntegrationTests(unittest.TestCase):
    def test_price_query_filters_product_hits_after_wide_search(self):
        retriever = FakeRetriever([
            _product("expensive", 1_400_000),
            _product("boundary", 1_000_000),
            _product("cheap", 700_000),
        ])

        hits = search_hits(retriever, "Có rèm nào dưới 1 triệu không?", k=2)

        self.assertEqual(retriever.calls[0]["k"], 200)
        self.assertEqual([hit.doc_id for hit in hits], ["boundary", "cheap"])
        self.assertTrue(all(hit.metadata["price"] <= 1_000_000 for hit in hits))

    def test_query_without_price_constraint_keeps_existing_search_behavior(self):
        retriever = FakeRetriever([
            _product("first", 1_400_000),
            _product("second", 700_000),
            _product("third", 500_000),
        ])

        hits = search_hits(retriever, "Có rèm cửa không?", k=2)

        self.assertEqual(retriever.calls[0]["k"], 2)
        self.assertEqual([hit.doc_id for hit in hits], ["first", "second"])

    def test_non_product_docs_do_not_crash_and_follow_filtered_products(self):
        retriever = FakeRetriever([
            _product("expensive", 1_400_000),
            _doc("policy"),
            _product("cheap", 700_000),
        ])

        hits = search_hits(retriever, "Có rèm nào dưới 1 triệu không?", k=3)

        self.assertEqual([hit.doc_id for hit in hits], ["cheap", "policy"])

    def test_empty_product_filter_falls_back_to_original_results(self):
        retriever = FakeRetriever([
            _product("expensive", 1_400_000),
            _product("premium", 2_000_000),
            _doc("policy"),
        ])

        hits = search_hits(retriever, "Có rèm nào dưới 500k không?", k=3)

        self.assertEqual([hit.doc_id for hit in hits], ["expensive", "premium", "policy"])

    def test_multi_category_query_diversifies_product_results(self):
        retriever = FakeRetriever([
            _product("rem-1", 700_000, "Rèm"),
            _product("rem-2", 800_000, "Rèm"),
            _product("den-1", 600_000, "Đèn"),
            _product("den-2", 500_000, "Đèn"),
        ])

        hits = search_hits(retriever, "toi muon rem hoac den trang tri", k=3)

        self.assertEqual(retriever.calls[0]["k"], 200)
        self.assertEqual(hits[0].doc_id, "rem-1")
        self.assertIn("Đèn", [hit.metadata["category"] for hit in hits])

    def test_single_category_query_keeps_existing_search_behavior(self):
        retriever = FakeRetriever([
            _product("den-1", 600_000, "Đèn"),
            _product("den-2", 500_000, "Đèn"),
            _product("tham-1", 700_000, "Thảm"),
        ])

        hits = search_hits(retriever, "co den khong", k=2)

        self.assertEqual(retriever.calls[0]["k"], 2)
        self.assertEqual([hit.doc_id for hit in hits], ["den-1", "den-2"])

    def test_price_and_multi_category_work_together(self):
        retriever = FakeRetriever([
            _product("rem-expensive", 1_400_000, "Rèm"),
            _product("rem-cheap", 700_000, "Rèm"),
            _product("den-cheap", 600_000, "Đèn"),
            _product("den-expensive", 1_200_000, "Đèn"),
        ])

        hits = search_hits(retriever, "toi muon rem hoac den duoi 1 trieu", k=3)

        self.assertEqual([hit.doc_id for hit in hits[:2]], ["rem-cheap", "den-cheap"])
        self.assertTrue(all(hit.metadata["price"] <= 1_000_000 for hit in hits[:2]))


if __name__ == "__main__":
    unittest.main()
