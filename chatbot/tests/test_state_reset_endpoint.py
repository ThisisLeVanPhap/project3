import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["CHATBOT_TEST_MODE"] = "1"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="chatbot-state-reset-logs-")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVER_IMPORT_ERROR = None
server = None
TestClient = None

try:
    from fastapi.testclient import TestClient  # noqa: E402
    from app import server  # noqa: E402
    from app.state import get_state  # noqa: E402
except ModuleNotFoundError as exc:
    SERVER_IMPORT_ERROR = exc


class StateResetEndpointTests(unittest.TestCase):
    def setUp(self):
        if SERVER_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"chatbot server dependencies are not installed: {SERVER_IMPORT_ERROR}")
        server.SALES_STATE_STORE.clear()
        self.client = TestClient(server.app)

    def tearDown(self):
        if server is not None:
            server.SALES_STATE_STORE.clear()

    def test_state_reset_clears_chat_and_sales_state_for_conversation(self):
        get_state("conv-a").last_question = "old question"
        sales_state = server._load_sales_state("tenant-a", "conv-a")
        sales_state.slots["phone"] = "0900000000"
        server._save_sales_state(sales_state)

        response = self.client.post(
            "/state/reset",
            json={"tenant_id": "tenant-a", "conversation_id": "conv-a"},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "conversation_id": "conv-a"}, response.json())
        self.assertIsNone(get_state("conv-a").last_question)
        self.assertNotIn(("tenant-a", "conv-a"), server.SALES_STATE_STORE)


if __name__ == "__main__":
    unittest.main()
