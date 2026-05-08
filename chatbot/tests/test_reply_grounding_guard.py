import unittest

from app.server import _apply_grounding_guard


class ReplyGroundingGuardTests(unittest.TestCase):
    def test_policy_guard_keeps_vietnamese_intro_for_ascii_vietnamese_query(self):
        context = (
            "- Chinh sach thanh toan: thanh toan hoac dat coc truc tiep voi nhan vien ban hang. "
            "Thanh toan sau khi giao hang ap dung trong pham vi 0-50km. "
            "Co ho tro chuyen khoan."
        )
        response = "From the verified store data, I can confirm: store policy is available."

        guarded = _apply_grounding_guard("Chinh sach thanh toan nhu the nao?", context, response)

        self.assertNotIn("From the verified store data", guarded)
        self.assertIn("theo", guarded.lower())
        self.assertIn("đặt cọc", guarded.lower())

    def test_policy_guard_replaces_unsupported_payment_methods(self):
        context = (
            "- Chinh sach thanh toan: thanh toan hoac dat coc truc tiep voi nhan vien ban hang. "
            "Thanh toan sau khi giao hang ap dung trong pham vi 0-50km. "
            "Co ho tro chuyen khoan. Hotline 0987822944."
        )
        response = "Chung toi ho tro the tin dung, Visa va chuyen khoan ngan hang."

        guarded = _apply_grounding_guard("Chinh sach thanh toan nhu the nao?", context, response)

        self.assertNotIn("Visa", guarded)
        self.assertNotIn("the tin dung", guarded.lower())
        self.assertIn("đặt cọc", guarded.lower())

    def test_material_guard_falls_back_when_cleaning_comparison_is_unsupported(self):
        context = (
            "- Sofa go cho phong khach nho. "
            "Sofa go co the duoc boc nem da hoac ni."
        )
        response = "Sofa vai de lau chui hon sofa da nen hop nha co tre nho."

        guarded = _apply_grounding_guard("Sofa vai hay sofa da se de ve sinh hon?", context, response)

        self.assertIn("chưa đủ", guarded.lower())
        self.assertNotIn("de lau chui hon", guarded.lower())


if __name__ == "__main__":
    unittest.main()
