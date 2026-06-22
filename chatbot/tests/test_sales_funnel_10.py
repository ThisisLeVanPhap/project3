import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.product_answer_renderer import render_product_answer  # noqa: E402
from app.purchase_intent_score import HANDOFF_READY, score_purchase_intent  # noqa: E402
from app.retrieval_service import format_context, search_hits, should_allow_retrieval  # noqa: E402
from app.retrievers import RetrievalResult  # noqa: E402
from app.sales_nlu import BUY_INTENT, COMPARE, DISCOVERY, classify_sales_nlu  # noqa: E402
from app.sales_state import SalesConversationState, apply_message_to_state, update_recommended_products  # noqa: E402
from app.sales_templates import render_comparison_template, render_off_topic_redirect_template  # noqa: E402


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query: str, k: int = 4):
        self.calls.append({"query": query, "k": k})
        return self.hits[:k]


def _product(doc_id, name, category, price=1_200_000, sku="", material="", url=None):
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=name,
        text=f"{name} {category} {material}",
        source=url or f"https://example.test/{doc_id}",
        score=10.0,
        metadata={
            "doc_type": "product",
            "product_name": name,
            "category": category,
            "price": price,
            "currency": "VND",
            "sku": sku,
            "material": material,
            "source_url": url or f"https://example.test/{doc_id}",
        },
    )


def _context(products):
    return format_context(list(products), max_chars=500)


class SalesFunnel10Tests(unittest.TestCase):
    def test_hybrid_nlu_rule_layer(self):
        self.assertEqual(classify_sales_nlu("Co ban tra nao khong?").intent, DISCOVERY)
        self.assertEqual(classify_sales_nlu("so sanh 2 cai nay").intent, COMPARE)
        self.assertEqual(classify_sales_nlu("Toi muon mua P1").intent, BUY_INTENT)

    def test_broad_query_retrieves_before_missing_info(self):
        retriever = FakeRetriever([
            _product("ban-tra-1", "Ban tra Osaka", "Ban tra", 1_200_000, "BT-1"),
        ])

        self.assertTrue(should_allow_retrieval("Co ban tra nao khong?", "discover", {}))
        hits = search_hits(retriever, "Co ban tra nao khong?", k=3)
        answer = render_product_answer("Co ban tra nao khong?", _context(hits))

        self.assertIn("Ban tra Osaka", answer)
        self.assertNotIn("chua tim thay", answer.lower())

    def test_material_query_returns_real_kb_product(self):
        retriever = FakeRetriever([
            _product("tu-go-1", "Tu go cong nghiep Mito", "Tu", 4_800_000, "TU-1", "go cong nghiep"),
        ])

        hits = search_hits(retriever, "San pham nao bang go cong nghiep?", k=3)
        answer = render_product_answer("San pham nao bang go cong nghiep?", _context(hits))

        self.assertIn("Tu go cong nghiep Mito", answer)
        self.assertIn("TU-1", answer)

    def test_recommendation_template_uses_only_available_fields(self):
        product = _product("ban-1", "Ban an Rio", "Ban an", 3_000_000, "BA-1", url="https://example.test/ban-1")
        answer = render_product_answer("Tu van ban an", _context([product]))

        self.assertIn("Ban an Rio", answer)
        self.assertIn("3.000.000", answer)
        self.assertIn("BA-1", answer)
        self.assertIn("https://example.test/ban-1", answer)
        self.assertNotIn("bao hanh 12", answer.lower())

    def test_multi_turn_slot_keeps_category_and_adds_price(self):
        state = SalesConversationState()
        apply_message_to_state(state, "Tu van sofa")
        apply_message_to_state(state, "duoi 5 trieu")

        self.assertEqual(state.slots["product_category"], "Sofa")
        self.assertEqual(state.slots["price_max"], 5_000_000)

    def test_user_changes_product_category(self):
        state = SalesConversationState()
        apply_message_to_state(state, "Tu van sofa")
        apply_message_to_state(state, "thoi doi sang ban an")

        self.assertEqual(state.slots["product_category"], "Bàn ăn")
        self.assertNotEqual(state.slots["product_category"], "Sofa")

    def test_comparison_uses_last_products(self):
        state = SalesConversationState()
        update_recommended_products(state, [
            {"product_name": "Ban A", "price": "1000000", "material": "go", "sku": "A"},
            {"product_name": "Ban B", "price": "1200000", "material": "kinh", "sku": "B"},
        ])

        answer = render_comparison_template("so sanh 2 cai nay", state.last_recommended_products)

        self.assertIn("Ban A", answer)
        self.assertIn("Ban B", answer)
        self.assertIn("1000000", answer)

    def test_cta_does_not_create_purchase_score_ready(self):
        scored = score_purchase_intent({"nlu_intent": "DISCOVERY"}, has_selected_product=False, has_contact=False)

        self.assertFalse(scored.create_lead)
        self.assertFalse(scored.handoff_ready)

    def test_purchase_scoring_handoff_ready(self):
        slots = {
            "nlu_intent": "BUY_INTENT",
            "has_ship_or_stock_question": True,
            "quantity": 1,
            "phone": "0901234567",
            "address": "Ha Noi",
        }
        scored = score_purchase_intent(slots, has_selected_product=True)

        self.assertGreaterEqual(scored.score, HANDOFF_READY)
        self.assertTrue(scored.handoff_ready)

    def test_off_topic_redirect_does_not_clear_context(self):
        state = SalesConversationState()
        apply_message_to_state(state, "Tu van sofa")
        reply = render_off_topic_redirect_template()

        self.assertIn("sofa", state.slots.get("product_category", "").lower())
        self.assertIn("noi that", reply)


if __name__ == "__main__":
    unittest.main()
