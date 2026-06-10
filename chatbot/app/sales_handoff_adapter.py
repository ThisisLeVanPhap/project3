from dataclasses import dataclass
import json
import os
import socket
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict

try:
    from .sales_handoff_store import mask_pii, utc_now
except ImportError:  # pragma: no cover
    from app.sales_handoff_store import mask_pii, utc_now


@dataclass
class HandoffAdapterResult:
    success: bool
    external_id: str | None = None
    status_code: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    raw_response: dict | None = None


class SalesHandoffAdapter:
    adapter_name = "none"

    def send(self, payload: dict, idempotency_key: str, correlation_id: str) -> HandoffAdapterResult:
        raise NotImplementedError


class NoopSalesHandoffAdapter(SalesHandoffAdapter):
    adapter_name = "none"

    def __init__(self):
        self.calls: list[dict] = []

    def send(self, payload: dict, idempotency_key: str, correlation_id: str) -> HandoffAdapterResult:
        self.calls.append({
            "payload": payload,
            "idempotency_key": idempotency_key,
            "correlation_id": correlation_id,
        })
        return HandoffAdapterResult(
            success=True,
            external_id=None,
            status_code=None,
            raw_response={"adapter": "none", "accepted": True},
        )


class MockSalesHandoffAdapter(SalesHandoffAdapter):
    adapter_name = "mock"

    def __init__(self):
        self.calls: list[dict] = []
        self.last_payload: dict | None = None

    def send(self, payload: dict, idempotency_key: str, correlation_id: str) -> HandoffAdapterResult:
        self.last_payload = payload
        self.calls.append({
            "payload": payload,
            "idempotency_key": idempotency_key,
            "correlation_id": correlation_id,
        })
        external_id = f"mock_{uuid.uuid4().hex[:12]}"
        return HandoffAdapterResult(
            success=True,
            external_id=external_id,
            status_code=200,
            retryable=False,
            raw_response={
                "external_id": external_id,
                "status": "accepted",
                "correlation_id": correlation_id,
            },
        )


class FailingSalesHandoffAdapter(SalesHandoffAdapter):
    adapter_name = "failing"

    def __init__(self, retryable: bool = True, error_code: str = "mock_failure"):
        self.retryable = retryable
        self.error_code = error_code
        self.calls: list[dict] = []

    def send(self, payload: dict, idempotency_key: str, correlation_id: str) -> HandoffAdapterResult:
        self.calls.append({
            "payload": payload,
            "idempotency_key": idempotency_key,
            "correlation_id": correlation_id,
        })
        return HandoffAdapterResult(
            success=False,
            external_id=None,
            status_code=503 if self.retryable else 400,
            error_code=self.error_code,
            error_message="Mock handoff adapter failure",
            retryable=self.retryable,
            raw_response={
                "error": self.error_code,
                "retryable": self.retryable,
                "correlation_id": correlation_id,
            },
        )


class HttpSalesHandoffAdapter(SalesHandoffAdapter):
    adapter_name = "http"

    def __init__(
        self,
        endpoint: str | None = None,
        service_token: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        auth_header: str | None = None,
        opener: Any | None = None,
    ):
        self.endpoint = (endpoint if endpoint is not None else os.getenv("SALES_HANDOFF_ENDPOINT", "")).strip()
        self.service_token = (
            service_token if service_token is not None else os.getenv("SALES_HANDOFF_SERVICE_TOKEN", "")
        ).strip()
        self.timeout_seconds = _float_env("SALES_HANDOFF_TIMEOUT_SECONDS", 5.0) if timeout_seconds is None else float(timeout_seconds)
        self.max_retries = _int_env("SALES_HANDOFF_MAX_RETRIES", 1, minimum=0) if max_retries is None else max(0, int(max_retries))
        self.auth_header = (
            auth_header if auth_header is not None else os.getenv("SALES_HANDOFF_AUTH_HEADER", "Authorization")
        ).strip() or "Authorization"
        self.opener = opener or urllib.request.urlopen

    def send(self, payload: dict, idempotency_key: str, correlation_id: str) -> HandoffAdapterResult:
        if not self.endpoint:
            return HandoffAdapterResult(
                success=False,
                error_code="missing_endpoint",
                error_message="SALES_HANDOFF_ENDPOINT is required for HTTP handoff adapter",
                retryable=False,
                raw_response={"adapter": "http", "configured": False},
            )
        if not self.service_token:
            return HandoffAdapterResult(
                success=False,
                error_code="missing_service_token",
                error_message="SALES_HANDOFF_SERVICE_TOKEN is required for HTTP handoff adapter",
                retryable=False,
                raw_response={"adapter": "http", "configured": False},
            )

        backend_payload = build_backend_purchase_request_payload(payload)
        attempts = self.max_retries + 1
        last_result: HandoffAdapterResult | None = None
        for attempt in range(1, attempts + 1):
            result = self._send_once(
                backend_payload,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                attempt=attempt,
                max_attempts=attempts,
            )
            last_result = result
            if result.success or not result.retryable:
                return result
        return last_result or HandoffAdapterResult(
            success=False,
            error_code="network_error",
            retryable=True,
            raw_response={"attempts": attempts},
        )

    def _send_once(
        self,
        backend_payload: dict,
        idempotency_key: str,
        correlation_id: str,
        attempt: int,
        max_attempts: int,
    ) -> HandoffAdapterResult:
        data = json.dumps(backend_payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": idempotency_key,
            "X-Correlation-Id": correlation_id,
        }
        if self.auth_header.lower() == "x-service-token":
            headers["X-Service-Token"] = self.service_token
        else:
            headers["Authorization"] = f"Bearer {self.service_token}"

        request = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
        try:
            response = self.opener(request, timeout=self.timeout_seconds)
            status_code = int(getattr(response, "status", None) or getattr(response, "code", 0) or 0)
            body = response.read()
            parsed = _parse_json_body(body)
            return _result_from_http_response(status_code, parsed, attempt, max_attempts)
        except urllib.error.HTTPError as exc:
            parsed = _parse_json_body(exc.read())
            return _result_from_http_response(int(exc.code), parsed, attempt, max_attempts)
        except (TimeoutError, socket.timeout) as exc:
            return HandoffAdapterResult(
                success=False,
                error_code="timeout",
                error_message=exc.__class__.__name__,
                retryable=True,
                raw_response={"attempt": attempt, "max_attempts": max_attempts},
            )
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, (TimeoutError, socket.timeout)):
                return HandoffAdapterResult(
                    success=False,
                    error_code="timeout",
                    error_message=reason.__class__.__name__,
                    retryable=True,
                    raw_response={"attempt": attempt, "max_attempts": max_attempts},
                )
            return HandoffAdapterResult(
                success=False,
                error_code="network_error",
                error_message=reason.__class__.__name__,
                retryable=True,
                raw_response={"attempt": attempt, "max_attempts": max_attempts},
            )
        except OSError as exc:
            return HandoffAdapterResult(
                success=False,
                error_code="network_error",
                error_message=exc.__class__.__name__,
                retryable=True,
                raw_response={"attempt": attempt, "max_attempts": max_attempts},
            )


def _float_env(name: str, default: float, minimum: float = 0.1) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def _parse_json_body(body: bytes | str | None) -> dict:
    if body is None:
        return {}
    if isinstance(body, bytes):
        text = body.decode("utf-8", errors="replace")
    else:
        text = str(body)
    if not text.strip():
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"body": parsed}
    except json.JSONDecodeError:
        return {"body": text[:500]}


def _extract_external_id(response: dict) -> str | None:
    value = response.get("id")
    if value is None and isinstance(response.get("purchase_request"), dict):
        value = response["purchase_request"].get("id")
    if value is None:
        return None
    return str(value)


def _result_from_http_response(status_code: int, response: dict, attempt: int, max_attempts: int) -> HandoffAdapterResult:
    safe_response = mask_pii(response)
    safe_response["_attempt"] = attempt
    safe_response["_max_attempts"] = max_attempts
    if status_code in {200, 201}:
        return HandoffAdapterResult(
            success=True,
            external_id=_extract_external_id(response),
            status_code=status_code,
            retryable=False,
            raw_response=safe_response,
        )

    error_code = _error_code_for_status(status_code)
    return HandoffAdapterResult(
        success=False,
        external_id=_extract_external_id(response),
        status_code=status_code,
        error_code=error_code,
        error_message=str(response.get("message") or response.get("error") or ""),
        retryable=_is_retryable_status(status_code),
        raw_response=safe_response,
    )


def _error_code_for_status(status_code: int) -> str:
    if status_code == 400:
        return "validation_error"
    if status_code in {401, 403}:
        return "auth_error"
    if status_code == 409:
        return "idempotency_conflict"
    if status_code == 429:
        return "rate_limited"
    if status_code in {500, 502, 503, 504}:
        return "backend_error"
    return "http_error"


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code in {500, 502, 503, 504}


def build_backend_purchase_request_payload(payload: dict) -> dict:
    customer = payload.get("customer") or {}
    request = payload.get("request") or {}
    product = payload.get("product") or {}
    metadata = payload.get("metadata") or {}
    product_name = _clean(product.get("name") or product.get("product_name"))
    product_sku = _clean(product.get("sku"))
    requested_product_ref = product_name
    if product_name and product_sku:
        requested_product_ref = f"{product_name} ({product_sku})"
    elif product_sku:
        requested_product_ref = product_sku
    elif _clean(product.get("source_url")):
        requested_product_ref = _clean(product.get("source_url"))

    quantity = request.get("quantity")
    if quantity in (None, ""):
        quantity = 1

    return {
        "handoff_id": _clean(payload.get("handoff_id")),
        "idempotency_key": _clean(payload.get("idempotency_key")),
        "tenant_id": _clean(payload.get("tenant_id")),
        "conversation_id": _clean(payload.get("conversation_id")),
        "channel": _clean(metadata.get("channel") or payload.get("channel") or "chatbot"),
        "customer_name": _clean(customer.get("name")),
        "phone": _clean(customer.get("phone")),
        "email": _clean(customer.get("email")),
        "shipping_address": _clean(request.get("location") or request.get("shipping_address")),
        "notes": _clean(request.get("note")),
        "requested_product_ref": requested_product_ref,
        "product_sku": product_sku,
        "product_url": _clean(product.get("source_url") or product.get("url")),
        "price": product.get("price"),
        "quantity": quantity,
    }


def _clean(value: Any) -> str:
    return str(value or "").strip()


def build_external_handoff_payload(
    draft: Dict[str, Any],
    state: Any,
    handoff_record: Dict[str, Any],
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    products = list(draft.get("products") or [])
    product = products[0] if products else {}
    contact = draft.get("contact") or {}
    metadata = metadata or {}
    return {
        "tenant_id": draft.get("tenant_id") or getattr(state, "tenant_id", None),
        "conversation_id": draft.get("conversation_id") or getattr(state, "conversation_id", None),
        "handoff_id": handoff_record.get("handoff_id"),
        "idempotency_key": handoff_record.get("idempotency_key"),
        "customer": {
            "phone": contact.get("phone") or "",
            "email": contact.get("email") or "",
            "name": contact.get("name"),
        },
        "request": {
            "type": "purchase_request",
            "status": "confirmed_by_user",
            "quantity": product.get("quantity") or 1,
            "location": draft.get("location") or "",
            "note": draft.get("notes") or "",
        },
        "product": {
            "sku": product.get("sku") or "",
            "name": product.get("product_name") or product.get("name") or "",
            "source_url": product.get("source_url") or product.get("url") or "",
            "price": product.get("price"),
            "currency": product.get("currency") or draft.get("currency") or "VND",
        },
        "metadata": {
            "source": "chatbot",
            "answer_mode": metadata.get("answer_mode"),
            "sales_mode": metadata.get("sales_mode", "active"),
            "created_at": handoff_record.get("created_at") or utc_now(),
            "confirmed_at": getattr(state, "confirmed_at", None) or metadata.get("confirmed_at"),
        },
    }


def build_sales_handoff_adapter(name: str | None = None) -> SalesHandoffAdapter:
    normalized = (name if name is not None else os.getenv("SALES_HANDOFF_ADAPTER", "none")).strip().lower()
    if normalized == "mock":
        return MockSalesHandoffAdapter()
    if normalized == "none":
        return NoopSalesHandoffAdapter()
    if normalized == "http":
        return HttpSalesHandoffAdapter()
    raise ValueError(f"Unsupported SALES_HANDOFF_ADAPTER: {name}")
