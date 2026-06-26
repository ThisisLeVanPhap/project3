"""Eval scenarios for market_price mode."""

import logging
import time
from typing import Dict, List

import requests

from eval_common import (
    BACKEND_BASE_URL,
    CHATBOT_BASE_URL,
    REQUEST_TIMEOUT,
    ScenarioResult,
    admin_session,
    check_backend,
    contains_forbidden,
    internal_headers,
    save_evidence,
    save_summary,
)

_logger = logging.getLogger("eval.market_price")

QUERIES = [
    ("Sofa vải 2m giá 8 triệu có hợp lý không?", True, 8000000),
    ("Tủ quần áo gỗ công nghiệp khoảng 5 triệu có đắt không?", True, 5000000),
    ("Bàn làm việc nhỏ tầm bao nhiêu?", True, None),
    ("Ghế sofa dưới 7 triệu có nhiều lựa chọn không?", True, None),
    ("Kệ tivi 4 triệu có hợp lý không?", True, None),
]

FORBIDDEN_PATTERNS = [
    "số điện thoại", "so dien thoai",
    "phone",
    "để lại thông tin", "de lai thong tin",
    "tạo đơn", "tao don",
    "purchase request",
    "đặt hàng", "dat hang",
    "chuyển cho nhân viên", "chuyen cho nhan vien",
]


def run() -> Dict[str, List[ScenarioResult]]:
    results: Dict[str, List[ScenarioResult]] = {"backend_insight": [], "chatbot_response": []}

    if not check_backend():
        _logger.warning("Backend not available")
        for name, _, _ in QUERIES:
            r = ScenarioResult(name)
            r.skipped("Backend not available")
            results["backend_insight"].append(r)
            results["chatbot_response"].append(ScenarioResult(name))
            results["chatbot_response"][-1].skipped("Backend not available")
        return results

    headers = internal_headers()

    for query, expect_data, input_price in QUERIES:
        _evaluate_backend_insight(query, expect_data, input_price, results["backend_insight"], headers)
        _evaluate_chatbot_response(query, expect_data, results["chatbot_response"], headers)

    save_summary(results, "market_price")
    return results


def _evaluate_backend_insight(query, expect_data, input_price, results_list, headers):
    r = ScenarioResult(f"backend: {query[:50]}")
    t0 = time.time()
    try:
        params = {"q": query, "mode": "MARKET_PRICE", "role": "USER"}
        if input_price:
            params["inputPrice"] = str(input_price)
        resp = requests.get(
            f"{BACKEND_BASE_URL}/api/internal/market-price/insight",
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        r.elapsed_ms = int((time.time() - t0) * 1000)
        if resp.status_code == 403:
            r.skipped("Backend returned 403 (internal API key required)")
        elif resp.status_code != 200:
            r.failed(f"HTTP {resp.status_code}")
        else:
            data = resp.json()
            stats = data.get("stats") or {}
            sample_count = stats.get("sampleCount", 0)
            if expect_data and sample_count == 0:
                r.failed("Expected data but sampleCount=0")
            elif sample_count == 0:
                r.passed("No data as expected")
            else:
                evidence = {
                    "query": query,
                    "sampleCount": sample_count,
                    "median": stats.get("medianPrice"),
                    "min": stats.get("minPrice"),
                    "max": stats.get("maxPrice"),
                    "confidence": stats.get("confidence"),
                    "assessment": data.get("assessment"),
                }
                r.passed(f"{sample_count} samples, median={stats.get('medianPrice')}", evidence)
    except Exception as e:
        r.elapsed_ms = int((time.time() - t0) * 1000)
        r.failed(str(e))
    results_list.append(r)


def _evaluate_chatbot_response(query, expect_data, results_list, headers):
    r = ScenarioResult(f"chatbot: {query[:50]}")
    t0 = time.time()
    try:
        resp = requests.post(
            f"{CHATBOT_BASE_URL}/chat",
            json={
                "message": query,
                "gen": {"mode": "market_price", "provider": "stub"},
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
                r.failed(f"Forbidden patterns: {violations}")
                r.evidence = {"reply_preview": reply[:300]}
            elif not reply.strip():
                r.failed("Empty reply")
            else:
                evidence = {"reply_preview": reply[:500]}
                if expect_data and "chua co du du lieu" in reply.lower():
                    r.failed("Expected data but got no-data")
                else:
                    r.passed("OK", evidence)
    except Exception as e:
        r.elapsed_ms = int((time.time() - t0) * 1000)
        r.failed(str(e))
    results_list.append(r)


if __name__ == "__main__":
    run()
