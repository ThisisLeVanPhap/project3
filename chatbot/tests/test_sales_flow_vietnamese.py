import unittest

from app.guardrails import rule_reply, want_similar
from app.prompt import build_messages, is_vietnamese_text
from app.sales_flow import extract_slots, next_stage


class VietnameseSupportTests(unittest.TestCase):
    def test_prompt_adds_vietnamese_reply_instruction(self):
        messages = build_messages("TÃ´i muá»‘n mua sofa cho cÄƒn há»™ nhá»", [])

        self.assertTrue(is_vietnamese_text("TÃ´i muá»‘n mua sofa cho cÄƒn há»™ nhá»"))
        self.assertEqual(messages[1]["role"], "system")
        self.assertIn("Vietnamese", messages[1]["content"])

    def test_guardrails_return_vietnamese_replies(self):
        bargain = rule_reply("Shop cÃ³ giáº£m giÃ¡ thÃªm khÃ´ng?")
        inventory = rule_reply("Máº«u nÃ y cÃ²n hÃ ng khÃ´ng?")
        handoff = rule_reply("Cho mÃ¬nh gáº·p nhÃ¢n viÃªn tÆ° váº¥n nhÃ©")

        self.assertEqual(bargain["type"], "bargain_policy")
        self.assertIn("ngÃ¢n sÃ¡ch", bargain["reply"])
        self.assertEqual(inventory["type"], "inventory_mock")
        self.assertIn("tá»“n kho", inventory["reply"])
        self.assertEqual(handoff["type"], "handoff")
        self.assertIn("nhÃ¢n viÃªn", handoff["reply"])

    def test_vietnamese_slots_cover_budget_space_kids_pets_style(self):
        slots = extract_slots(
            "TÃ´i cáº§n sofa hiá»‡n Ä‘áº¡i cho cÄƒn há»™ nhá», nhÃ  cÃ³ tráº» em vÃ  mÃ¨o, ngÃ¢n sÃ¡ch khoáº£ng 12 triá»‡u"
        )

        self.assertEqual(slots["space"], "small")
        self.assertTrue(slots["kids"])
        self.assertTrue(slots["pets"])
        self.assertEqual(slots["style"], "modern")
        self.assertEqual(slots["budget_text"], "12 triá»‡u")

    def test_vietnamese_stage_transitions_preserve_existing_flow(self):
        self.assertEqual(next_stage("discover", {"style": "modern"}, "TÃ´i muá»‘n sofa hiá»‡n Ä‘áº¡i"), "propose")
        self.assertEqual(next_stage("propose", {"style": "modern"}, "Báº¡n so sÃ¡nh giÃºp mÃ¬nh nhÃ©"), "compare")
        self.assertEqual(next_stage("propose", {"style": "modern"}, "MÃ¬nh muá»‘n Ä‘áº·t hÃ ng máº«u nÃ y"), "close")
        self.assertEqual(next_stage("discover", {}, "Cho mÃ¬nh gáº·p nhÃ¢n viÃªn tÆ° váº¥n"), "handoff")
        self.assertTrue(want_similar("CÃ³ máº«u nÃ o tÆ°Æ¡ng tá»± khÃ´ng?"))

    def test_english_happy_path_still_works(self):
        slots = extract_slots("I need a modern sofa under $800 for a small apartment")

        self.assertEqual(slots["style"], "modern")
        self.assertEqual(slots["budget_usd"], 800)
        self.assertEqual(slots["space"], "small")
        self.assertEqual(
            next_stage("discover", slots, "I need a modern sofa under $800 for a small apartment"),
            "propose",
        )


if __name__ == "__main__":
    unittest.main()
