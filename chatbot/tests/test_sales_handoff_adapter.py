import json
import os
import sys
import tempfile
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

os.environ["CHATBOT_TEST_MODE"] = "1"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="chatbot-sales-adapter-logs-")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app import server  # noqa: E402
from app.retrievers import RetrievalResult  # noqa: E402
from app.sales_handoff import StoredSalesHandoffService, build_sales_handoff_service  # noqa: E402
from app.sales_handoff_adapter import (  # noqa: E402
    FailingSalesHandoffAdapter,
    HttpSalesHandoffAdapter,
    MockSalesHandoffAdapter,
    build_backend_purchase_request_payload,
    build_external_handoff_payload,
    build_sales_handoff_adapter,
)
from app.sales_handoff_store import SQLiteHandoffStore, build_idempotency_key  # noqa: E402
from app.sales_state import SalesConversationState  # noqa: E402
from tools.inspect_sales_handoffs import inspect_handoffs  # noqa: E402


class FakeHttpResponse:
    def __init__(self, status, body):
        self.status = status
        self.code = status
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body


class FakeHttpOpener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append({"request": request, "timeout": timeout})
        if not self.outcomes:
            raise AssertionError("No fake HTTP outcome configured")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        status, body = outcome
        if status >= 400:
            raise urllib.error.HTTPError(
                request.full_url,
                status,
                "fake error",
                hdrs={},
                fp=BytesIO(json.dumps(body).encode("utf-8")),
            )
        return FakeHttpResponse(status, body)


def decode_request_body(fake_opener):
    request = fake_opener.requests[-1]["request"]
    return json.loads(request.data.decode("utf-8"))


def request_header(fake_opener, name):
    return fake_opener.requests[-1]["request"].get_header(name)


def draft(quantity=1, sku="SKU-1"):
    return {
        "tenant_id": "tenant-a",
        "conversation_id": "conv-a",
        "products": [{
            "sku": sku,
            "product_name": "Rèm cuốn test",
            "source_url": "https://example.test/p1",
            "price": 700000,
            "quantity": quantity,
        }],
        "contact": {"phone": "0987654321", "email": "buyer@example.com"},
        "location": "Hà Nội",
        "address": "",
        "notes": "Purchase request draft only.",
        "status": "draft",
    }


def hit(doc_id, product_name, sku, price, url):
    return RetrievalResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}#0",
        title=product_name,
        text=f"{product_name} SKU {sku} giá {price} VND.",
        source=url,
        score=10.0,
        metadata={
            "doc_type": "product",
            "product_name": product_name,
            "category": "Rèm",
            "price": price,
            "currency": "VND",
            "sku": sku,
            "source_url": url,
        },
    )


class FakeRetriever:
    def __init__(self):
        self.hits = [
            hit("p1", "Rèm cuốn test", "SKU-1", 700000, "https://example.test/p1"),
            hit("p2", "Rèm vải test", "SKU-2", 900000, "https://example.test/p2"),
        ]

    def search(self, query: str, k: int = 4):
        return self.hits[:k]


class SalesHandoffAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "adapter.sqlite3")
        self.store = SQLiteHandoffStore(self.db_path)
        self.state = SalesConversationState(tenant_id="tenant-a", conversation_id="conv-a")

    def tearDown(self):
        self.tmp.cleanup()

    def test_mock_adapter_returns_success_and_external_id(self):
        adapter = MockSalesHandoffAdapter()

        result = adapter.send({"hello": "world"}, "idem", "corr-1")

        self.assertTrue(result.success)
        self.assertRegex(result.external_id, r"^mock_[0-9a-f]{12}$")
        self.assertEqual(len(adapter.calls), 1)

    def test_failing_adapter_returns_failure(self):
        adapter = FailingSalesHandoffAdapter(retryable=True)

        result = adapter.send({}, "idem", "corr-1")

        self.assertFalse(result.success)
        self.assertTrue(result.retryable)
        self.assertEqual(result.error_code, "mock_failure")

    def test_payload_builder_contract(self):
        payload = draft()
        key = build_idempotency_key(payload, self.state)
        record = self.store.create_or_get_request(payload, self.state, key)

        external = build_external_handoff_payload(payload, self.state, record)

        self.assertEqual(external["tenant_id"], "tenant-a")
        self.assertEqual(external["conversation_id"], "conv-a")
        self.assertEqual(external["handoff_id"], record["handoff_id"])
        self.assertEqual(external["idempotency_key"], key)
        self.assertEqual(external["customer"]["phone"], "0987654321")
        self.assertEqual(external["customer"]["email"], "buyer@example.com")
        self.assertEqual(external["product"]["sku"], "SKU-1")
        self.assertEqual(external["product"]["currency"], "VND")

    def test_backend_payload_maps_nested_payload_to_flat_dto(self):
        payload = {
            "tenant_id": "tenant-a",
            "conversation_id": "conv-a",
            "handoff_id": "handoff-1",
            "idempotency_key": "idem-1",
            "customer": {"name": "Nguyen Van A", "phone": "0987654321", "email": "buyer@example.com"},
            "request": {"quantity": 2, "location": "Ha Noi", "note": "Call before delivery"},
            "product": {
                "sku": "GHO-607",
                "name": "Rem cuon tranh cao cap",
                "source_url": "https://example.test/gho-607",
                "price": 700000,
            },
            "metadata": {"channel": "web"},
        }

        backend = build_backend_purchase_request_payload(payload)

        self.assertEqual(backend["handoff_id"], "handoff-1")
        self.assertEqual(backend["idempotency_key"], "idem-1")
        self.assertEqual(backend["tenant_id"], "tenant-a")
        self.assertEqual(backend["conversation_id"], "conv-a")
        self.assertEqual(backend["channel"], "web")
        self.assertEqual(backend["customer_name"], "Nguyen Van A")
        self.assertEqual(backend["phone"], "0987654321")
        self.assertEqual(backend["email"], "buyer@example.com")
        self.assertEqual(backend["shipping_address"], "Ha Noi")
        self.assertEqual(backend["notes"], "Call before delivery")
        self.assertEqual(backend["requested_product_ref"], "Rem cuon tranh cao cap (GHO-607)")
        self.assertEqual(backend["product_sku"], "GHO-607")
        self.assertEqual(backend["product_url"], "https://example.test/gho-607")
        self.assertEqual(backend["price"], 700000)
        self.assertEqual(backend["quantity"], 2)

    def test_http_adapter_posts_flat_payload_with_bearer_token(self):
        opener = FakeHttpOpener([(201, {"id": 123, "created": True, "status": "NEW"})])
        adapter = HttpSalesHandoffAdapter(
            endpoint="https://backend.test/api/chatbot/purchase-requests",
            service_token="secret-token",
            opener=opener,
        )
        payload = build_external_handoff_payload(draft(), self.state, {
            "handoff_id": "handoff-1",
            "idempotency_key": "idem-1",
            "created_at": "2026-01-01T00:00:00+00:00",
        })

        result = adapter.send(payload, "idem-1", "corr-1")

        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.external_id, "123")
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(request_header(opener, "Authorization"), "Bearer secret-token")
        self.assertEqual(request_header(opener, "X-correlation-id"), "corr-1")
        body = decode_request_body(opener)
        self.assertEqual(body["handoff_id"], "handoff-1")
        self.assertEqual(body["idempotency_key"], "idem-1")
        self.assertEqual(body["phone"], "0987654321")
        self.assertNotIn("customer", body)
        self.assertNotIn("product", body)

    def test_http_adapter_supports_x_service_token_header(self):
        opener = FakeHttpOpener([(201, {"id": 123, "created": True})])
        adapter = HttpSalesHandoffAdapter(
            endpoint="https://backend.test/api/chatbot/purchase-requests",
            service_token="secret-token",
            auth_header="X-Service-Token",
            opener=opener,
        )

        result = adapter.send(
            build_external_handoff_payload(draft(), self.state, {"handoff_id": "handoff-1", "idempotency_key": "idem-1"}),
            "idem-1",
            "corr-1",
        )

        self.assertTrue(result.success)
        self.assertEqual(request_header(opener, "X-service-token"), "secret-token")
        self.assertIsNone(request_header(opener, "Authorization"))

    def test_http_200_duplicate_is_idempotent_success(self):
        opener = FakeHttpOpener([(200, {"id": 123, "created": False, "purchase_request": {"id": 123}})])
        adapter = HttpSalesHandoffAdapter(endpoint="https://backend.test", service_token="token", opener=opener)

        result = adapter.send(
            build_external_handoff_payload(draft(), self.state, {"handoff_id": "handoff-1", "idempotency_key": "idem-1"}),
            "idem-1",
            "corr-1",
        )

        self.assertTrue(result.success)
        self.assertFalse(result.retryable)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.external_id, "123")

    def test_http_status_error_mapping(self):
        cases = [
            (400, "validation_error", False),
            (401, "auth_error", False),
            (403, "auth_error", False),
            (409, "idempotency_conflict", False),
            (429, "rate_limited", True),
            (500, "backend_error", True),
        ]
        payload = build_external_handoff_payload(draft(), self.state, {"handoff_id": "handoff-1", "idempotency_key": "idem-1"})
        for status, code, retryable in cases:
            with self.subTest(status=status):
                opener = FakeHttpOpener([(status, {"message": f"status {status}"})])
                adapter = HttpSalesHandoffAdapter(
                    endpoint="https://backend.test",
                    service_token="token",
                    max_retries=0,
                    opener=opener,
                )

                result = adapter.send(payload, "idem-1", "corr-1")

                self.assertFalse(result.success)
                self.assertEqual(result.status_code, status)
                self.assertEqual(result.error_code, code)
                self.assertEqual(result.retryable, retryable)

    def test_http_timeout_and_network_error_are_retryable(self):
        payload = build_external_handoff_payload(draft(), self.state, {"handoff_id": "handoff-1", "idempotency_key": "idem-1"})
        for exc, code in [(TimeoutError("slow"), "timeout"), (OSError("down"), "network_error")]:
            with self.subTest(code=code):
                opener = FakeHttpOpener([exc])
                adapter = HttpSalesHandoffAdapter(
                    endpoint="https://backend.test",
                    service_token="token",
                    max_retries=0,
                    opener=opener,
                )

                result = adapter.send(payload, "idem-1", "corr-1")

                self.assertFalse(result.success)
                self.assertEqual(result.error_code, code)
                self.assertTrue(result.retryable)

    def test_http_adapter_retries_retryable_errors_only(self):
        payload = build_external_handoff_payload(draft(), self.state, {"handoff_id": "handoff-1", "idempotency_key": "idem-1"})
        opener = FakeHttpOpener([
            (503, {"message": "temporary"}),
            (201, {"id": 124, "created": True}),
        ])
        adapter = HttpSalesHandoffAdapter(
            endpoint="https://backend.test",
            service_token="token",
            max_retries=1,
            opener=opener,
        )

        result = adapter.send(payload, "idem-1", "corr-1")

        self.assertTrue(result.success)
        self.assertEqual(result.external_id, "124")
        self.assertEqual(len(opener.requests), 2)

        non_retry_opener = FakeHttpOpener([
            (400, {"message": "bad"}),
            (201, {"id": 125}),
        ])
        non_retry_adapter = HttpSalesHandoffAdapter(
            endpoint="https://backend.test",
            service_token="token",
            max_retries=2,
            opener=non_retry_opener,
        )

        non_retry_result = non_retry_adapter.send(payload, "idem-1", "corr-1")

        self.assertFalse(non_retry_result.success)
        self.assertEqual(non_retry_result.error_code, "validation_error")
        self.assertEqual(len(non_retry_opener.requests), 1)

    def test_adapter_factory_uses_http_only_when_env_requests_it(self):
        with patch.dict(os.environ, {
            "SALES_HANDOFF_ADAPTER": "http",
            "SALES_HANDOFF_ENDPOINT": "https://backend.test",
            "SALES_HANDOFF_SERVICE_TOKEN": "token",
        }, clear=False):
            self.assertIsInstance(build_sales_handoff_adapter(), HttpSalesHandoffAdapter)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(build_sales_handoff_adapter().adapter_name, "none")

    def test_service_factory_selects_http_adapter_when_configured(self):
        db_path = os.path.join(self.tmp.name, "factory-http.sqlite3")
        with patch.dict(os.environ, {
            "SALES_HANDOFF_STORE": "sqlite",
            "SALES_HANDOFF_DB_PATH": db_path,
            "SALES_HANDOFF_ADAPTER": "http",
            "SALES_HANDOFF_ENDPOINT": "https://backend.test",
            "SALES_HANDOFF_SERVICE_TOKEN": "token",
        }, clear=False):
            service = build_sales_handoff_service()

        self.assertIsInstance(service, StoredSalesHandoffService)
        self.assertIsInstance(service.adapter, HttpSalesHandoffAdapter)

    def test_stored_service_calls_adapter_once_on_first_confirm(self):
        adapter = MockSalesHandoffAdapter()
        service = StoredSalesHandoffService(self.store, adapter=adapter)

        result = service.send_purchase_request(draft(), self.state)

        self.assertTrue(result.success)
        self.assertEqual(len(adapter.calls), 1)
        record = self.store.get_by_handoff_id(result.handoff_id)
        self.assertEqual(record["status"], "sent")
        self.assertRegex(record["external_id"], r"^mock_[0-9a-f]{12}$")
        self.assertRegex(record["correlation_id"], r"^corr_[0-9a-f]{12}$")
        self.assertEqual(record["adapter_name"], "mock")

    def test_stored_service_with_http_success_marks_sent_and_masks_events(self):
        opener = FakeHttpOpener([(
            201,
            {
                "id": 321,
                "created": True,
                "purchase_request": {
                    "id": 321,
                    "phone": "0987654321",
                    "email": "buyer@example.com",
                },
            },
        )])
        adapter = HttpSalesHandoffAdapter(
            endpoint="https://backend.test",
            service_token="token",
            opener=opener,
        )
        service = StoredSalesHandoffService(self.store, adapter=adapter)

        result = service.send_purchase_request(draft(), self.state)

        self.assertTrue(result.success)
        self.assertEqual(result.external_id, "321")
        record = self.store.get_by_handoff_id(result.handoff_id)
        self.assertEqual(record["status"], "sent")
        self.assertEqual(record["external_id"], "321")
        self.assertRegex(record["correlation_id"], r"^corr_[0-9a-f]{12}$")
        self.assertEqual(record["adapter_name"], "http")
        text = json.dumps(self.store.list_events(result.handoff_id), ensure_ascii=False)
        self.assertNotIn("0987654321", text)
        self.assertNotIn("buyer@example.com", text)
        report_text = json.dumps(inspect_handoffs(self.db_path, include_events=True), ensure_ascii=False)
        self.assertNotIn("0987654321", report_text)
        self.assertNotIn("buyer@example.com", report_text)

    def test_confirm_again_after_sent_does_not_call_adapter_again(self):
        adapter = MockSalesHandoffAdapter()
        service = StoredSalesHandoffService(self.store, adapter=adapter)

        first = service.send_purchase_request(draft(), self.state)
        second = service.send_purchase_request(draft(), self.state)

        self.assertTrue(second.already_sent)
        self.assertEqual(second.handoff_id, first.handoff_id)
        self.assertEqual(len(adapter.calls), 1)

    def test_reload_after_sent_does_not_call_adapter_again(self):
        adapter = MockSalesHandoffAdapter()
        service = StoredSalesHandoffService(self.store, adapter=adapter)
        first = service.send_purchase_request(draft(), self.state)
        reloaded_adapter = MockSalesHandoffAdapter()
        reloaded = StoredSalesHandoffService(SQLiteHandoffStore(self.db_path), adapter=reloaded_adapter)

        second = reloaded.send_purchase_request(draft(), self.state)

        self.assertTrue(second.already_sent)
        self.assertEqual(second.handoff_id, first.handoff_id)
        self.assertEqual(len(reloaded_adapter.calls), 0)

    def test_retryable_failure_can_retry_and_records_retry_event(self):
        failing = FailingSalesHandoffAdapter(retryable=True)
        service = StoredSalesHandoffService(self.store, adapter=failing)
        first = service.send_purchase_request(draft(), self.state)
        retry_adapter = MockSalesHandoffAdapter()
        retry_service = StoredSalesHandoffService(self.store, adapter=retry_adapter)

        second = retry_service.send_purchase_request(draft(), self.state)

        self.assertFalse(first.success)
        self.assertTrue(first.retryable)
        self.assertTrue(second.success)
        self.assertEqual(len(retry_adapter.calls), 1)
        events = self.store.list_events(second.handoff_id)
        self.assertIn("handoff_retry", [event["event_type"] for event in events])

    def test_non_retryable_failure_does_not_retry(self):
        failing = FailingSalesHandoffAdapter(retryable=False)
        service = StoredSalesHandoffService(self.store, adapter=failing)
        first = service.send_purchase_request(draft(), self.state)
        retry_adapter = MockSalesHandoffAdapter()
        retry_service = StoredSalesHandoffService(self.store, adapter=retry_adapter)

        second = retry_service.send_purchase_request(draft(), self.state)

        self.assertFalse(first.success)
        self.assertFalse(second.success)
        self.assertEqual(second.error, "mock_failure")
        self.assertEqual(len(retry_adapter.calls), 0)

    def test_adapter_events_mask_raw_contact(self):
        adapter = MockSalesHandoffAdapter()
        service = StoredSalesHandoffService(self.store, adapter=adapter)

        result = service.send_purchase_request(draft(), self.state)
        event_text = json.dumps(self.store.list_events(result.handoff_id), ensure_ascii=False)

        self.assertNotIn("0987654321", event_text)
        self.assertNotIn("buyer@example.com", event_text)
        self.assertIn("098****321", event_text)
        self.assertIn("b***@example.com", event_text)


class ServerAdapterIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_kb = server.KB
        cls.previous_by_mode = dict(server.KB_BY_MODE)
        server.KB = FakeRetriever()
        server.KB_BY_MODE.clear()
        server.KB_BY_MODE["keyword"] = server.KB
        server._set_ready(True, None)
        cls.client = TestClient(server.app)

    @classmethod
    def tearDownClass(cls):
        server.KB = cls.previous_kb
        server.KB_BY_MODE.clear()
        server.KB_BY_MODE.update(cls.previous_by_mode)
        server.SALES_STATE_STORE.clear()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "server-adapter.sqlite3")
        self.previous_service = server.SALES_HANDOFF_SERVICE
        self.adapter = MockSalesHandoffAdapter()
        server.SALES_STATE_STORE.clear()
        server.SALES_HANDOFF_SERVICE = StoredSalesHandoffService(
            SQLiteHandoffStore(self.db_path),
            adapter=self.adapter,
        )

    def tearDown(self):
        server.SALES_HANDOFF_SERVICE = self.previous_service
        server.SALES_STATE_STORE.clear()
        self.tmp.cleanup()

    def post(self, conversation_id, message, sales_mode="active"):
        return self.client.post(
            "/chat",
            json={
                "message": message,
                "history": [],
                "conversation_id": conversation_id,
                "tenant_id": "tenant-a",
                "channel": "web",
                "gen": {
                    "provider": "stub",
                    "mode": "general_compare",
                    "retrieval_mode": "keyword",
                    "retrieval_top_k": 4,
                    "answer_mode": "template",
                    "sales_mode": sales_mode,
                },
            },
        )

    def create_pending(self, conversation_id):
        self.post(conversation_id, "Có rèm nào dưới 1 triệu không?")
        self.post(conversation_id, "tôi lấy P1, số tôi 0987654321, email buyer@example.com")

    def test_debug_does_not_expose_raw_contact(self):
        self.create_pending("adapter-debug")

        response = self.post("adapter-debug", "ok gửi")

        debug_text = json.dumps(response.json()["debug"], ensure_ascii=False)
        self.assertNotIn("0987654321", debug_text)
        self.assertNotIn("buyer@example.com", debug_text)

    def test_sales_mode_off_does_not_call_adapter(self):
        self.post("adapter-off", "tôi lấy P1, số tôi 0987654321", sales_mode="off")

        self.assertEqual(len(self.adapter.calls), 0)

    def test_shadow_mode_does_not_call_adapter(self):
        self.post("adapter-shadow", "Có rèm nào dưới 1 triệu không?", sales_mode="shadow")
        self.post("adapter-shadow", "tôi lấy P1, số tôi 0987654321", sales_mode="shadow")
        self.post("adapter-shadow", "ok gửi", sales_mode="shadow")

        self.assertEqual(len(self.adapter.calls), 0)


if __name__ == "__main__":
    unittest.main()
