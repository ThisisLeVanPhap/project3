import json
import os
import tempfile
import unittest

from tools.evaluate_sales_conversations import evaluate_scenarios, main


class SalesConversationEvaluatorTests(unittest.TestCase):
    def test_evaluator_report_pass(self):
        scenarios = [
            {
                "id": "pass-case",
                "turns": ["Mình mua P1, số 0901234567"],
                "mocked_recommended_products": [
                    {
                        "after_turn": 0,
                        "products": [
                            {
                                "sku": "SF-700",
                                "product_name": "Sofa Nami",
                                "source_url": "https://shop.test/sofa-nami",
                                "price": 700000,
                            }
                        ],
                    }
                ],
                "expected": {
                    "final_intent": "contact_provided",
                    "selected_product_sku": "SF-700",
                    "contact_extracted": True,
                    "quantity": 1,
                    "lead_status": "hot",
                    "purchase_request_status": "draft",
                    "handoff_required": False,
                    "should_ask_missing_info": False,
                },
            }
        ]

        report = evaluate_scenarios(scenarios)

        self.assertEqual(report["summary"]["total_scenarios"], 1)
        self.assertEqual(report["summary"]["pass_rate"], 1.0)
        self.assertEqual(report["failed_cases"], [])

    def test_evaluator_report_fail(self):
        scenarios = [
            {
                "id": "fail-case",
                "turns": ["Thôi để sau"],
                "expected": {
                    "final_intent": "purchase_intent",
                    "contact_extracted": False,
                    "lead_status": "hot",
                    "purchase_request_status": "draft",
                    "handoff_required": False,
                    "should_ask_missing_info": False,
                },
            }
        ]

        report = evaluate_scenarios(scenarios)

        self.assertEqual(report["summary"]["total_scenarios"], 1)
        self.assertEqual(report["summary"]["pass_rate"], 0.0)
        self.assertEqual(report["failed_cases"][0]["id"], "fail-case")

    def test_cli_writes_report(self):
        scenario = {
            "id": "cli-case",
            "turns": ["Cho mình gặp nhân viên"],
            "expected": {
                "final_intent": "handoff_request",
                "contact_extracted": False,
                "lead_status": "cold",
                "purchase_request_status": "needs_product",
                "handoff_required": True,
                "should_ask_missing_info": False,
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            scenarios_path = os.path.join(tmpdir, "scenarios.json")
            output_path = os.path.join(tmpdir, "report.json")
            with open(scenarios_path, "w", encoding="utf-8") as handle:
                json.dump([scenario], handle)

            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = [
                    "evaluate_sales_conversations.py",
                    "--scenarios",
                    scenarios_path,
                    "--output",
                    output_path,
                ]
                self.assertEqual(main(), 0)
            finally:
                __import__("sys").argv = old_argv

            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "r", encoding="utf-8") as handle:
                report = json.load(handle)
            self.assertEqual(report["summary"]["pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
