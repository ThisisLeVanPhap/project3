import os
import unittest

from tools.evaluate_sales_runtime import evaluate_scenarios


def scenario(scenario_id, turns, gen=None, tenant_id="eval-tenant", conversation_id=None):
    return {
        "id": scenario_id,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id or f"{scenario_id}-conv",
        "gen": gen or {"answer_mode": "template", "sales_mode": "active"},
        "turns": turns,
    }


class SalesRuntimeEvaluatorTests(unittest.TestCase):
    def test_e2e_small_scenario_pass(self):
        report = evaluate_scenarios([
            scenario("small-pass", [
                {"message": "Có rèm nào dưới 1 triệu không?", "expect": {"model": "product-template"}},
                {
                    "message": "tôi lấy P1",
                    "expect": {
                        "model": "sales-template",
                        "debug": {"purchase_request_status": "needs_contact", "sales_action_taken": "ask_contact"},
                    },
                },
            ])
        ])

        self.assertEqual(report["summary"]["passed"], 1)
        self.assertEqual(report["summary"]["pass_rate"], 1.0)

    def test_failed_expectation_is_reported_clearly(self):
        report = evaluate_scenarios([
            scenario("expected-fail", [
                {"message": "Có rèm nào dưới 1 triệu không?", "expect": {"model": "sales-template"}}
            ])
        ])

        self.assertEqual(report["summary"]["passed"], 0)
        failure = report["failed"][0]
        self.assertEqual(failure["scenario_id"], "expected-fail")
        self.assertEqual(failure["turn_index"], 0)
        self.assertIn("model expected", failure["reason"])

    def test_product_reference_question_does_not_create_draft(self):
        report = evaluate_scenarios([
            scenario("reference-question", [
                {"message": "Có rèm nào dưới 1 triệu không?", "expect": {"model": "product-template"}},
                {
                    "message": "P1 có kích thước bao nhiêu?",
                    "expect": {
                        "model": "product-template",
                        "product_reference_safety": True,
                        "debug": {"sales_action_taken": "none", "purchase_request_status": None},
                    },
                },
            ])
        ])

        self.assertEqual(report["summary"]["metrics"]["product_reference_safety_rate"], 1.0)
        self.assertEqual(report["failed"], [])

    def test_contact_masking_metric(self):
        report = evaluate_scenarios([
            scenario("contact-mask", [
                {"message": "Có rèm nào dưới 1 triệu không?", "expect": {"model": "product-template"}},
                {
                    "message": "tôi lấy P1, số tôi 0987654321",
                    "expect": {
                        "model": "sales-template",
                        "debug_not_contains": ["0987654321"],
                        "contact_masking": True,
                        "debug": {"purchase_request_status": "draft"},
                    },
                },
            ])
        ])

        self.assertEqual(report["summary"]["metrics"]["contact_masking_rate"], 1.0)
        self.assertEqual(report["failed"], [])

    def test_tenant_isolation_scenario_pass(self):
        report = evaluate_scenarios([
            {
                "id": "tenant-isolation",
                "tenant_id": "tenant-a",
                "conversation_id": "same-conv",
                "gen": {"answer_mode": "template", "sales_mode": "active"},
                "turns": [
                    {"message": "Có rèm nào dưới 1 triệu không?", "expect": {"model": "product-template"}},
                    {
                        "tenant_id": "tenant-b",
                        "message": "tôi lấy P1",
                        "expect": {
                            "model": "sales-template",
                            "tenant_isolation": True,
                            "debug": {"purchase_request_status": "needs_product", "sales_action_taken": "ask_product"},
                        },
                    },
                ],
            }
        ])

        self.assertEqual(report["summary"]["metrics"]["tenant_isolation_rate"], 1.0)
        self.assertEqual(report["failed"], [])

    def test_missing_conversation_id_scenario_pass(self):
        report = evaluate_scenarios([
            {
                "id": "missing-conversation",
                "tenant_id": "tenant-a",
                "gen": {"answer_mode": "template", "sales_mode": "active"},
                "turns": [
                    {
                        "message": "Có rèm nào dưới 1 triệu không?",
                        "expect": {
                            "model": "product-template",
                            "debug": {
                                "sales_state_persistent": False,
                                "sales_state_warning": "missing_conversation_id_ephemeral_state",
                            },
                        },
                    },
                    {
                        "message": "tôi lấy P1",
                        "expect": {
                            "model": "sales-template",
                            "debug": {"purchase_request_status": "needs_product", "sales_action_taken": "ask_product"},
                        },
                    },
                ],
            }
        ])

        self.assertEqual(report["failed"], [])

    def test_shadow_mode_no_override_detected(self):
        report = evaluate_scenarios([
            scenario(
                "shadow",
                [
                    {
                        "message": "tôi lấy P1",
                        "expect": {
                            "model": "product-template",
                            "shadow_no_override": True,
                            "debug": {"sales_mode": "shadow"},
                        },
                    }
                ],
                gen={"answer_mode": "template", "sales_mode": "shadow"},
            )
        ])

        self.assertEqual(report["summary"]["metrics"]["shadow_no_override_rate"], 1.0)
        self.assertEqual(report["failed"], [])

    def test_evaluator_uses_stub_runtime_not_llm_or_network(self):
        original = os.environ.get("CHATBOT_TEST_MODE")
        report = evaluate_scenarios([
            scenario("stub-only", [
                {"message": "Có rèm nào dưới 1 triệu không?", "expect": {"model": "product-template"}}
            ])
        ])

        self.assertEqual(report["failed"], [])
        self.assertEqual(os.environ.get("CHATBOT_TEST_MODE"), original)


if __name__ == "__main__":
    unittest.main()
