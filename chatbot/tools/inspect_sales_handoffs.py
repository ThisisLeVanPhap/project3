import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

CHATBOT_DIR = Path(__file__).resolve().parents[1]
if str(CHATBOT_DIR) not in sys.path:
    sys.path.insert(0, str(CHATBOT_DIR))

from app.sales_handoff_store import SQLiteHandoffStore, mask_pii  # noqa: E402


def _safe_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "handoff_id": record.get("handoff_id"),
        "external_id": record.get("external_id"),
        "correlation_id": record.get("correlation_id"),
        "adapter_name": record.get("adapter_name"),
        "retryable": bool(record.get("retryable")) if record.get("retryable") is not None else None,
        "tenant_id": record.get("tenant_id"),
        "conversation_id": record.get("conversation_id"),
        "status": record.get("status"),
        "confirmation_status": record.get("confirmation_status"),
        "purchase_request_status": record.get("purchase_request_status"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "sent_at": record.get("sent_at"),
        "failed_at": record.get("failed_at"),
        "cancelled_at": record.get("cancelled_at"),
        "masked_summary": mask_pii(record.get("masked_summary") or {}),
        "error": record.get("error"),
    }


def inspect_handoffs(
    db_path: str,
    tenant_id: str | None = None,
    limit: int = 20,
    handoff_id: str | None = None,
    include_events: bool = False,
) -> Dict[str, Any]:
    store = SQLiteHandoffStore(db_path)
    records = [_safe_record(record) for record in store.list_recent(tenant_id, limit, handoff_id)]
    if include_events:
        for record in records:
            record["events"] = [
                {
                    "event_id": event.get("event_id"),
                    "handoff_id": event.get("handoff_id"),
                    "event_type": event.get("event_type"),
                    "created_at": event.get("created_at"),
                    "payload": mask_pii(event.get("payload") or {}),
                }
                for event in store.list_events(record["handoff_id"])
            ]
    return {
        "db": os.path.abspath(db_path),
        "tenant_id": tenant_id,
        "total": store.total_count(tenant_id),
        "by_status": store.count_by_status(tenant_id),
        "recent": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect masked sales handoff records from SQLite.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--tenant-id")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--handoff-id")
    parser.add_argument("--include-events", action="store_true")
    args = parser.parse_args()

    report = inspect_handoffs(
        args.db,
        tenant_id=args.tenant_id,
        limit=args.limit,
        handoff_id=args.handoff_id,
        include_events=args.include_events,
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
