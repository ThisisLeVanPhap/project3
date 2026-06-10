import unittest

from app.guardrails import rule_reply, want_similar
from app.prompt import build_messages, is_vietnamese_text
from app.sales_flow import extract_slots, next_stage


VI_PROMPT = "T\u00f4i mu\u1ed1n mua sofa cho c\u0103n h\u1ed9 nh\u1ecf"
VI_BARGAIN = "Shop c\u00f3 gi\u1ea3m gi\u00e1 th\u00eam kh\u00f4ng?"
VI_INVENTORY = "M\u1eabu n\u00e0y c\u00f2n h\u00e0ng kh\u00f4ng?"
VI_HANDOFF = "Cho m\u00ecnh g\u1eb7p nh\u00e2n vi\u00ean t\u01b0 v\u1ea5n nh\u00e9"
VI_SLOTS = (
    "T\u00f4i c\u1ea7n sofa hi\u1ec7n \u0111\u1ea1i cho c\u0103n h\u1ed9 nh\u1ecf, "
    "nh\u00e0 c\u00f3 tr\u1ebb em v\u00e0 m\u00e8o, ng\u00e2n s\u00e1ch kho\u1ea3ng 12 tri\u1ec7u"
)


class VietnameseSupportTests(unittest.TestCase):
    def test_prompt_adds_vietnamese_reply_instruction(self):
        messages = build_messages(VI_PROMPT, [])

        self.assertTrue(is_vietnamese_text(VI_PROMPT))
        self.assertEqual(messages[1]["role"], "system")
        self.assertIn("Vietnamese", messages[1]["content"])

    def test_guardrails_return_vietnamese_replies(self):
        greeting = rule_reply("hi")
        bargain = rule_reply(VI_BARGAIN)
        inventory = rule_reply(VI_INVENTORY)
        handoff = rule_reply(VI_HANDOFF)

        self.assertEqual(greeting["type"], "greeting")
        self.assertIn("Ch\u00e0o b\u1ea1n", greeting["reply"])
        self.assertEqual(bargain["type"], "bargain_policy")
        self.assertIn("ng\u00e2n s\u00e1ch", bargain["reply"])
        self.assertEqual(inventory["type"], "inventory_mock")
        self.assertIn("t\u1ed3n kho", inventory["reply"])
        self.assertEqual(handoff["type"], "handoff")
        self.assertIn("nh\u00e2n vi\u00ean", handoff["reply"])

    def test_vietnamese_slots_cover_budget_space_kids_pets_style(self):
        slots = extract_slots(VI_SLOTS)

        self.assertEqual(slots["space"], "small")
        self.assertTrue(slots["kids"])
        self.assertTrue(slots["pets"])
        self.assertEqual(slots["style"], "modern")
        self.assertEqual(slots["budget_text"], "12 tri\u1ec7u")

    def test_vietnamese_stage_transitions_preserve_existing_flow(self):
        self.assertEqual(next_stage("discover", {"style": "modern"}, "T\u00f4i mu\u1ed1n sofa hi\u1ec7n \u0111\u1ea1i"), "propose")
        self.assertEqual(next_stage("propose", {"style": "modern"}, "B\u1ea1n so s\u00e1nh gi\u00fap m\u00ecnh nh\u00e9"), "compare")
        self.assertEqual(next_stage("propose", {"style": "modern"}, "M\u00ecnh mu\u1ed1n \u0111\u1eb7t h\u00e0ng m\u1eabu n\u00e0y"), "close")
        self.assertEqual(next_stage("discover", {}, "Cho m\u00ecnh g\u1eb7p nh\u00e2n vi\u00ean t\u01b0 v\u1ea5n"), "handoff")
        self.assertTrue(want_similar("C\u00f3 m\u1eabu n\u00e0o t\u01b0\u01a1ng t\u1ef1 kh\u00f4ng?"))

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
