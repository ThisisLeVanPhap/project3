from dataclasses import dataclass
import os
import threading
import uuid
from typing import Any, Dict, List

try:
    from .sales_handoff_adapter import (
        SalesHandoffAdapter,
        build_external_handoff_payload,
        build_sales_handoff_adapter,
    )
    from .sales_state import SalesConversationState
    from .sales_handoff_store import (
        SQLiteHandoffStore,
        build_idempotency_key,
        default_sqlite_path,
        mask_pii,
    )
except ImportError:  # pragma: no cover
    from app.sales_handoff_adapter import (
        SalesHandoffAdapter,
        build_external_handoff_payload,
        build_sales_handoff_adapter,
    )
    from app.sales_state import SalesConversationState
    from app.sales_handoff_store import (
        SQLiteHandoffStore,
        build_idempotency_key,
        default_sqlite_path,
        mask_pii,
    )


@dataclass
class HandoffResult:
    success: bool
    handoff_id: str | None = None
    error: str | None = None
    already_sent: bool = False
    status: str | None = None
    external_id: str | None = None
    retryable: bool = False


class SalesHandoffService:
    def send_purchase_request(self, draft: Dict[str, Any], state: SalesConversationState) -> HandoffResult:
        raise NotImplementedError


class InMemorySalesHandoffService(SalesHandoffService):
    def __init__(self, fail_next: bool = False):
        self.sent_payloads: List[Dict[str, Any]] = []
        self.fail_next = fail_next
        self._lock = threading.Lock()

    def send_purchase_request(self, draft: Dict[str, Any], state: SalesConversationState) -> HandoffResult:
        with self._lock:
            if self.fail_next:
                self.fail_next = False
                return HandoffResult(False, None, "in_memory_handoff_failure")

            handoff_id = f"handoff_{uuid.uuid4().hex[:12]}"
            self.sent_payloads.append({
                "handoff_id": handoff_id,
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "draft": draft,
            })
        return HandoffResult(True, handoff_id, None)


class StoredSalesHandoffService(SalesHandoffService):
    def __init__(
        self,
        store: SQLiteHandoffStore,
        fail_next: bool = False,
        adapter: SalesHandoffAdapter | None = None,
    ):
        self.store = store
        self.fail_next = fail_next
        self.adapter = adapter or build_sales_handoff_adapter("none")
        self.sent_payloads: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def ensure_pending_request(
        self,
        draft: Dict[str, Any],
        state: SalesConversationState,
        event_type: str | None = None,
    ) -> Dict[str, Any]:
        idempotency_key = build_idempotency_key(draft, state)
        existing = self.store.get_by_idempotency_key(idempotency_key)
        record = existing or self.store.create_or_get_request(draft, state, idempotency_key)
        state.handoff_id = record.get("handoff_id")
        if event_type and record.get("handoff_id") and (existing or event_type == "draft_updated"):
            self.store.append_event(record["handoff_id"], event_type, {
                "handoff_id": record["handoff_id"],
                "status": record.get("status"),
            })
        return record

    def cancel_pending_request(self, state: SalesConversationState, reason: str | None = None) -> Dict[str, Any] | None:
        if not state.handoff_id:
            return None
        record = self.store.get_by_handoff_id(state.handoff_id)
        if not record or record.get("status") == "sent":
            return record
        return self.store.mark_cancelled(state.handoff_id, reason)

    def append_state_event(
        self,
        state: SalesConversationState,
        event_type: str,
        payload: Dict[str, Any] | None = None,
    ) -> None:
        if state.handoff_id:
            self.store.append_event(state.handoff_id, event_type, payload or {})

    def send_purchase_request(self, draft: Dict[str, Any], state: SalesConversationState) -> HandoffResult:
        with self._lock:
            record = self.ensure_pending_request(draft, state)
            handoff_id = record.get("handoff_id")
            status = record.get("status")
            if status == "sent":
                self.store.append_event(handoff_id, "duplicate_confirm_ignored", {"handoff_id": handoff_id})
                return HandoffResult(
                    True,
                    handoff_id,
                    None,
                    already_sent=True,
                    status="sent",
                    external_id=record.get("external_id"),
                )
            if status == "failed":
                if record.get("retryable") == 0:
                    self.store.append_event(handoff_id, "duplicate_confirm_ignored", {
                        "handoff_id": handoff_id,
                        "reason": "non_retryable_failure",
                    })
                    return HandoffResult(
                        False,
                        handoff_id,
                        record.get("error") or "non_retryable_handoff_failure",
                        status="failed",
                        retryable=False,
                    )
                self.store.append_event(handoff_id, "handoff_retry", {"handoff_id": handoff_id})

            if self.fail_next:
                self.fail_next = False
                self.store.mark_failed(handoff_id, "stored_handoff_failure", retryable=True)
                return HandoffResult(False, handoff_id, "stored_handoff_failure", status="failed", retryable=True)

            idempotency_key = record.get("idempotency_key") or build_idempotency_key(draft, state)
            correlation_id = record.get("correlation_id") or f"corr_{uuid.uuid4().hex[:12]}"
            payload = build_external_handoff_payload(
                draft,
                state,
                record,
                metadata={"sales_mode": "active"},
            )
            adapter_result = self.adapter.send(payload, idempotency_key, correlation_id)
            adapter_payload = {
                "handoff_id": handoff_id,
                "external_id": adapter_result.external_id,
                "correlation_id": correlation_id,
                "adapter_name": getattr(self.adapter, "adapter_name", "unknown"),
                "status_code": adapter_result.status_code,
                "retryable": adapter_result.retryable,
                "raw_response": adapter_result.raw_response,
            }
            if not adapter_result.success:
                error = adapter_result.error_code or adapter_result.error_message or "handoff_adapter_failed"
                self.store.append_event(handoff_id, "handoff_adapter_failed", {
                    **adapter_payload,
                    "error_code": adapter_result.error_code,
                    "error_message": adapter_result.error_message,
                })
                self.store.mark_failed(handoff_id, error, retryable=adapter_result.retryable, result=adapter_payload)
                return HandoffResult(
                    False,
                    handoff_id,
                    error,
                    status="failed",
                    external_id=adapter_result.external_id,
                    retryable=adapter_result.retryable,
                )

            self.sent_payloads.append({
                "handoff_id": handoff_id,
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "draft": draft,
                "external_payload": payload,
            })
            self.store.append_event(handoff_id, "handoff_adapter_success", {
                **adapter_payload,
                "payload": mask_pii(payload),
            })
            self.store.mark_sent(handoff_id, {
                "handoff_id": handoff_id,
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                **adapter_payload,
                "draft": mask_pii(draft),
            })
            return HandoffResult(
                True,
                handoff_id,
                None,
                status="sent",
                external_id=adapter_result.external_id,
                retryable=False,
            )


def build_sales_handoff_service() -> SalesHandoffService:
    if (os.getenv("SALES_HANDOFF_STORE") or "").strip().lower() == "sqlite":
        db_path = os.getenv("SALES_HANDOFF_DB_PATH") or default_sqlite_path()
        adapter = build_sales_handoff_adapter(os.getenv("SALES_HANDOFF_ADAPTER") or "none")
        return StoredSalesHandoffService(SQLiteHandoffStore(db_path), adapter=adapter)
    return InMemorySalesHandoffService()
