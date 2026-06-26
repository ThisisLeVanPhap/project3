#!/usr/bin/env python3
"""Run all eval scenarios for 3 capabilities."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure scripts/eval is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_common import (
    BACKEND_BASE_URL,
    CHATBOT_BASE_URL,
    check_backend,
    check_chatbot,
    save_evidence,
    save_summary,
)
from test_general_compare_scenarios import run as run_general_compare
from test_market_price_scenarios import run as run_market_price
from test_tenant_sales_scenarios import run as run_tenant_sales

_logger = logging.getLogger("eval.run_all")

SUMMARY_FIELDS = [
    "generalCompare", "marketPrice", "tenantSales",
]


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    _logger.info("=== Eval Harness ===")
    _logger.info("Backend: %s", BACKEND_BASE_URL)
    _logger.info("Chatbot: %s", CHATBOT_BASE_URL)

    backend_ok = check_backend()
    chatbot_ok = check_chatbot()
    _logger.info("Backend available: %s", backend_ok)
    _logger.info("Chatbot available: %s", chatbot_ok)

    all_results = {}

    _logger.info("\n--- General Compare ---")
    gc_result = run_general_compare()
    all_results["generalCompare"] = gc_result

    _logger.info("\n--- Market Price ---")
    mp_result = run_market_price()
    all_results["marketPrice"] = mp_result

    _logger.info("\n--- Tenant Sales ---")
    ts_result = run_tenant_sales()
    all_results["tenantSales"] = ts_result

    # Collect totals
    total_pass = 0
    total_fail = 0
    total_skip = 0
    for mode_key, mode_data in all_results.items():
        for category, scenarios in mode_data.items():
            for s in scenarios:
                if s.status == "PASS":
                    total_pass += 1
                elif s.status == "FAIL":
                    total_fail += 1
                else:
                    total_skip += 1

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "backend_base_url": BACKEND_BASE_URL,
        "chatbot_base_url": CHATBOT_BASE_URL,
        "backend_available": backend_ok,
        "chatbot_available": chatbot_ok,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "total_skipped": total_skip,
        "overall": "PASS" if total_fail == 0 and total_pass > 0 else "PARTIAL" if total_pass > 0 else "FAIL",
    }

    save_evidence("eval_summary.json", summary)
    _logger.info("\n=== Eval Summary ===")
    _logger.info("Pass: %d  Fail: %d  Skip: %d", total_pass, total_fail, total_skip)
    _logger.info("Overall: %s", summary["overall"])
    _logger.info("Evidence: tmp/eval/")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
