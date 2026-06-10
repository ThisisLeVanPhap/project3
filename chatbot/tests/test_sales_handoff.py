import unittest
from concurrent.futures import ThreadPoolExecutor

from app.sales_handoff import InMemorySalesHandoffService
from app.sales_state import SalesConversationState


class SalesHandoffTests(unittest.TestCase):
    def test_in_memory_handoff_generates_id_and_records_payload(self):
        service = InMemorySalesHandoffService()
        state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-a")
        draft = {"status": "draft", "products": [{"sku": "P1"}], "contact": {"phone": "0987654321"}}

        result = service.send_purchase_request(draft, state)

        self.assertTrue(result.success)
        self.assertRegex(result.handoff_id, r"^handoff_[0-9a-f]{12}$")
        self.assertNotIn("conv-a", result.handoff_id)
        self.assertIsNone(result.error)
        self.assertEqual(len(service.sent_payloads), 1)
        self.assertEqual(service.sent_payloads[0]["draft"], draft)

    def test_in_memory_handoff_can_fail_once_for_tests(self):
        service = InMemorySalesHandoffService(fail_next=True)
        state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-a")

        failed = service.send_purchase_request({}, state)
        succeeded = service.send_purchase_request({}, state)

        self.assertFalse(failed.success)
        self.assertEqual(failed.error, "in_memory_handoff_failure")
        self.assertTrue(succeeded.success)
        self.assertEqual(len(service.sent_payloads), 1)

    def test_in_memory_handoff_ids_are_unique_under_concurrent_sends(self):
        service = InMemorySalesHandoffService()
        state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-a")
        draft = {"status": "draft", "products": [{"sku": "P1"}], "contact": {"phone": "0987654321"}}

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: service.send_purchase_request(draft, state), range(25)))

        handoff_ids = [result.handoff_id for result in results]
        self.assertEqual(len(handoff_ids), 25)
        self.assertEqual(len(set(handoff_ids)), 25)
        self.assertEqual(len(service.sent_payloads), 25)


if __name__ == "__main__":
    unittest.main()
