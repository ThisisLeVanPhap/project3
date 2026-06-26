"""Common utilities for eval scenarios."""

import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_logger = logging.getLogger("eval")

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8080").rstrip("/")
CHATBOT_BASE_URL = os.getenv("CHATBOT_BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "tmp" / "eval"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_TIMEOUT = int(os.getenv("EVAL_TIMEOUT_SECONDS", "30"))

# Vietnamese normalization

def strip_vietnamese_accents(text: str) -> str:
    """Remove Vietnamese diacritics for comparison purposes."""
    normalized = unicodedata.normalize("NFD", text or "")
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D")


def normalize_text(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    text = strip_vietnamese_accents(text)
    text = re.sub(r"\s+", " ", text)
    return text


def contains_forbidden(text: str, patterns: List[str]) -> List[str]:
    """Check if text contains any forbidden pattern (accent-insensitive)."""
    if not text:
        return []
    normalized = normalize_text(text)
    found = []
    for pattern in patterns:
        norm_pattern = normalize_text(pattern)
        if norm_pattern in normalized:
            found.append(pattern)
    return found


class ScenarioResult:
    def __init__(self, name: str):
        self.name = name
        self.status = "SKIPPED"
        self.detail = ""
        self.evidence: Dict[str, Any] = {}
        self.elapsed_ms = 0

    def passed(self, detail: str = "", evidence: Optional[Dict] = None):
        self.status = "PASS"
        self.detail = detail
        if evidence:
            self.evidence = evidence

    def failed(self, detail: str):
        self.status = "FAIL"
        self.detail = detail

    def skipped(self, detail: str = ""):
        self.status = "SKIPPED"
        self.detail = detail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail[:500],
            "elapsed_ms": self.elapsed_ms,
            "evidence_keys": list(self.evidence.keys()) if self.evidence else [],
        }


def admin_session() -> Optional[requests.Session]:
    """Login as admin and return session with cookie."""
    session = requests.Session()
    resp = session.post(
        f"{BACKEND_BASE_URL}/api/login",
        json={"name": ADMIN_USERNAME, "code": ADMIN_PASSWORD},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code == 200 and resp.json().get("ok"):
        _logger.info("Admin login OK")
        return session
    _logger.warning("Admin login failed (status %s)", resp.status_code)
    return None


def internal_headers() -> Dict[str, str]:
    headers = {}
    if INTERNAL_API_SECRET:
        headers["X-Internal-Api-Key"] = INTERNAL_API_SECRET
    return headers


def check_backend() -> bool:
    try:
        resp = requests.get(f"{BACKEND_BASE_URL}/api/login", timeout=5)
        return resp.status_code in (200, 401, 405)
    except Exception:
        return False


def check_chatbot() -> bool:
    try:
        resp = requests.get(f"{CHATBOT_BASE_URL}/healthz", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def save_evidence(name: str, data: Any):
    path = EVIDENCE_DIR / name
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _logger.info("Evidence saved: %s", path)


def save_summary(results: Dict[str, List[ScenarioResult]], mode_name: str):
    total_pass = sum(1 for r in sum(results.values(), []) if r.status == "PASS")
    total_fail = sum(1 for r in sum(results.values(), []) if r.status == "FAIL")
    total_skip = sum(1 for r in sum(results.values(), []) if r.status == "SKIPPED")
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode_name,
        "backend_base_url": BACKEND_BASE_URL,
        "chatbot_base_url": CHATBOT_BASE_URL,
        "scenarios": {k: [s.to_dict() for s in v] for k, v in results.items()},
        "total_pass": total_pass,
        "total_fail": total_fail,
        "total_skipped": total_skip,
        "overall": "PASS" if total_fail == 0 and total_pass > 0 else "PARTIAL" if total_pass > 0 else "FAIL",
    }
    save_evidence(f"{mode_name}_results.json", summary)
    return summary
