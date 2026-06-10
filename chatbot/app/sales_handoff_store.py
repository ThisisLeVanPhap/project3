import hashlib
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional


PHONE_RE = re.compile(r"(?<!\d)(0[35789]\d{8}|\+?84\d{9})(?!\d)")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mask_phone(phone: Any) -> str:
    if "*" in str(phone or ""):
        return str(phone or "")
    digits = re.sub(r"\D", "", str(phone or ""))
    if not digits:
        return ""
    if len(digits) <= 6:
        return digits[0] + "***" + digits[-1]
    return f"{digits[:3]}****{digits[-3:]}"


def mask_email(email: Any) -> str:
    value = str(email or "").strip()
    if "***" in value:
        return value
    if "@" not in value:
        return value
    local, domain = value.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def mask_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    masked = PHONE_RE.sub(lambda match: mask_phone(match.group(0)), value)
    return EMAIL_RE.sub(lambda match: mask_email(match.group(0)), masked)


def mask_pii(data: Any) -> Any:
    if isinstance(data, dict):
        masked: Dict[str, Any] = {}
        for key, value in data.items():
            lowered = str(key).lower()
            if lowered == "phone":
                masked[key] = mask_phone(value)
            elif lowered == "email":
                masked[key] = mask_email(value)
            else:
                masked[key] = mask_pii(value)
        return masked
    if isinstance(data, list):
        return [mask_pii(item) for item in data]
    return mask_text(data)


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalized_product(product: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sku": _clean(product.get("sku")),
        "source_url": _clean(product.get("source_url") or product.get("url")),
        "product_name": _clean(product.get("product_name") or product.get("name")),
        "quantity": int(product.get("quantity") or 1),
    }


def build_idempotency_key(draft: Dict[str, Any], state: Any = None) -> str:
    products = [_normalized_product(product) for product in (draft.get("products") or [])]
    contact = draft.get("contact") or {}
    identity = {
        "tenant_id": _clean(draft.get("tenant_id") or getattr(state, "tenant_id", "")),
        "conversation_id": _clean(draft.get("conversation_id") or getattr(state, "conversation_id", "")),
        "products": products,
        "contact": {
            "phone": re.sub(r"\D", "", _clean(contact.get("phone"))),
            "email": _clean(contact.get("email")).lower(),
        },
        "location": _clean(draft.get("location")),
        "address": _clean(draft.get("address")),
    }
    digest = hashlib.sha256(stable_json(identity).encode("utf-8")).hexdigest()
    return f"sales_handoff:{digest}"


def build_masked_summary(draft: Dict[str, Any], state: Any, handoff_id: str, idempotency_key: str) -> Dict[str, Any]:
    products = []
    for product in draft.get("products") or []:
        products.append({
            "sku": product.get("sku") or "",
            "product_name": product.get("product_name") or "",
            "source_url": product.get("source_url") or "",
            "price": product.get("price"),
            "quantity": product.get("quantity") or 1,
        })
    return {
        "handoff_id": handoff_id,
        "tenant_id": draft.get("tenant_id") or getattr(state, "tenant_id", None),
        "conversation_id": draft.get("conversation_id") or getattr(state, "conversation_id", None),
        "idempotency_key": idempotency_key,
        "purchase_request_status": draft.get("status"),
        "products": products,
        "contact": mask_pii(draft.get("contact") or {}),
        "location": mask_text(draft.get("location") or ""),
        "address": mask_text(draft.get("address") or ""),
    }


def row_to_dict(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    data = dict(row)
    for key in ("payload_json", "masked_summary_json"):
        if data.get(key):
            data[key.replace("_json", "")] = json.loads(data[key])
    return data


class HandoffStore:
    def create_or_get_request(self, draft: dict, state: Any, idempotency_key: str) -> dict:
        raise NotImplementedError

    def mark_sent(self, handoff_id: str, result: dict) -> dict:
        raise NotImplementedError

    def mark_failed(self, handoff_id: str, error: str) -> dict:
        raise NotImplementedError

    def mark_cancelled(self, handoff_id: str, reason: str | None = None) -> dict:
        raise NotImplementedError

    def get_by_handoff_id(self, handoff_id: str) -> dict | None:
        raise NotImplementedError

    def get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        raise NotImplementedError

    def append_event(self, handoff_id: str, event_type: str, payload: dict | None = None) -> None:
        raise NotImplementedError


class SQLiteHandoffStore(HandoffStore):
    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        parent = os.path.dirname(os.path.abspath(self.db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS handoff_requests (
                    handoff_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    conversation_id TEXT,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    confirmation_status TEXT,
                    purchase_request_status TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    sent_at TEXT,
                    failed_at TEXT,
                    cancelled_at TEXT,
                    payload_json TEXT,
                    masked_summary_json TEXT,
                    error TEXT,
                    external_id TEXT,
                    correlation_id TEXT,
                    adapter_name TEXT,
                    retryable INTEGER
                );
                CREATE TABLE IF NOT EXISTS handoff_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    handoff_id TEXT,
                    event_type TEXT,
                    created_at TEXT,
                    payload_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_handoff_requests_tenant_id ON handoff_requests(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_handoff_requests_conversation_id ON handoff_requests(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_handoff_requests_idempotency_key ON handoff_requests(idempotency_key);
                CREATE INDEX IF NOT EXISTS idx_handoff_requests_status ON handoff_requests(status);
                """
            )
            existing_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(handoff_requests)").fetchall()
            }
            for column_name, column_type in (
                ("external_id", "TEXT"),
                ("correlation_id", "TEXT"),
                ("adapter_name", "TEXT"),
                ("retryable", "INTEGER"),
            ):
                if column_name not in existing_columns:
                    conn.execute(f"ALTER TABLE handoff_requests ADD COLUMN {column_name} {column_type}")

    def create_or_get_request(self, draft: dict, state: Any, idempotency_key: str) -> dict:
        existing = self.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        handoff_id = f"handoff_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        tenant_id = draft.get("tenant_id") or getattr(state, "tenant_id", None) or "default"
        conversation_id = draft.get("conversation_id") or getattr(state, "conversation_id", None)
        masked_summary = build_masked_summary(draft, state, handoff_id, idempotency_key)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO handoff_requests (
                    handoff_id, tenant_id, conversation_id, idempotency_key, status,
                    confirmation_status, purchase_request_status, created_at, updated_at,
                    payload_json, masked_summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    handoff_id,
                    tenant_id,
                    conversation_id,
                    idempotency_key,
                    "pending_confirmation",
                    "pending",
                    draft.get("status"),
                    now,
                    now,
                    stable_json(draft),
                    stable_json(masked_summary),
                ),
            )
        self.append_event(handoff_id, "draft_created", masked_summary)
        self.append_event(handoff_id, "confirmation_pending", {"handoff_id": handoff_id})
        return self.get_by_handoff_id(handoff_id) or {}

    def mark_sent(self, handoff_id: str, result: dict) -> dict:
        now = utc_now()
        result = result or {}
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE handoff_requests
                SET status = ?, confirmation_status = ?, updated_at = ?, sent_at = ?,
                    error = NULL, external_id = ?, correlation_id = ?, adapter_name = ?, retryable = ?
                WHERE handoff_id = ?
                """,
                (
                    "sent",
                    "confirmed",
                    now,
                    now,
                    result.get("external_id"),
                    result.get("correlation_id"),
                    result.get("adapter_name"),
                    0 if result.get("retryable") is False else (1 if result.get("retryable") else None),
                    handoff_id,
                ),
            )
        self.append_event(handoff_id, "handoff_sent", result or {"handoff_id": handoff_id})
        return self.get_by_handoff_id(handoff_id) or {}

    def mark_failed(
        self,
        handoff_id: str,
        error: str,
        retryable: bool | None = None,
        result: dict | None = None,
    ) -> dict:
        now = utc_now()
        result = result or {}
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE handoff_requests
                SET status = ?, confirmation_status = ?, updated_at = ?, failed_at = ?, error = ?,
                    external_id = COALESCE(?, external_id),
                    correlation_id = COALESCE(?, correlation_id),
                    adapter_name = COALESCE(?, adapter_name),
                    retryable = ?
                WHERE handoff_id = ?
                """,
                (
                    "failed",
                    "confirmed",
                    now,
                    now,
                    str(error or ""),
                    result.get("external_id"),
                    result.get("correlation_id"),
                    result.get("adapter_name"),
                    1 if retryable else 0,
                    handoff_id,
                ),
            )
        payload = {"error": str(error or ""), "retryable": bool(retryable)}
        payload.update(result)
        self.append_event(handoff_id, "handoff_failed", payload)
        return self.get_by_handoff_id(handoff_id) or {}

    def mark_cancelled(self, handoff_id: str, reason: str | None = None) -> dict:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE handoff_requests
                SET status = ?, confirmation_status = ?, updated_at = ?, cancelled_at = ?, error = ?
                WHERE handoff_id = ?
                """,
                ("cancelled", "cancelled", now, now, reason, handoff_id),
            )
        self.append_event(handoff_id, "handoff_cancelled", {"reason": reason or ""})
        return self.get_by_handoff_id(handoff_id) or {}

    def get_by_handoff_id(self, handoff_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM handoff_requests WHERE handoff_id = ?",
                (handoff_id,),
            ).fetchone()
        return row_to_dict(row)

    def get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM handoff_requests WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return row_to_dict(row)

    def append_event(self, handoff_id: str, event_type: str, payload: dict | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO handoff_events (handoff_id, event_type, created_at, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (handoff_id, event_type, utc_now(), stable_json(mask_pii(payload or {}))),
            )

    def list_recent(
        self,
        tenant_id: str | None = None,
        limit: int = 20,
        handoff_id: str | None = None,
    ) -> list[dict]:
        params: list[Any] = []
        where = []
        if tenant_id:
            where.append("tenant_id = ?")
            params.append(tenant_id)
        if handoff_id:
            where.append("handoff_id = ?")
            params.append(handoff_id)
        clause = "WHERE " + " AND ".join(where) if where else ""
        params.append(max(1, int(limit)))
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM handoff_requests {clause} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [row_to_dict(row) or {} for row in rows]

    def list_events(self, handoff_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM handoff_events WHERE handoff_id = ? ORDER BY event_id ASC",
                (handoff_id,),
            ).fetchall()
        events = []
        for row in rows:
            data = dict(row)
            data["payload"] = json.loads(data["payload_json"] or "{}")
            events.append(data)
        return events

    def count_by_status(self, tenant_id: str | None = None) -> Dict[str, int]:
        params: list[Any] = []
        clause = ""
        if tenant_id:
            clause = "WHERE tenant_id = ?"
            params.append(tenant_id)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT status, COUNT(*) AS count FROM handoff_requests {clause} GROUP BY status",
                params,
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def total_count(self, tenant_id: str | None = None) -> int:
        params: list[Any] = []
        clause = ""
        if tenant_id:
            clause = "WHERE tenant_id = ?"
            params.append(tenant_id)
        with self.connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS count FROM handoff_requests {clause}", params).fetchone()
        return int(row["count"] if row else 0)


def default_sqlite_path() -> str:
    return str(Path("chatbot") / "data" / "sales_handoff.sqlite3")
