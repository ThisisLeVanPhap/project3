"""Tests for BackendMarketPriceInsightProvider and market price reply renderer."""

import json
import unittest
from unittest.mock import patch, MagicMock

import requests

from app.market_price_insight_provider import (
    BackendMarketPriceInsightProvider,
    PriceInsight,
    build_market_price_insight_provider,
)
from app.market_price_reply import (
    build_market_price_insight_reply,
    _fmt_price,
    _confidence_label,
)


SAMPLE_INSIGHT = {
    "query": "sofa vai 2m gia 8 trieu",
    "category": "Sofa",
    "material": "vai",
    "inputPrice": 8000000.0,
    "stats": {
        "minPrice": 3900000.0,
        "p25Price": 5200000.0,
        "medianPrice": 6900000.0,
        "p75Price": 9200000.0,
        "maxPrice": 18000000.0,
        "sampleCount": 37,
        "sourceCount": 1,
        "currency": "VND",
        "confidence": "MEDIUM",
    },
    "samples": [
        {"name": "Sofa vai SFG041", "price": 6500000.0, "sourceName": "Go Trang Tri",
         "sourceUrl": "https://gotrangtri.vn/sofa", "material": "vai", "category": "Sofa",
         "sourceCode": "gotrangtri"},
        {"name": "Sofa vai SFG042", "price": 8900000.0, "sourceName": "Go Trang Tri",
         "sourceUrl": "https://gotrangtri.vn/sofa2", "material": "vai", "category": "Sofa",
         "sourceCode": "gotrangtri"},
    ],
    "assessment": {
        "inputPrice": 8000000.0,
        "position": "between_median_and_p75",
        "label": "nam trong khoang pho bien",
    },
}

EMPTY_INSIGHT = {
    "query": "san pham khong ton tai",
    "category": None, "material": None, "inputPrice": None,
    "stats": {"sampleCount": 0, "sourceCount": 0, "currency": "VND", "confidence": "INSUFFICIENT"},
    "samples": [],
    "assessment": None,
}


class MarketPriceInsightProviderTests(unittest.TestCase):

    def setUp(self):
        self.provider = BackendMarketPriceInsightProvider(base_url="http://test-backend:8080")

    @patch("app.market_price_insight_provider.requests.get")
    def test_get_insight_returns_stats(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_INSIGHT
        mock_get.return_value = mock_resp

        result = self.provider.get_insight("sofa vai 2m gia 8 trieu")
        self.assertIsNotNone(result)
        self.assertEqual(result.stats.get("sampleCount"), 37)
        self.assertEqual(result.stats.get("medianPrice"), 6900000.0)
        self.assertEqual(len(result.samples), 2)
        self.assertIsNotNone(result.assessment)

    @patch("app.market_price_insight_provider.requests.get")
    def test_get_insight_sends_role_user(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_INSIGHT
        mock_get.return_value = mock_resp

        self.provider.get_insight("sofa")
        params = mock_get.call_args[1].get("params", {})
        self.assertEqual(params.get("role"), "USER")

    @patch("app.market_price_insight_provider.requests.get")
    def test_secret_header_sent_when_configured(self, mock_get):
        self.provider._internal_secret = "secret-123"
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_INSIGHT
        mock_get.return_value = mock_resp

        self.provider.get_insight("sofa")
        headers = mock_get.call_args[1].get("headers", {})
        self.assertEqual(headers.get("X-Internal-Api-Key"), "secret-123")

    @patch("app.market_price_insight_provider.requests.get")
    def test_401_returns_none(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        result = self.provider.get_insight("sofa")
        self.assertIsNone(result)

    @patch("app.market_price_insight_provider.requests.get")
    def test_403_returns_none(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp

        result = self.provider.get_insight("sofa")
        self.assertIsNone(result)

    @patch("app.market_price_insight_provider.requests.get")
    def test_500_returns_none(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 500
        mock_resp.text = "Error"
        mock_get.return_value = mock_resp

        result = self.provider.get_insight("sofa")
        self.assertIsNone(result)

    @patch("app.market_price_insight_provider.requests.get")
    def test_timeout_returns_none(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("timeout")
        result = self.provider.get_insight("sofa")
        self.assertIsNone(result)

    def test_empty_query_returns_none(self):
        result = self.provider.get_insight("")
        self.assertIsNone(result)

    @patch("app.market_price_insight_provider.requests.get")
    def test_no_data_returns_none(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = EMPTY_INSIGHT
        mock_get.return_value = mock_resp

        result = self.provider.get_insight("khong ton tai")
        self.assertIsNone(result)

    def test_build_provider(self):
        provider = build_market_price_insight_provider()
        self.assertIsNotNone(provider)


class MarketPriceReplyRendererTests(unittest.TestCase):

    def test_render_insight_contains_stats(self):
        insight = PriceInsight(stats=SAMPLE_INSIGHT["stats"], samples=SAMPLE_INSIGHT["samples"],
                                assessment=SAMPLE_INSIGHT["assessment"],
                                category="Sofa", material="vai")
        text = build_market_price_insight_reply("sofa vai 2m gia 8 trieu", insight)
        self.assertIn("37", text)
        self.assertIn("Sofa", text)
        self.assertIn("5.200.000", text)
        self.assertIn("6.900.000", text)
        self.assertIn("9.200.000", text)
        self.assertIn("TRUNG BINH", text)
        self.assertIn("1 nguon", text)

    def test_render_insight_assessment_shown(self):
        insight = PriceInsight(stats=SAMPLE_INSIGHT["stats"], samples=SAMPLE_INSIGHT["samples"],
                                assessment=SAMPLE_INSIGHT["assessment"],
                                category="Sofa", material="vai")
        text = build_market_price_insight_reply("sofa vai 2m gia 8 trieu", insight)
        self.assertIn("8.000.000", text)
        self.assertIn("nam trong khoang pho bien", text)
        self.assertIn("Nhan xet", text)

    def test_render_insight_samples_shown(self):
        insight = PriceInsight(stats=SAMPLE_INSIGHT["stats"], samples=SAMPLE_INSIGHT["samples"],
                                assessment=SAMPLE_INSIGHT["assessment"],
                                category="Sofa", material="vai")
        text = build_market_price_insight_reply("sofa vai 2m gia 8 trieu", insight)
        self.assertIn("SFG041", text)
        self.assertIn("SFG042", text)
        self.assertIn("6.500.000", text)

    def test_render_no_insight_returns_no_data(self):
        text = build_market_price_insight_reply("test", None)
        self.assertIn("chua co du du lieu", text.lower())

    def test_render_empty_stats_returns_no_data(self):
        insight = PriceInsight(stats=EMPTY_INSIGHT["stats"], samples=[], assessment=None)
        text = build_market_price_insight_reply("test", insight)
        self.assertIn("chua co du du lieu", text.lower())

    def test_no_phone_asking(self):
        insight = PriceInsight(stats=SAMPLE_INSIGHT["stats"], samples=SAMPLE_INSIGHT["samples"],
                                assessment=SAMPLE_INSIGHT["assessment"],
                                category="Sofa", material="vai")
        text = build_market_price_insight_reply("test", insight)
        self.assertNotIn("so dien thoai", text.lower())
        self.assertNotIn("phone", text.lower())

    def test_no_lead_purchase_language(self):
        insight = PriceInsight(stats=SAMPLE_INSIGHT["stats"], samples=SAMPLE_INSIGHT["samples"],
                                assessment=SAMPLE_INSIGHT["assessment"],
                                category="Sofa", material="vai")
        text = build_market_price_insight_reply("test", insight)
        self.assertNotIn("dat hang", text.lower())
        self.assertNotIn("purchase request", text.lower())

    def test_fmt_price_formats_correctly(self):
        self.assertEqual("10.000.000 VND", _fmt_price(10000000))
        self.assertEqual("chua co du lieu", _fmt_price(None))

    def test_confidence_label_maps_correctly(self):
        self.assertEqual("CAO", _confidence_label("HIGH"))
        self.assertEqual("THAP (chua du mau)", _confidence_label("INSUFFICIENT"))


if __name__ == "__main__":
    unittest.main()
