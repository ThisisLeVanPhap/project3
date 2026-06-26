#!/usr/bin/env python3
"""Quick smoke check for local Docker environment."""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_common import (
    BACKEND_BASE_URL,
    CHATBOT_BASE_URL,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    INTERNAL_API_SECRET,
    REQUEST_TIMEOUT,
    admin_session,
    internal_headers,
    save_evidence,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_logger = logging.getLogger("smoke")

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "tmp" / "eval"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

results: Dict[str, Any] = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "backend_url": BACKEND_BASE_URL,
    "chatbot_url": CHATBOT_BASE_URL,
    "checks": [],
}

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def check(name: str, status: str, detail: str = ""):
    results["checks"].append({"name": name, "status": status, "detail": detail[:200]})
    _logger.info("%s: %s - %s", status, name, detail[:80])


def main():
    # 1. Backend reachable
    try:
        r = requests.get(f"{BACKEND_BASE_URL}/api/login", timeout=5)
        if r.status_code in (200, 401, 405):
            check("Backend reachable", PASS, f"HTTP {r.status_code}")
        else:
            check("Backend reachable", FAIL, f"Unexpected HTTP {r.status_code}")
    except Exception as e:
        check("Backend reachable", FAIL, str(e))
        _save_and_exit()

    # 2. FastAPI healthz
    try:
        r = requests.get(f"{CHATBOT_BASE_URL}/healthz", timeout=5)
        if r.status_code == 200:
            data = r.json()
            ready = data.get("ready", False)
            check("FastAPI /healthz", PASS if ready else FAIL,
                  f"ready={ready} cached_pipelines={data.get('cached_pipelines', 0)}")
        else:
            check("FastAPI /healthz", FAIL, f"HTTP {r.status_code}")
    except Exception as e:
        check("FastAPI /healthz", FAIL, str(e))

    # 3. Admin login
    try:
        r = requests.post(f"{BACKEND_BASE_URL}/api/login",
                          json={"name": ADMIN_USERNAME, "code": ADMIN_PASSWORD}, timeout=5)
        if r.status_code == 200 and r.json().get("ok"):
            check("Admin login", PASS, f"role={r.json().get('role')}")
        else:
            check("Admin login", FAIL, r.json().get("message", "login failed"))
    except Exception as e:
        check("Admin login", FAIL, str(e))

    # 4. Internal API behavior
    if INTERNAL_API_SECRET:
        # Test without header
        r = requests.get(f"{BACKEND_BASE_URL}/api/internal/general-products/search",
                         params={"q": "test", "mode": "GENERAL_COMPARE", "role": "USER", "limit": "1"}, timeout=5)
        if r.status_code == 403:
            check("Internal API: missing header rejected", PASS)
        else:
            check("Internal API: missing header rejected", FAIL, f"Expected 403 got {r.status_code}")

        # Test with correct header
        r = requests.get(f"{BACKEND_BASE_URL}/api/internal/general-products/search",
                         params={"q": "test", "mode": "GENERAL_COMPARE", "role": "USER", "limit": "1"},
                         headers={"X-Internal-Api-Key": INTERNAL_API_SECRET}, timeout=5)
        check("Internal API: correct header accepted", PASS if r.status_code == 200 else FAIL,
              f"HTTP {r.status_code}")
    else:
        check("Internal API secret", SKIP,
              "INTERNAL_API_SECRET not set — dev mode, endpoints open")
        # Quick check endpoint works
        r = requests.get(f"{BACKEND_BASE_URL}/api/internal/general-products/search",
                         params={"q": "sofa", "mode": "GENERAL_COMPARE", "role": "USER", "limit": "1"}, timeout=5)
        check("Internal API dev mode accessible", PASS if r.status_code == 200 else FAIL,
              f"HTTP {r.status_code}")

    # 5. Data checks via backend
    session = admin_session()
    if session:
        r = session.get(f"{BACKEND_BASE_URL}/api/admin/general/quality-summary", timeout=10)
        if r.status_code == 200:
            data = r.json()
            total = data.get("totalProducts", 0)
            sources = data.get("sourceCount", 0)
            check("General layer data", PASS if total > 0 else FAIL,
                  f"{total} products, {sources} sources")
        else:
            check("General layer data", FAIL, f"HTTP {r.status_code}")
    else:
        check("General layer data", SKIP, "Admin login unavailable")

    # 6. Quick general_compare search
    try:
        r = requests.get(f"{BACKEND_BASE_URL}/api/internal/general-products/search",
                         params={"q": "sofa", "mode": "GENERAL_COMPARE", "role": "USER", "limit": "3"},
                         headers=internal_headers(), timeout=10)
        if r.status_code == 200:
            items = r.json().get("items", [])
            check("General compare search", PASS if len(items) > 0 else FAIL,
                  f"{len(items)} items returned")
        else:
            check("General compare search", FAIL, f"HTTP {r.status_code}")
    except Exception as e:
        check("General compare search", FAIL, str(e))

    # 7. Quick market_price insight
    try:
        r = requests.get(f"{BACKEND_BASE_URL}/api/internal/market-price/insight",
                         params={"q": "sofa", "mode": "MARKET_PRICE", "role": "USER"},
                         headers=internal_headers(), timeout=10)
        if r.status_code == 200:
            stats = r.json().get("stats", {})
            count = stats.get("sampleCount", 0)
            check("Market price insight", PASS if count > 0 else FAIL,
                  f"{count} samples, confidence={stats.get('confidence', 'N/A')}")
        else:
            check("Market price insight", FAIL, f"HTTP {r.status_code}")
    except Exception as e:
        check("Market price insight", FAIL, str(e))

    # 8. FastAPI health data check
    try:
        r = requests.get(f"{CHATBOT_BASE_URL}/healthz", timeout=5)
        if r.status_code == 200:
            data = r.json()
            kb_loaded = data.get("kb_loaded", False)
            kb_dir = data.get("kb_dir", "")
            check("FastAPI KB loaded", PASS if kb_loaded else FAIL,
                  f"kb_dir={kb_dir}, kb_loaded={kb_loaded}")
        else:
            check("FastAPI KB loaded", FAIL, f"HTTP {r.status_code}")
    except Exception as e:
        check("FastAPI KB loaded", FAIL, str(e))

    # 9. UI static
    try:
        r = requests.get(f"{BACKEND_BASE_URL}/admin/", timeout=5)
        check("Admin UI", PASS if r.status_code == 200 else FAIL, f"HTTP {r.status_code}")
    except Exception as e:
        check("Admin UI", FAIL, str(e))

    # Summary
    passed = sum(1 for c in results["checks"] if c["status"] == PASS)
    failed = sum(1 for c in results["checks"] if c["status"] == FAIL)
    skipped = sum(1 for c in results["checks"] if c["status"] == SKIP)
    results["passed"] = passed
    results["failed"] = failed
    results["skipped"] = skipped
    results["overall"] = PASS if failed == 0 and passed > 0 else (FAIL if failed > 0 else SKIP)

    save_evidence("docker_smoke_results.json", results)

    _logger.info("\n=== Smoke Summary ===")
    _logger.info("Pass: %d  Fail: %d  Skip: %d", passed, failed, skipped)
    _logger.info("Overall: %s", results["overall"])
    return 0 if failed == 0 else 1


def _save_and_exit():
    save_evidence("docker_smoke_results.json", results)
    sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
