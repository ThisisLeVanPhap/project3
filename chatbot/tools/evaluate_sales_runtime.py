import argparse
import json
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("CHATBOT_TEST_MODE", "1")
os.environ.setdefault("LOG_DIR", tempfile.mkdtemp(prefix="sales-runtime-eval-"))

CHATBOT_DIR = Path(__file__).resolve().parents[1]
if str(CHATBOT_DIR) not in sys.path:
    sys.path.insert(0, str(CHATBOT_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app import server  # noqa: E402
from app.retrievers import RetrievalResult  # noqa: E402
from app.sales_handoff import InMemorySalesHandoffService, build_sales_handoff_service  # noqa: E402
from app.sales_handoff_store import mask_pii  # noqa: E402


DEFAULT_PRODUCTS = [
    {
        "doc_id": "runtime-p1",
        "product_name": "Rèm cuốn tranh cao cấp GHO-607",
        "sku": "GHO-607",
        "price": 700000,
        "source_url": "https://example.test/rem-gho-607",
        "material": "Vải polyester",
        "dimensions": "120 x 180 cm",
        "color": "Trắng",
    },
    {
        "doc_id": "runtime-p2",
        "product_name": "Rèm vải chống nắng R2",
        "sku": "REM-R2",
        "price": 900000,
        "source_url": "https://example.test/rem-r2",
        "material": "Vải chống nắng",
        "dimensions": "140 x 200 cm",
        "color": "Ghi",
    },
    {
        "doc_id": "runtime-p3",
        "product_name": "Rèm roman phòng khách R3",
        "sku": "REM-R3",
        "price": 1200000,
        "source_url": "https://example.test/rem-r3",
        "material": "Vải bố",
        "dimensions": "160 x 220 cm",
        "color": "Kem",
    },
]


class FakeRuntimeRetriever:
    def __init__(self, products: Optional[List[Dict[str, Any]]] = None):
        self.products = products or DEFAULT_PRODUCTS

    def search(self, query: str, k: int = 4):
        return [_product_hit(product, idx) for idx, product in enumerate(self.products[:k], start=1)]


def _product_hit(product: Dict[str, Any], idx: int) -> RetrievalResult:
    return RetrievalResult(
        doc_id=product.get("doc_id") or f"runtime-p{idx}",
        chunk_id=f"{product.get('doc_id') or idx}#0",
        title=product["product_name"],
        text=(
            f"{product['product_name']} có SKU {product['sku']}, "
            f"giá {product['price']} VND, chất liệu {product.get('material', '')}, "
            f"kích thước {product.get('dimensions', '')}."
        ),
        source=product["source_url"],
        score=10.0 - idx,
        metadata={
            "doc_type": "product",
            "product_name": product["product_name"],
            "category": "Rèm",
            "price": product["price"],
            "currency": "VND",
            "sku": product["sku"],
            "material": product.get("material", ""),
            "dimensions": product.get("dimensions", ""),
            "color": product.get("color", ""),
            "source_url": product["source_url"],
        },
    )


class RuntimeHarness:
    def __init__(self):
        self.previous_kb = server.KB
        self.previous_by_mode = dict(server.KB_BY_MODE)
        self.previous_env_mode = os.environ.get("SALES_CONVERSATION_MODE")
        self.previous_test_mode = os.environ.get("CHATBOT_TEST_MODE")
        self.previous_handoff_service = server.SALES_HANDOFF_SERVICE
        self.handoff_base_count = 0

    def __enter__(self):
        os.environ["CHATBOT_TEST_MODE"] = "1"
        server.KB = FakeRuntimeRetriever()
        server.KB_BY_MODE.clear()
        server.KB_BY_MODE["keyword"] = server.KB
        server.SALES_STATE_STORE.clear()
        server.SALES_HANDOFF_SERVICE = build_sales_handoff_service()
        server._set_ready(True, None)
        self.client = TestClient(server.app)
        return self

    def __exit__(self, exc_type, exc, tb):
        server.KB = self.previous_kb
        server.KB_BY_MODE.clear()
        server.KB_BY_MODE.update(self.previous_by_mode)
        server.SALES_STATE_STORE.clear()
        server.SALES_HANDOFF_SERVICE = self.previous_handoff_service
        if self.previous_env_mode is None:
            os.environ.pop("SALES_CONVERSATION_MODE", None)
        else:
            os.environ["SALES_CONVERSATION_MODE"] = self.previous_env_mode
        if self.previous_test_mode is None:
            os.environ.pop("CHATBOT_TEST_MODE", None)
        else:
            os.environ["CHATBOT_TEST_MODE"] = self.previous_test_mode

    def post_turn(self, scenario: Dict[str, Any], turn: Dict[str, Any]) -> Dict[str, Any]:
        if turn.get("handoff_fail_next"):
            server.SALES_HANDOFF_SERVICE.fail_next = True
        gen = {
            "provider": "stub",
            "mode": "general_compare",
            "retrieval_mode": "keyword",
            "retrieval_top_k": 4,
            "answer_mode": "template",
            "sales_mode": "active",
        }
        gen.update(scenario.get("gen") or {})
        gen.update(turn.get("gen") or {})
        payload = {
            "message": turn["message"],
            "history": turn.get("history", []),
            "tenant_id": turn.get("tenant_id", scenario.get("tenant_id", "runtime-tenant")),
            "channel": turn.get("channel", scenario.get("channel", "web")),
            "gen": gen,
        }
        conversation_id = turn.get("conversation_id", scenario.get("conversation_id"))
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        response = self.client.post("/chat", json=payload)
        try:
            body = response.json()
        except Exception:
            body = {"raw_text": response.text}
        body["_http_status"] = response.status_code
        body["_handoff_sent_count"] = len(getattr(server.SALES_HANDOFF_SERVICE, "sent_payloads", [])) - self.handoff_base_count
        return body


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _get_path(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            return None
    return current


def _debug_text(actual: Dict[str, Any]) -> str:
    return json.dumps(actual.get("debug") or {}, ensure_ascii=False, sort_keys=True)


def _safe_actual_for_report(actual: Dict[str, Any]) -> Dict[str, Any]:
    return mask_pii(deepcopy(actual))


def _check_expectation(actual: Dict[str, Any], expect: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    reply = actual.get("reply") or ""
    debug = actual.get("debug") or {}

    if actual.get("_http_status") != expect.get("http_status", 200):
        failures.append(f"http_status expected={expect.get('http_status', 200)} actual={actual.get('_http_status')}")
    if "model" in expect and actual.get("model") != expect["model"]:
        failures.append(f"model expected={expect['model']} actual={actual.get('model')}")
    for value in expect.get("reply_contains_any", []):
        if value in reply:
            break
    else:
        if expect.get("reply_contains_any"):
            failures.append(f"reply missing any of {expect['reply_contains_any']}")
    for value in expect.get("reply_contains_all", []):
        if value not in reply:
            failures.append(f"reply missing {value!r}")
    for value in expect.get("reply_not_contains", []):
        if value.lower() in reply.lower():
            failures.append(f"reply unexpectedly contains {value!r}")

    for key, expected_value in (expect.get("debug") or {}).items():
        actual_value = _get_path({"debug": debug}, f"debug.{key}")
        if actual_value != expected_value:
            failures.append(f"debug.{key} expected={expected_value!r} actual={actual_value!r}")
    for key in expect.get("debug_absent", []):
        if _get_path({"debug": debug}, f"debug.{key}") is not None:
            failures.append(f"debug.{key} expected absent actual={_get_path({'debug': debug}, f'debug.{key}')!r}")
    for value in expect.get("debug_not_contains", []):
        if value in _debug_text(actual):
            failures.append(f"debug unexpectedly contains raw value {value!r}")
    for key, expected_value in (expect.get("fields") or {}).items():
        actual_value = _get_path(actual, key)
        if actual_value != expected_value:
            failures.append(f"{key} expected={expected_value!r} actual={actual_value!r}")
    if "handoff_sent_count" in expect and actual.get("_handoff_sent_count") != expect["handoff_sent_count"]:
        failures.append(f"handoff_sent_count expected={expect['handoff_sent_count']!r} actual={actual.get('_handoff_sent_count')!r}")

    if expect.get("selected_product_sku"):
        products = debug.get("selected_products") or []
        selected = products[0].get("sku") if products else None
        if selected != expect["selected_product_sku"]:
            failures.append(f"selected_product_sku expected={expect['selected_product_sku']!r} actual={selected!r}")
    if expect.get("no_sales_override") and actual.get("model") == "sales-template":
        failures.append("expected no sales-template override")
    if expect.get("no_external_flow", True) and actual.get("trigger_purchase_request"):
        failures.append("trigger_purchase_request should be false")
    return failures


def _metric_flags(expect: Dict[str, Any], actual: Dict[str, Any], turn_passed: bool) -> Dict[str, Optional[bool]]:
    debug = actual.get("debug") or {}
    flags: Dict[str, Optional[bool]] = {
        "purchase_status_accuracy": None,
        "product_reference_safety_rate": None,
        "contact_masking_rate": None,
        "tenant_isolation_rate": None,
        "shadow_no_override_rate": None,
        "no_external_flow_rate": not actual.get("trigger_purchase_request", False),
        "confirmation_required_rate": None,
        "handoff_only_after_confirmation_rate": None,
        "confirmation_cancel_rate": None,
        "no_raw_contact_debug_rate": None,
        "handoff_failure_handling_rate": None,
    }
    if "purchase_request_status" in (expect.get("debug") or {}):
        flags["purchase_status_accuracy"] = debug.get("purchase_request_status") == expect["debug"]["purchase_request_status"]
    if expect.get("product_reference_safety"):
        flags["product_reference_safety_rate"] = actual.get("model") != "sales-template" and debug.get("sales_action_taken") == "none"
    if expect.get("contact_masking"):
        flags["contact_masking_rate"] = all(value not in _debug_text(actual) for value in expect.get("debug_not_contains", []))
    if expect.get("tenant_isolation"):
        flags["tenant_isolation_rate"] = turn_passed
    if expect.get("shadow_no_override"):
        flags["shadow_no_override_rate"] = actual.get("model") != "sales-template" and debug.get("sales_mode") == "shadow"
    if expect.get("confirmation_required"):
        flags["confirmation_required_rate"] = (
            debug.get("confirmation_status") == "pending"
            and debug.get("handoff_status") == "pending_confirmation"
            and debug.get("sales_action_taken") == "ask_confirmation"
        )
    if expect.get("handoff_after_confirmation"):
        flags["handoff_only_after_confirmation_rate"] = (
            debug.get("confirmation_status") == "confirmed"
            and debug.get("handoff_status") == "sent"
            and debug.get("sales_action_taken") == "handoff_sent"
        )
    if expect.get("confirmation_cancel"):
        flags["confirmation_cancel_rate"] = (
            debug.get("confirmation_status") == "cancelled"
            and debug.get("handoff_status") == "cancelled"
            and debug.get("sales_action_taken") == "confirmation_cancelled"
        )
    if expect.get("no_raw_contact_debug"):
        flags["no_raw_contact_debug_rate"] = all(value not in _debug_text(actual) for value in expect.get("debug_not_contains", []))
    if expect.get("handoff_failure_handling"):
        flags["handoff_failure_handling_rate"] = (
            debug.get("handoff_status") == "failed"
            and debug.get("sales_action_taken") == "handoff_failed"
        )
    return flags


def evaluate_scenarios(scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    failed: List[Dict[str, Any]] = []
    cases: List[Dict[str, Any]] = []
    metric_values: Dict[str, List[bool]] = {
        "purchase_status_accuracy": [],
        "product_reference_safety_rate": [],
        "contact_masking_rate": [],
        "tenant_isolation_rate": [],
        "shadow_no_override_rate": [],
        "no_external_flow_rate": [],
        "confirmation_required_rate": [],
        "handoff_only_after_confirmation_rate": [],
        "confirmation_cancel_rate": [],
        "no_raw_contact_debug_rate": [],
        "handoff_failure_handling_rate": [],
    }
    turns_total = 0
    turns_passed = 0

    with RuntimeHarness() as harness:
        for scenario in scenarios:
            original_env = os.environ.get("SALES_CONVERSATION_MODE")
            if "env" in scenario:
                if scenario["env"].get("SALES_CONVERSATION_MODE") is None:
                    os.environ.pop("SALES_CONVERSATION_MODE", None)
                else:
                    os.environ["SALES_CONVERSATION_MODE"] = scenario["env"]["SALES_CONVERSATION_MODE"]
            harness.handoff_base_count = len(getattr(server.SALES_HANDOFF_SERVICE, "sent_payloads", []))
            scenario_failed: List[Dict[str, Any]] = []
            turn_results: List[Dict[str, Any]] = []
            for turn_index, turn in enumerate(scenario.get("turns", [])):
                turns_total += 1
                actual = harness.post_turn(scenario, turn)
                expect = turn.get("expect") or {}
                failures = _check_expectation(actual, expect)
                turn_passed = not failures
                if turn_passed:
                    turns_passed += 1
                flags = _metric_flags(expect, actual, turn_passed)
                for metric, value in flags.items():
                    if value is not None:
                        metric_values[metric].append(value)
                result = {
                    "turn_index": turn_index,
                    "message": mask_pii(turn.get("message")),
                    "passed": turn_passed,
                    "actual": _safe_actual_for_report(actual),
                    "failures": failures,
                }
                turn_results.append(result)
                for reason in failures:
                    failure = {
                        "scenario_id": scenario.get("id"),
                        "turn_index": turn_index,
                        "message": mask_pii(turn.get("message")),
                        "expected": mask_pii(expect),
                        "actual": _safe_actual_for_report({
                            "model": actual.get("model"),
                            "reply": actual.get("reply"),
                            "debug": actual.get("debug"),
                            "trigger_purchase_request": actual.get("trigger_purchase_request"),
                        }),
                        "reason": reason,
                    }
                    failed.append(failure)
                    scenario_failed.append(failure)
            cases.append({
                "id": scenario.get("id"),
                "passed": not scenario_failed,
                "turns": turn_results,
            })
            if "env" in scenario:
                if original_env is None:
                    os.environ.pop("SALES_CONVERSATION_MODE", None)
                else:
                    os.environ["SALES_CONVERSATION_MODE"] = original_env

    total_scenarios = len(scenarios)
    passed = sum(1 for case in cases if case["passed"])

    def ratio(values: List[bool]) -> float:
        return (sum(1 for value in values if value) / len(values)) if values else 1.0

    return {
        "summary": {
            "total_scenarios": total_scenarios,
            "passed": passed,
            "pass_rate": passed / total_scenarios if total_scenarios else 0.0,
            "turns_total": turns_total,
            "turns_passed": turns_passed,
            "metrics": {metric: ratio(values) for metric, values in metric_values.items()},
            "failed": deepcopy(failed),
        },
        "failed": failed,
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate /chat runtime sales multi-turn behavior.")
    parser.add_argument("--scenarios", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    scenarios = load_json(args.scenarios)
    report = evaluate_scenarios(scenarios)
    write_json(args.output, report)
    print(json.dumps(report["summary"], ensure_ascii=True, indent=2))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
