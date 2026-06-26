"""Eval scenarios for tenant_sales mode."""

import logging
import time
from typing import Dict, List, Optional

import requests

from eval_common import (
    BACKEND_BASE_URL,
    CHATBOT_BASE_URL,
    REQUEST_TIMEOUT,
    ScenarioResult,
    admin_session,
    check_backend,
    internal_headers,
    save_evidence,
    save_summary,
)

_logger = logging.getLogger("eval.tenant_sales")

QUERIES = [
    ("Toi muon mua tu quan ao", True),
    ("Co ban lam viec nao phu hop phong nho khong?", True),
    ("Tu van sofa cho phong khach nho ngan sach 5 trieu", True),
    ("reset", False),
    ("Toi muon dat mua mau nay", True),
]


def _find_tenant_with_kb(session) -> Optional[str]:
    """Find a tenant UUID that has active_kb_version_id set."""
    try:
        resp = session.get(f"{BACKEND_BASE_URL}/api/admin/tenants", timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        tenants = resp.json()
        if isinstance(tenants, dict) and "data" in tenants:
            tenants = tenants["data"]
        for t in tenants if isinstance(tenants, list) else []:
            kb_id = t.get("active_kb_version_id") or t.get("activeKbVersionId")
            if kb_id:
                _logger.info("Found tenant %s with active KB", t.get("code"))
                return t.get("id")
    except Exception as e:
        _logger.warning("Error finding tenant: %s", e)
    return None


def run() -> Dict[str, List[ScenarioResult]]:
    results: Dict[str, List[ScenarioResult]] = {"tenant_sales": []}

    if not check_backend():
        _logger.warning("Backend not available")
        for name, _ in QUERIES:
            r = ScenarioResult(name)
            r.skipped("Backend not available")
            results["tenant_sales"].append(r)
        return results

    session = admin_session()
    if not session:
        for name, _ in QUERIES:
            r = ScenarioResult(name)
            r.skipped("Admin login failed")
            results["tenant_sales"].append(r)
        return results

    tenant_id = _find_tenant_with_kb(session)
    if not tenant_id:
        _logger.warning("No tenant with active KB found — skipping tenant sales scenarios")
        for name, _ in QUERIES:
            r = ScenarioResult(name)
            r.skipped("No tenant with active KB found")
            results["tenant_sales"].append(r)
        return results

    for query, expect_data in QUERIES:
        r = ScenarioResult(f"chatbot: {query[:50]}")
        t0 = time.time()
        try:
            resp = requests.post(
                f"{CHATBOT_BASE_URL}/chat",
                json={
                    "message": query,
                    "tenant_id": tenant_id,
                    "gen": {"mode": "tenant_sales", "provider": "stub"},
                    "channel": "web",
                },
                timeout=REQUEST_TIMEOUT,
            )
            r.elapsed_ms = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                r.failed(f"HTTP {resp.status_code}")
            else:
                chat = resp.json()
                reply = chat.get("reply", "")
                if not reply.strip():
                    r.failed("Empty reply")
                else:
                    evidence = {"reply_preview": reply[:500], "trigger_purchase": chat.get("trigger_purchase_request")}
                    if expect_data:
                        r.passed("OK", evidence)
                    else:
                        # reset command should not error
                        r.passed("OK (control command)", evidence)
        except Exception as e:
            r.elapsed_ms = int((time.time() - t0) * 1000)
            r.failed(str(e))
        results["tenant_sales"].append(r)

    save_summary(results, "tenant_sales")
    return results


if __name__ == "__main__":
    run()
