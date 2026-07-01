import os
import unittest


class ServerTenantSalesWordingTests(unittest.TestCase):
    def _read_server_source(self) -> str:
        here = os.path.dirname(__file__)
        srv_path = os.path.normpath(os.path.join(here, "..", "app", "server.py"))
        with open(srv_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_close_cta_contains_confirm_cancel_and_no_direct_payment(self):
        src = self._read_server_source()
        self.assertIn("CONFIRM", src)
        self.assertIn("CANCEL", src)
        # Accept multiple spellings to be robust across source encodings.
        self.assertTrue(
            ("thanh toán trực tiếp trong chat" in src)
            or ("thanh toan truc tiep trong chat" in src)
            or ("xử lý thanh toán trực tiếp trong chat" in src)
            or ("xu ly thanh toan truc tiep trong chat" in src),
            "CTA must state no direct payment processing in chat"
        )
        self.assertNotIn("To proceed, reply CONFIRM and I", src)

    def test_similar_suggestion_does_not_ask_then_list(self):
        src = self._read_server_source()
        # Must not contain the old question-before-list form
        self.assertNotIn("Bạn có muốn mình gợi ý một số sản phẩm tương tự không?", src)
        # If the similar suggestion block exists in source, the header should be the non-question form.
        # We only require that the question form is absent; the header may be present as a literal.
        # To keep the test stable, also assert the preferred header appears as a source string.
        self.assertIn("Mình gợi ý một vài sản phẩm tương tự trong dữ liệu hiện có:", src)


if __name__ == "__main__":
    unittest.main()
