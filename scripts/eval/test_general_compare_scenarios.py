"""Eval scenarios for general_compare mode."""

import logging
import time
from typing import Dict, List

import requests

from eval_common import (
    BACKEND_BASE_URL,
    CHATBOT_BASE_URL,
    INTERNAL_API_SECRET,
    REQUEST_TIMEOUT,
    ScenarioResult,
    admin_session,
    check_backend,
    contains_forbidden,
    internal_headers,
    save_evidence,
    save_summary,
)

_logger = logging.getLogger("eval.general_compare")

QUERIES = [
    ("sofa", True),
    ("sofa", True),  # duplicate for chatbot
    ("tủ quần áo", True),
    ("bàn", True),
    ("kệ", True),
    ("thảm", True),
    ("xe đạp điện", False),  # no data expected
]

FORBIDDEN_PATTERNS = [
    "số điện thoại", "so dien thoai",
    "phone",
    "để lại thông tin", "de lai thong tin",
    "tạo đơn", "tao don",
    "đặt hàng", "dat hang",
    "chuyển cho nhân viên", "chuyen cho nhan vien",
]


def run() -> Dict[str, List[ScenarioResult]]:
    results: Dict[str, List[ScenarioResult]] = {"backend_search": [], "chatbot_response": []}

    if not check_backend():
        _logger.warning("Backend not available")
        for name, _ in QUERIES:
            r = ScenarioResult(name)
            r.skipped("Backend not available")
            results["backend_search"].append(r)
            results["chatbot_response"].append(ScenarioResult(name))
            results["chatbot_response"][-1].skipped("Backend not available")
        return results

    session = admin_session()
    headers = internal_headers()

    for query, expect_data in QUERIES:
        _evaluate_backend_search(query, expect_data, results["backend_search"], headers, session)
        _evaluate_chatbot_response(query, expect_data, results["chatbot_response"], headers, session)

    save_summary(results, "general_compare")
    return results


def _evaluate_backend_search(query, expect_data, results_list, headers, session):
    r = ScenarioResult(f"backend: {query[:50]}")
    t0 = time.time()
    try:
        resp = requests.get(
            f"{BACKEND_BASE_URL}/api/internal/general-products/search",
            params={"q": query, "mode": "GENERAL_COMPARE", "role": "USER", "limit": "5"},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        r.elapsed_ms = int((time.time() - t0) * 1000)
        if resp.status_code == 403:
            r.skipped(f"Backend returned 403 (internal API key required)")
        elif resp.status_code != 200:
            r.failed(f"HTTP {resp.status_code}")
        else:
            data = resp.json()
            items = data.get("items") or data.get("products") or []
            if expect_data and len(items) == 0:
                r.failed(f"Expected >0 items, got 0")
            elif not expect_data and len(items) == 0:
                r.passed("No data as expected")
            else:
                item_names = [i.get("name", "?") for i in items[:3]]
                reasons = []
                for i in items:
                    sr = i.get("scoreReasons") or i.get("score_reasons") or []
                    reasons.extend(sr)
                evidence = {
                    "query": query,
                    "item_count": len(items),
                    "top_names": item_names,
                    "score_reasons": list(set(reasons))[:5],
                }
                r.passed(f"{len(items)} items, top: {item_names}", evidence)
    except Exception as e:
        r.elapsed_ms = int((time.time() - t0) * 1000)
        r.failed(str(e))
    results_list.append(r)


def _evaluate_chatbot_response(query, expect_data, results_list, headers, session):
    r = ScenarioResult(f"chatbot: {query[:50]}")
    t0 = time.time()
    try:
        # Call FastAPI chat
        resp = requests.post(
            f"{CHATBOT_BASE_URL}/chat",
            json={
                "message": query,
                "gen": {"mode": "general_compare", "provider": "stub"},
                "channel": "web",
            },
            timeout=REQUEST_TIMEOUT,
        )
        r.elapsed_ms = int((time.time() - t0) * 1000)
        if resp.status_code != 200:
            r.failed(f"HTTP {resp.status_code}")
        else:
            reply = resp.json().get("reply", "")
            violations = contains_forbidden(reply, FORBIDDEN_PATTERNS)
            if violations:
                r.failed(f"Forbidden patterns found: {violations}")
                r.evidence = {"reply_preview": reply[:300]}
            elif not reply.strip():
                r.failed("Empty reply")
            else:
                evidence = {"reply_preview": reply[:500]}
                if expect_data and "chua co du du lieu" in reply.lower():
                    r.failed("Expected data but got no-data message")
                else:
                    r.passed("OK", evidence)
    except Exception as e:
        r.elapsed_ms = int((time.time() - t0) * 1000)
        r.failed(str(e))
    results_list.append(r)


if __name__ == "__main__":
    run()
