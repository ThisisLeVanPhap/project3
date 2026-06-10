import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol

CHATBOT_DIR = Path(__file__).resolve().parents[1]
if str(CHATBOT_DIR) not in sys.path:
    sys.path.insert(0, str(CHATBOT_DIR))

from app.sales_handoff_store import SQLiteHandoffStore, mask_pii, stable_json  # noqa: E402


SMOKE_PHONE = "0987654321"
SMOKE_EMAIL = "smoke.buyer@example.com"


class SmokeChatClient(Protocol):
    def post_turn(self, message: str) -> Dict[str, Any]:
        ...

    def handoff_sent_count(self) -> int | None:
        ...


@dataclass
class SmokeConfig:
    chatbot_kb_dir: str
    backend_url: str
    service_token: str
    tenant_id: str
    conversation_id: str
    db: str
    output: str | None = None


class InProcessChatClient:
    def __init__(self, tenant_id: str, conversation_id: str):
        from fastapi.testclient import TestClient
        from app import server

        self.server = server
        self.client = TestClient(server.app)
        self.tenant_id = tenant_id
        self.conversation_id = conversation_id

    def post_turn(self, message: str) -> Dict[str, Any]:
        response = self.client.post(
            "/chat",
            json={
                "message": message,
                "history": [],
                "conversation_id": self.conversation_id,
                "tenant_id": self.tenant_id,
                "channel": "web",
                "gen": {
                    "provider": "stub",
                    "mode": "general_compare",
                    "retrieval_mode": "keyword",
                    "retrieval_top_k": 4,
                    "answer_mode": "template",
                    "sales_mode": "active",
                },
            },
        )
        try:
            body = response.json()
        except Exception:
            body = {"raw_text": response.text}
        body["_http_status"] = response.status_code
        return body

    def handoff_sent_count(self) -> int | None:
        service = getattr(self.server, "SALES_HANDOFF_SERVICE", None)
        sent_payloads = getattr(service, "sent_payloads", None)
        if sent_payloads is None:
            return None
        return len(sent_payloads)


def configure_environment(config: SmokeConfig) -> None:
    os.environ["KB_DIR"] = config.chatbot_kb_dir
    os.environ["CHATBOT_TEST_MODE"] = "1"
    os.environ.setdefault("LOG_DIR", tempfile.mkdtemp(prefix="handoff-e2e-smoke-"))
    os.environ["SALES_HANDOFF_STORE"] = "sqlite"
    os.environ["SALES_HANDOFF_DB_PATH"] = config.db
    os.environ["SALES_HANDOFF_ADAPTER"] = "http"
    os.environ["SALES_HANDOFF_ENDPOINT"] = config.backend_url.rstrip("/") + "/api/chatbot/purchase-requests"
    os.environ["SALES_HANDOFF_SERVICE_TOKEN"] = config.service_token


def _turn_summary(response: Dict[str, Any]) -> Dict[str, Any]:
    debug = response.get("debug") or {}
    return mask_pii({
        "http_status": response.get("_http_status"),
        "model": response.get("model"),
        "sales_action_taken": debug.get("sales_action_taken"),
        "handoff_status": debug.get("handoff_status"),
        "confirmation_status": debug.get("confirmation_status"),
        "handoff_id": debug.get("handoff_id"),
    })


def _append_error(errors: List[str], message: str) -> None:
    if message not in errors:
        errors.append(message)


def run_smoke_flow(
    config: SmokeConfig,
    chat_client: SmokeChatClient,
    store: SQLiteHandoffStore,
) -> Dict[str, Any]:
    errors: List[str] = []
    turns: List[Dict[str, Any]] = []

    flow = [
        "Co rem nao duoi 1 trieu khong?",
        "Toi lay P1",
        f"So dien thoai cua toi la {SMOKE_PHONE}, email {SMOKE_EMAIL}, giao o Ha Noi",
        "ok gui",
    ]

    first_confirm_response: Dict[str, Any] = {}
    for message in flow:
        response = chat_client.post_turn(message)
        turns.append(_turn_summary(response))
        first_confirm_response = response

    first_debug = first_confirm_response.get("debug") or {}
    handoff_id = first_debug.get("handoff_id")
    if first_confirm_response.get("_http_status") != 200:
        _append_error(errors, f"confirm HTTP status was {first_confirm_response.get('_http_status')}, expected 200")
    if first_debug.get("handoff_status") != "sent":
        _append_error(errors, f"handoff_status was {first_debug.get('handoff_status')!r}, expected 'sent'")
    if first_debug.get("sales_action_taken") != "handoff_sent":
        _append_error(errors, f"sales_action_taken was {first_debug.get('sales_action_taken')!r}, expected 'handoff_sent'")
    if not handoff_id:
        _append_error(errors, "missing handoff_id in confirm debug")

    record = store.get_by_handoff_id(handoff_id) if handoff_id else None
    sqlite_status = record.get("status") if record else None
    external_id = record.get("external_id") if record else None
    if not record:
        _append_error(errors, "missing SQLite handoff record")
    else:
        if record.get("status") != "sent":
            _append_error(errors, f"SQLite status was {record.get('status')!r}, expected 'sent'")
        if record.get("adapter_name") != "http":
            _append_error(errors, f"SQLite adapter_name was {record.get('adapter_name')!r}, expected 'http'")
        if not record.get("external_id"):
            _append_error(errors, "SQLite external_id is missing")

    total_before_duplicate = store.total_count(config.tenant_id)
    sent_count_before_duplicate = chat_client.handoff_sent_count()
    duplicate_response = chat_client.post_turn("xac nhan")
    turns.append(_turn_summary(duplicate_response))
    total_after_duplicate = store.total_count(config.tenant_id)
    sent_count_after_duplicate = chat_client.handoff_sent_count()
    duplicate_debug = duplicate_response.get("debug") or {}
    duplicate_action = duplicate_debug.get("sales_action_taken")
    duplicate_safe = (
        total_after_duplicate == total_before_duplicate
        and duplicate_debug.get("handoff_id") == handoff_id
        and duplicate_action in {"handoff_already_sent", "handoff_sent"}
    )
    if sent_count_before_duplicate is not None and sent_count_after_duplicate is not None:
        duplicate_safe = duplicate_safe and sent_count_after_duplicate == sent_count_before_duplicate
    if not duplicate_safe:
        _append_error(errors, "duplicate confirm was not safe")

    report = {
        "passed": not errors,
        "backend_endpoint": config.backend_url.rstrip("/") + "/api/chatbot/purchase-requests",
        "tenant_id": config.tenant_id,
        "conversation_id": config.conversation_id,
        "handoff_id": handoff_id,
        "external_id": external_id,
        "sqlite_status": sqlite_status,
        "duplicate_safe": duplicate_safe,
        "admin_visible": "skipped",
        "admin_visibility_reason": "backend GET /api/purchase-requests requires admin/session auth, not service token",
        "turns": turns,
        "errors": errors,
    }
    return _ensure_no_raw_contact(mask_pii(report))


def _ensure_no_raw_contact(report: Dict[str, Any]) -> Dict[str, Any]:
    text = stable_json(report)
    if SMOKE_PHONE in text or SMOKE_EMAIL in text:
        safe = mask_pii(report)
        safe.setdefault("errors", []).append("report contained raw contact before final masking")
        safe["passed"] = False
        return safe
    return report


def write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test chatbot HTTP handoff against Java backend.")
    parser.add_argument("--chatbot-kb-dir", required=True)
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--service-token", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = SmokeConfig(
        chatbot_kb_dir=args.chatbot_kb_dir,
        backend_url=args.backend_url,
        service_token=args.service_token,
        tenant_id=args.tenant_id,
        conversation_id=args.conversation_id,
        db=args.db,
        output=args.output,
    )
    configure_environment(config)
    store = SQLiteHandoffStore(config.db)
    client = InProcessChatClient(config.tenant_id, config.conversation_id)
    report = run_smoke_flow(config, client, store)
    write_json(config.output or args.output, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
