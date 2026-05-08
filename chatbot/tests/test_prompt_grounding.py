import unittest

from app.prompt import build_messages


class PromptGroundingTests(unittest.TestCase):
    def test_build_messages_includes_verified_kb_context_when_provided(self):
        messages = build_messages(
            "Toi can sofa cho can ho nho",
            [],
            system_prompt="system",
            grounding_context=(
                "- sofa bang: gon cho phong khach nho\n"
                "- sofa goc mini: hop 2-3 nguoi ngoi"
            ),
        )

        self.assertEqual(messages[1]["role"], "system")
        self.assertIn("Verified KB context", messages[1]["content"])
        self.assertIn("sofa bang", messages[1]["content"].lower())
        self.assertIn("sofa goc mini", messages[1]["content"].lower())

    def test_build_messages_adds_query_specific_grounding_rules(self):
        messages = build_messages(
            "Chinh sach thanh toan nhu the nao?",
            [],
            system_prompt="system",
            grounding_context="- dat coc truc tiep\n- thanh toan sau khi giao hang trong pham vi 0-50km",
        )

        self.assertIn("Grounding rules for this user message", messages[1]["content"])
        self.assertIn("only methods, conditions, distance ranges", messages[1]["content"])
        self.assertIn("instead of guessing", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
