import argparse
import json
import os
import sys
from typing import Any, Dict, List

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CHATBOT_DIR = os.path.dirname(CURRENT_DIR)
if CHATBOT_DIR not in sys.path:
    sys.path.insert(0, CHATBOT_DIR)

from app.purchase_request import build_purchase_request_draft  # noqa: E402
from app.sales_state import SalesConversationState, apply_message_to_state, update_recommended_products  # noqa: E402


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _products_for_turn(scenario: Dict[str, Any], turn_index: int) -> List[Dict[str, Any]]:
    mocked = scenario.get("mocked_recommended_products")
    if isinstance(mocked, list):
        if mocked and all(isinstance(item, dict) and "after_turn" in item for item in mocked):
            products: List[Dict[str, Any]] = []
            for event in mocked:
                if int(event.get("after_turn", -1)) == turn_index:
                    products = event.get("products") or []
            return products
        if turn_index == 0:
            return mocked
    if isinstance(mocked, dict):
        key = str(turn_index)
        return mocked.get(key) or mocked.get(turn_index) or []
    return []


def simulate_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    state = SalesConversationState(
        tenant_id=scenario.get("tenant_id"),
        conversation_id=scenario.get("id"),
    )
    final_turn_result: Dict[str, Any] = {}
    draft: Dict[str, Any] = {}

    for turn_index, message in enumerate(scenario.get("turns", [])):
        products = _products_for_turn(scenario, turn_index)
        if products:
            update_recommended_products(state, products)
        final_turn_result = apply_message_to_state(state, message)
        draft = build_purchase_request_draft(state, message)

    return {
        "scenario_id": scenario.get("id"),
        "state": {
            "lead_status": state.lead_status,
            "lead_score": state.lead_score,
            "selected_products": state.selected_products,
            "contact": state.contact,
            "handoff_required": state.handoff_required,
            "missing_fields": state.missing_fields,
        },
        "final_intent": (final_turn_result.get("slots") or {}).get("intent", "unknown"),
        "purchase_request": draft,
        "resolved_product": getattr(final_turn_result.get("resolved_product"), "product", None),
    }


def _selected_matches(actual_products: List[Dict[str, Any]], expected: Dict[str, Any]) -> bool:
    expected_sku = expected.get("selected_product_sku")
    expected_url = expected.get("selected_product_source_url")
    if not expected_sku and not expected_url:
        return not actual_products
    for product in actual_products:
        if expected_sku and product.get("sku") == expected_sku:
            return True
        if expected_url and product.get("source_url") == expected_url:
            return True
    return False


def evaluate_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    actual = simulate_scenario(scenario)
    expected = scenario.get("expected", {})
    state = actual["state"]
    draft = actual["purchase_request"] or {}
    failures: List[str] = []

    checks = {
        "intent": actual["final_intent"] == expected.get("final_intent"),
        "product_resolution": _selected_matches(state["selected_products"], expected),
        "contact_extraction": bool(state["contact"].get("phone") or state["contact"].get("email")) == bool(expected.get("contact_extracted")),
        "purchase_request": draft.get("status") == expected.get("purchase_request_status"),
        "lead_status": state["lead_status"] == expected.get("lead_status"),
        "handoff": bool(state["handoff_required"]) == bool(expected.get("handoff_required")),
        "missing_info": bool(state["missing_fields"]) == bool(expected.get("should_ask_missing_info")),
    }
    if "quantity" in expected:
        checks["quantity"] = (draft.get("products") or [{}])[0].get("quantity") == expected.get("quantity")

    for name, passed in checks.items():
        if not passed:
            failures.append(f"{name}: expected={expected.get(name) if name in expected else expected} actual={actual}")

    return {
        "id": scenario.get("id"),
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "actual": actual,
    }


def evaluate_scenarios(scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    cases = [evaluate_scenario(scenario) for scenario in scenarios]
    total = len(cases)

    def accuracy(check_name: str) -> float:
        if not total:
            return 0.0
        return sum(1 for case in cases if case["checks"].get(check_name)) / total

    passed = sum(1 for case in cases if case["passed"])
    return {
        "summary": {
            "total_scenarios": total,
            "pass_rate": passed / total if total else 0.0,
            "intent_accuracy": accuracy("intent"),
            "product_resolution_accuracy": accuracy("product_resolution"),
            "contact_extraction_accuracy": accuracy("contact_extraction"),
            "purchase_request_accuracy": accuracy("purchase_request"),
            "lead_status_accuracy": accuracy("lead_status"),
        },
        "failed_cases": [
            {"id": case["id"], "failures": case["failures"], "actual": case["actual"]}
            for case in cases
            if not case["passed"]
        ],
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate rule-based sales conversation state.")
    parser.add_argument("--scenarios", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    scenarios = _load_json(args.scenarios)
    report = evaluate_scenarios(scenarios)
    _write_json(args.output, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if not report["failed_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
