import unittest

from app.purchase_request import build_purchase_request_draft
from app.sales_slots import extract_sales_slots, score_lead
from app.sales_state import (
    SalesConversationState,
    apply_message_to_state,
    consultation_missing_slots,
    known_consultation_slots,
    next_best_action,
    resolve_product_reference,
    update_recommended_products,
)


PRODUCTS = [
    {"sku": "SF-700", "product_name": "Sofa Nami", "source_url": "https://shop.test/sofa-nami", "price": 700000},
    {"sku": "TB-900", "product_name": "Bàn Osaka", "source_url": "https://shop.test/ban-osaka", "price": 900000},
]


class SalesStateTests(unittest.TestCase):
    def make_state(self):
        state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-a")
        update_recommended_products(state, PRODUCTS)
        return state

    def test_resolve_position_references(self):
        state = self.make_state()

        self.assertEqual(resolve_product_reference("P1", state).product["sku"], "SF-700")
        self.assertEqual(resolve_product_reference("p2", state).product["sku"], "TB-900")
        self.assertEqual(resolve_product_reference("mẫu thứ 2", state).product["sku"], "TB-900")

    def test_resolve_sku_name_and_price(self):
        state = self.make_state()

        self.assertEqual(resolve_product_reference("lấy SKU TB-900", state).product["sku"], "TB-900")
        self.assertEqual(resolve_product_reference("mình chọn Osaka", state).product["sku"], "TB-900")
        self.assertEqual(resolve_product_reference("cái 700k", state).product["sku"], "SF-700")

    def test_extract_phone_email_quantity(self):
        slots = extract_sales_slots("Mình lấy 2 cái, số 0901 234 567, email buyer@example.com")

        self.assertEqual(slots["phone"], "0901234567")
        self.assertEqual(slots["email"], "buyer@example.com")
        self.assertEqual(slots["quantity"], 2)

    def test_lead_scoring_hot_with_contact_intent_product(self):
        slots = extract_sales_slots("Mình mua 1 cái, số 0901234567, giao Hà Nội")
        score, status = score_lead(slots, has_selected_product=True)

        self.assertGreaterEqual(score, 7)
        self.assertEqual(status, "hot")

    def test_purchase_draft_statuses(self):
        state = self.make_state()

        self.assertEqual(build_purchase_request_draft(state, "Mình muốn mua")["status"], "needs_product")
        apply_message_to_state(state, "Mình chọn P1")
        self.assertEqual(build_purchase_request_draft(state, "Mình muốn mua")["status"], "needs_contact")
        self.assertEqual(build_purchase_request_draft(state, "Số mình 0901234567")["status"], "draft")

    def test_cancel_intent_does_not_create_active_draft(self):
        state = self.make_state()
        apply_message_to_state(state, "Mình lấy P1")

        draft = build_purchase_request_draft(state, "Thôi không mua nữa")

        self.assertEqual(draft["status"], "cancelled")

    def test_product_inquiry_does_not_create_hot_lead(self):
        state = self.make_state()
        result = apply_message_to_state(state, "Có mẫu sofa nào nhỏ không?")

        self.assertEqual(result["slots"]["intent"], "product_inquiry")
        self.assertEqual(state.lead_status, "cold")

    def test_consultation_stage_missing_slots_and_next_action(self):
        state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-discover")
        result = apply_message_to_state(state, "Tôi muốn mua sofa")

        self.assertEqual(state.current_stage, "confirm")
        self.assertIn("room_or_space", consultation_missing_slots(state))
        self.assertIn("budget", consultation_missing_slots(state))
        self.assertEqual(result["next_best_action"], "ask_discovery_question")
        self.assertEqual(next_best_action(state, result["slots"]), "ask_discovery_question")

    def test_consultation_known_slots_include_constraints(self):
        state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-known")
        apply_message_to_state(state, "Sofa phòng khách, nhà có mèo, cần dễ vệ sinh")

        known = known_consultation_slots(state)
        self.assertEqual(known["room"], "phòng khách")
        self.assertTrue(known["pets"])
        self.assertTrue(known["easy_clean"])
        self.assertIn("constraints", known)

    def test_objection_moves_to_handle_objection_stage(self):
        state = self.make_state()
        result = apply_message_to_state(state, "Mẫu này đắt quá")

        self.assertEqual(state.current_stage, "handle_objection")
        self.assertEqual(result["next_best_action"], "handle_objection")
        self.assertEqual(state.slots["objection_type"], "too_expensive")


if __name__ == "__main__":
    unittest.main()
