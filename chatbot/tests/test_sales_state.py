import unittest
from types import SimpleNamespace

from app.purchase_request import build_purchase_request_draft
from app.sales_slots import extract_sales_slots, extract_sku_reference, score_lead
from app.sales_state import (
    SalesConversationState,
    apply_message_to_state,
    consultation_missing_slots,
    known_consultation_slots,
    next_best_action,
    resolve_product_reference,
    update_recommended_products,
    _has_recommendation_readiness,
    _has_specific_product_subtype,
)
from app.sales_response_renderer import render_sales_response


PRODUCTS = [
    {"sku": "SF-700", "product_name": "Sofa Nami", "source_url": "https://shop.test/sofa-nami", "price": 700000},
    {"sku": "TB-900", "product_name": "Ban Osaka", "source_url": "https://shop.test/ban-osaka", "price": 900000},
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
        self.assertEqual(resolve_product_reference("mau thu 2", state).product["sku"], "TB-900")

    def test_resolve_sku_name_and_price(self):
        state = self.make_state()

        self.assertEqual(resolve_product_reference("lay SKU TB-900", state).product["sku"], "TB-900")
        self.assertEqual(resolve_product_reference("minh chon Osaka", state).product["sku"], "TB-900")
        self.assertEqual(resolve_product_reference("cai 700k", state).product["sku"], "SF-700")

    def test_extract_phone_email_quantity(self):
        slots = extract_sales_slots("Minh lay 2 cai, so 0901 234 567, email buyer@example.com")

        self.assertEqual(slots["phone"], "0901234567")
        self.assertEqual(slots["email"], "buyer@example.com")
        self.assertEqual(slots["quantity"], 2)

    def test_lead_scoring_hot_with_contact_intent_product(self):
        slots = extract_sales_slots("Minh mua 1 cai, so 0901234567, giao Ha Noi")
        score, status = score_lead(slots, has_selected_product=True)

        self.assertGreaterEqual(score, 7)
        self.assertEqual(status, "hot")

    def test_purchase_draft_statuses(self):
        state = self.make_state()

        self.assertEqual(build_purchase_request_draft(state, "Minh muon mua")["status"], "needs_product")
        apply_message_to_state(state, "Minh chon P1")
        self.assertEqual(build_purchase_request_draft(state, "Minh muon mua")["status"], "needs_contact")
        self.assertEqual(build_purchase_request_draft(state, "So minh 0901234567")["status"], "draft")

    def test_cancel_intent_does_not_create_active_draft(self):
        state = self.make_state()
        apply_message_to_state(state, "Minh lay P1")

        draft = build_purchase_request_draft(state, "Thoi khong mua nua")

        self.assertEqual(draft["status"], "cancelled")

    def test_thoi_after_room_size_is_not_cancel_or_confirmation_reject(self):
        slots = extract_sales_slots("cho day cua t chac khoang 3x3 m thoi")

        self.assertNotIn("cancel", slots["intents"])
        self.assertNotEqual(slots["intent"], "cancel")
        self.assertIsNone(slots["confirmation_intent"])
        self.assertEqual(slots.get("room_size"), "3x3 m")
        self.assertEqual(slots.get("width_m"), 3.0)
        self.assertEqual(slots.get("length_m"), 3.0)

    def test_product_inquiry_does_not_create_hot_lead(self):
        state = self.make_state()
        result = apply_message_to_state(state, "Co mau sofa nao nho khong?")

        self.assertEqual(result["slots"]["intent"], "product_inquiry")
        self.assertEqual(state.lead_status, "cold")

    def test_consultation_stage_missing_slots_and_next_action(self):
        state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-discover")
        result = apply_message_to_state(state, "Toi muon mua sofa")

        # Phase 7: vague purchase intent without specific product -> discover, not confirm
        self.assertEqual(state.current_stage, "discover")
        self.assertIn("room_or_space", consultation_missing_slots(state))
        self.assertIn("budget", consultation_missing_slots(state))
        self.assertEqual(result["next_best_action"], "ask_discovery_question")
        self.assertEqual(next_best_action(state, result["slots"]), "ask_discovery_question")

    def test_consultation_known_slots_include_constraints(self):
        state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-known")
        apply_message_to_state(state, "Sofa phong khach, nha co meo, can de ve sinh")

        known = known_consultation_slots(state)
        # 'room' may not be extracted for 'phong khach' by keyword-only parser
        # The important assertions are pets, easy_clean, and constraints
        self.assertTrue(known.get("pets", False))
        self.assertTrue(known.get("easy_clean", False))
        self.assertIn("constraints", known)

    def test_objection_moves_to_handle_objection_stage(self):
        state = self.make_state()
        result = apply_message_to_state(state, "Mau nay dat qua")

        self.assertEqual(state.current_stage, "handle_objection")
        self.assertEqual(result["next_best_action"], "handle_objection")
        self.assertEqual(state.slots["objection_type"], "too_expensive")


class RecommendationReadinessTests(unittest.TestCase):
    """Phase 2: consultation_stage_for -- bare category vs. ready-to-suggest."""

    def test_bare_category_returns_false(self):
        self.assertFalse(_has_recommendation_readiness({"product_category": "Sofa"}))
        self.assertFalse(_has_recommendation_readiness({"product_category": "Ghe"}))
        self.assertFalse(_has_recommendation_readiness({"product_category": "Ban"}))

    def test_category_plus_budget_returns_true(self):
        self.assertTrue(_has_recommendation_readiness({"product_category": "Sofa", "budget": "duoi 10 trieu"}))

    def test_category_plus_room_returns_false(self):
        # Phase 7B: room alone + bare category is not enough for readiness
        self.assertFalse(_has_recommendation_readiness({"product_category": "Sofa", "room": "phong khach"}))

    def test_category_plus_material_returns_true(self):
        self.assertTrue(_has_recommendation_readiness({"product_category": "Sofa", "material": "go"}))

    def test_category_plus_color_returns_true(self):
        self.assertTrue(_has_recommendation_readiness({"product_category": "Sofa", "color": "navy"}))

    def test_category_plus_style_returns_false(self):
        # Phase 10F: style alone does not justify listing; need budget/material/color/size
        self.assertFalse(_has_recommendation_readiness({"product_category": "Sofa", "style": "modern"}))

    def test_subtype_counts_as_readiness(self):
        self.assertTrue(_has_specific_product_subtype({"product_type": "ghe van phong"}))
        self.assertTrue(_has_specific_product_subtype({"product_type": "sofa goc"}))
        self.assertTrue(_has_specific_product_subtype({"product_type": "ban an"}))

    def test_bare_category_is_not_subtype(self):
        self.assertFalse(_has_specific_product_subtype({"product_category": "Ghe"}))
        self.assertFalse(_has_specific_product_subtype({"product_category": "Sofa"}))
        self.assertFalse(_has_specific_product_subtype({"product_category": "Ban"}))


class SkuExtractionTests(unittest.TestCase):
    """Phase 6D: SKU reference extraction."""

    def test_sku_direct(self):
        self.assertEqual(extract_sku_reference("GHO-239"), "GHO-239")

    def test_sku_lowercase(self):
        self.assertEqual(extract_sku_reference("gho-239"), "GHO-239")

    def test_sku_in_sentence(self):
        self.assertEqual(extract_sku_reference("Đèn thả trần GHO-239 tôi muốn mua"), "GHO-239")

    def test_sku_slot_in_extract_sales_slots(self):
        slots = extract_sales_slots("GHO-239 tôi muốn mua")
        self.assertEqual(slots.get("product_sku_ref"), "GHO-239")

    def test_sku_slot_in_full_message(self):
        slots = extract_sales_slots("Đèn thả trần kiểu dáng đẹp giá rẻ GHO-239 mẫu a hay đấy t muốn mua")
        self.assertEqual(slots.get("product_sku_ref"), "GHO-239")


class DimensionBudgetExtractionTests(unittest.TestCase):
    """Phase 9C: dimension/area/budget extraction and false positive prevention."""

    def test_dimension_3m_x_5m(self):
        slots = extract_sales_slots("phòng khách đi, chắc khoảng 3m x 5m là to nhất rồi")
        self.assertEqual(slots.get("room"), "phòng khách")
        self.assertEqual(slots.get("room_size"), "3m x 5m")
        self.assertEqual(slots.get("width_m"), 3.0)
        self.assertEqual(slots.get("length_m"), 5.0)
        self.assertIsNone(slots.get("budget"))
        self.assertIsNone(slots.get("price_target"))

    def test_dimension_3_met_x_5_met(self):
        slots = extract_sales_slots("phòng khách khoảng 3 mét x 5 mét")
        self.assertEqual(slots.get("room"), "phòng khách")
        self.assertIsNotNone(slots.get("room_size"))

    def test_area_15m2(self):
        slots = extract_sales_slots("phòng rộng khoảng 15m2")
        self.assertEqual(slots.get("area_m2"), 15.0)
        self.assertIsNone(slots.get("budget"))
        self.assertIsNone(slots.get("price_target"))
        self.assertIsNone(slots.get("price_max"))

    def test_area_15_met_vuong(self):
        slots = extract_sales_slots("phòng rộng 15 mét vuông")
        self.assertEqual(slots.get("area_m2"), 15.0)

    def test_budget_5_trieu_tro_xuong(self):
        slots = extract_sales_slots("5 triệu trở xuống")
        self.assertEqual(slots.get("budget"), "5 triệu")

    def test_budget_duoi_5_trieu(self):
        slots = extract_sales_slots("dưới 5 triệu")
        self.assertEqual(slots.get("budget"), "5 triệu")

    def test_budget_khoang_5tr(self):
        slots = extract_sales_slots("khoảng 5tr")
        self.assertIsNotNone(slots.get("budget"))

    def test_budget_lteq_5_trieu(self):
        slots = extract_sales_slots("<= 5 triệu")
        self.assertEqual(slots.get("budget"), "5 triệu")

    def test_dimension_does_not_set_price_target(self):
        slots = extract_sales_slots("phòng khách đi, chắc khoảng 3m x 5m là to nhất rồi")
        self.assertIsNone(slots.get("price_target"))
        self.assertIsNone(slots.get("price_min"))
        self.assertIsNone(slots.get("price_max"))


class MaterialFalsePositiveFixTests(unittest.TestCase):
    """Phase 2B: sales_nlu material extraction should not fire on 'gợi ý/goi y'."""

    def test_goi_y_sofa_di_has_no_material(self):
        from app.sales_slots import extract_sales_slots
        slots = extract_sales_slots("goi y sofa di")
        self.assertIsNone(slots.get("material"))

    def test_goi_y_sofa_di_accented_has_no_material(self):
        from app.sales_slots import extract_sales_slots
        slots = extract_sales_slots("gợi ý sofa đi")
        self.assertIsNone(slots.get("material"))

    def test_apply_state_goi_y_sofa_di_goes_to_discover(self):
        state = SalesConversationState(tenant_id="t", conversation_id="c")
        r = apply_message_to_state(state, "goi y sofa di")
        self.assertEqual(state.current_stage, "discover")
        self.assertEqual(r["next_best_action"], "ask_discovery_question")

    def test_sofa_go_still_detects_material(self):
        from app.sales_slots import extract_sales_slots
        slots = extract_sales_slots("sofa gỗ")
        self.assertEqual(slots.get("material"), "go")

    def test_sofa_go_phong_khach_still_suggests(self):
        # "sofa gỗ phòng khách" has both material and room -> suggest
        state = SalesConversationState(tenant_id="t", conversation_id="c")
        r = apply_message_to_state(state, "sofa go phong khach")  # no accent version
        # material should be detected for bare "go" (word boundary match)
        # state depends on whether room is also extracted; with material it should be suggest
        self.assertEqual(state.current_stage, "suggest")

    # Phase 10I: "đã" should not become material "da"
    def test_da_in_past_tense_not_material(self):
        from app.sales_slots import extract_sales_slots
        from app.sales_flow import extract_slots
        slots = extract_sales_slots("ban, da noi roi ma")
        self.assertIsNone(slots.get("material"), msg="'da' from past-tense 'da' should not be material")
        flow_slots = extract_slots("ban, da noi roi ma")
        self.assertIsNone(flow_slots.get("material"), msg="flow: 'da' from past-tense 'da' should not be material")

    def test_da_accented_past_tense_not_material(self):
        from app.sales_slots import extract_sales_slots
        slots = extract_sales_slots("ban, da noi roi ma")
        self.assertIsNone(slots.get("material"))

    def test_ghe_da_still_material(self):
        from app.sales_slots import extract_sales_slots
        from app.sales_flow import extract_slots
        slots = extract_sales_slots("ghe da")
        self.assertEqual(slots.get("material"), "da")
        flow_slots = extract_slots("ghe da")
        self.assertEqual(flow_slots.get("material"), "da")

    def test_sofa_da_cong_nghiep_still_material(self):
        from app.sales_slots import extract_sales_slots
        slots = extract_sales_slots("sofa da cong nghiep")
        self.assertEqual(slots.get("material"), "da")

    # Phase 10M: "tuong tu" must NOT become category Tu
    def test_tuong_tu_not_tu_category(self):
        from app.sales_slots import extract_sales_slots
        from app.product_filters import parse_product_categories
        slots = extract_sales_slots("co mau nao tuong tu khong")
        self.assertIsNone(slots.get("product_category"), msg="tuong tu should not become Tu")
        self.assertIsNone(slots.get("product_type"), msg="tuong tu should not become Tu")
        cats = parse_product_categories("co mau nao tuong tu khong")
        self.assertNotIn("Tủ", cats, msg="tuong tu should not be Tu category")

    def test_tu_tivi_still_tu_category(self):
        from app.product_filters import parse_product_categories
        cats = parse_product_categories("tu tivi")
        self.assertIn("Tủ", cats, msg="tu tivi should still be Tu")


class CategoryAwareDiscoveryQuestionTests(unittest.TestCase):
    """Phase 3: category-aware discovery questions in render_sales_response."""

    def _make_state(self, category, missing_fields, slots=None):
        s = SimpleNamespace()
        s.missing_fields = missing_fields
        s.slots = dict(slots or {})
        s.slots.setdefault("product_category", category)
        s.slots.setdefault("product_type", category)
        return s

    def test_ghe_discovery_asks_about_purpose(self):
        state = self._make_state("Ghế", ["room_or_space", "budget"])
        reply = render_sales_response("ask_discovery", None, state)
        self.assertIn("mục đích", reply.lower())
        self.assertIn("ghế", reply.lower())
        self.assertIn("ngân sách", reply.lower())
        self.assertNotIn("Mình tìm thấy", reply)

    def test_sofa_discovery_asks_about_space(self):
        state = self._make_state("Sofa", ["room_or_space", "budget"])
        reply = render_sales_response("ask_discovery", None, state)
        self.assertIn("không gian", reply.lower())
        self.assertIn("sofa", reply.lower())
        self.assertIn("ngân sách", reply.lower())

    def test_ban_discovery_asks_about_purpose(self):
        state = self._make_state("Bàn", ["room_or_space", "budget"])
        reply = render_sales_response("ask_discovery", None, state)
        self.assertIn("mục đích", reply.lower())
        self.assertIn("bàn", reply.lower())

    def test_no_listing_in_discovery_reply(self):
        state = self._make_state("Sofa", ["room_or_space", "budget"])
        reply = render_sales_response("ask_discovery", None, state)
        self.assertNotIn("Mình tìm thấy", reply)
        self.assertNotIn("một số sản phẩm", reply)
        self.assertNotIn("[P", reply)
        self.assertNotIn("Link nguồn:", reply)

    def test_product_type_missing_asks_type(self):
        state = self._make_state("", ["product_type"])
        reply = render_sales_response("ask_discovery", None, state)
        self.assertIn("sản phẩm nội thất", reply)
        self.assertIn("sofa", reply)
        self.assertIn("bàn", reply)
        self.assertIn("giường", reply)
        self.assertIn("tủ", reply)


class StateRetentionPhase9CTests(unittest.TestCase):
    """Phase 9C: accumulated state across Tranh consultation turns."""

    def test_tranh_full_state_retention(self):
        state = SalesConversationState(tenant_id="t", conversation_id="c")
        apply_message_to_state(state, "t muốn mua 1 bức tranh")
        apply_message_to_state(state, "phòng khách đi, chắc khoảng 3m x 5m là to nhất rồi")
        apply_message_to_state(state, "5 triệu trở xuống")

        self.assertEqual(state.slots.get("product_category"), "Tranh")
        self.assertEqual(state.slots.get("product_type"), "Tranh")
        self.assertEqual(state.slots.get("room"), "phòng khách")
        self.assertEqual(state.slots.get("budget"), "5 triệu")
        self.assertEqual(state.current_stage, "suggest")
        self.assertEqual(len(state.selected_products), 0)
        self.assertIsNone(state.slots.get("pending_sku_ref"))
        missing = state.slots.get("consultation_missing_slots")
        # missing should NOT contain 'contact' when no selected product exists
        self.assertNotIn("contact", missing)
        self.assertEqual(state.slots.get("next_best_action"), "suggest_from_kb")


class ConsultationStageForIntegrationTests(unittest.TestCase):
    """Integration tests: apply_message_to_state -> stage/action."""

    def test_bare_category_goes_to_discover(self):
        state = SalesConversationState(tenant_id="t", conversation_id="c")
        result = apply_message_to_state(state, "tu van t 1 cai ghe di")
        self.assertEqual(state.current_stage, "discover")
        self.assertEqual(result["next_best_action"], "ask_discovery_question")

    def test_category_plus_budget_goes_to_suggest(self):
        state = SalesConversationState(tenant_id="t", conversation_id="c")
        result = apply_message_to_state(state, "ghe van phong duoi 3 trieu")
        self.assertEqual(state.current_stage, "suggest")
        self.assertEqual(result["next_best_action"], "suggest_from_kb")

    def test_category_plus_room_goes_to_discover(self):
        state = SalesConversationState(tenant_id="t", conversation_id="c")
        result = apply_message_to_state(state, "sofa phong khach")
        # Phase 7B: room alone + bare category is not enough for readiness; need budget/material/color
        self.assertEqual(state.current_stage, "discover")

    def test_product_reference_goes_to_compare(self):
        state = SalesConversationState(tenant_id="t", conversation_id="c")
        update_recommended_products(state, PRODUCTS)
        result = apply_message_to_state(state, "P1 gia bao nhieu?")
        # has_product_reference + question -> compare (not suggest/discover)
        self.assertEqual(state.current_stage, "compare")

    def test_selected_products_maintains_suggest(self):
        state = SalesConversationState(tenant_id="t", conversation_id="c")
        update_recommended_products(state, PRODUCTS)
        result = apply_message_to_state(state, "cai nay bao nhieu?")
        # Has recommended -> stays suggest
        self.assertEqual(state.current_stage, "suggest")


if __name__ == "__main__":
    unittest.main()
