"""Tests for BackendGeneralCatalogProvider — hardened version."""

import json
import unittest
from unittest.mock import patch, MagicMock

import requests

from app.general_catalog_provider import (
    BackendGeneralCatalogProvider,
    BackendCatalogItem,
    build_backend_catalog_provider,
    format_backend_catalog_items,
)


SAMPLE_RESPONSE = {
    "query": "sofa vai duoi 7 trieu",
    "mode": "GENERAL_COMPARE",
    "totalCandidates": 3,
    "items": [
        {
            "name": "Sofa vai cao cap SFG041",
            "sourceCode": "gotrangtri",
            "sourceName": "Go Trang Tri",
            "category": "Sofa",
            "material": "vai",
            "price": 6500000.0,
            "currency": "VND",
            "sourceUrl": "https://gotrangtri.vn/shop/sofa-sfg041",
            "imageUrl": "https://gotrangtri.vn/img.jpg",
            "dimensionsText": "200x80x90cm",
            "description": "Sofa vai cao cap",
            "score": 23.0,
            "scoreReasons": ["category_match", "material_match", "price_within_budget", "text_match"],
        },
    ],
}

EMPTY_RESPONSE = {"query": None, "mode": "GENERAL_COMPARE", "totalCandidates": 0, "items": []}


class BackendGeneralCatalogProviderTests(unittest.TestCase):

    def setUp(self):
        self.provider = BackendGeneralCatalogProvider(base_url="http://test-backend:8080")

    # --- A: URL encoding ---

    @patch("app.general_catalog_provider.requests.get")
    def test_search_vietnamese_query_encoded_correctly(self, mock_get):
        """Query tiếng Việt có dấu phải được encode UTF-8 đúng."""
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_RESPONSE
        mock_get.return_value = mock_resp

        items = self.provider.search_candidates("sofa vải dưới 7 triệu")
        self.assertEqual(len(items), 1)

        # Verify requests.get was called with proper params
        call_kwargs = mock_get.call_args[1]
        params = call_kwargs.get("params", {})
        self.assertIn("q", params)
        self.assertEqual(params["q"], "sofa vải dưới 7 triệu")

    @patch("app.general_catalog_provider.requests.get")
    def test_search_url_with_special_chars(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_RESPONSE
        mock_get.return_value = mock_resp

        items = self.provider.search_candidates("tủ quần áo gỗ công nghiệp dưới 5.000.000đ")
        self.assertEqual(len(items), 1)

    # --- B: Internal API secret ---

    @patch("app.general_catalog_provider.requests.get")
    def test_internal_secret_header_sent_when_configured(self, mock_get):
        provider = BackendGeneralCatalogProvider(base_url="http://test:8080")
        provider._internal_secret = "my-secret-key"

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_RESPONSE
        mock_get.return_value = mock_resp

        provider.search_candidates("test")
        headers = mock_get.call_args[1].get("headers", {})
        self.assertEqual(headers.get("X-Internal-Api-Key"), "my-secret-key")

    @patch("app.general_catalog_provider.requests.get")
    def test_no_internal_secret_header_when_not_configured(self, mock_get):
        self.provider._internal_secret = ""
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = EMPTY_RESPONSE
        mock_get.return_value = mock_resp

        self.provider.search_candidates("test")
        headers = mock_get.call_args[1].get("headers", {})
        self.assertNotIn("X-Internal-Api-Key", headers)

    # --- C: Role safety ---

    def test_provider_always_uses_user_role(self):
        """Provider không có param role — luôn gửi role=USER."""
        # This is enforced by the provider always using role=USER internally
        pass  # verified via the mock call assertions below

    @patch("app.general_catalog_provider.requests.get")
    def test_search_sends_role_user(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = EMPTY_RESPONSE
        mock_get.return_value = mock_resp

        self.provider.search_candidates("test")
        params = mock_get.call_args[1].get("params", {})
        self.assertEqual(params.get("role"), "USER")

    # --- D: Fallback behavior ---

    @patch("app.general_catalog_provider.requests.get")
    def test_401_returns_empty_fallback(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        items = self.provider.search_candidates("test")
        self.assertEqual(len(items), 0)

    @patch("app.general_catalog_provider.requests.get")
    def test_403_returns_empty_fallback(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp

        items = self.provider.search_candidates("test")
        self.assertEqual(len(items), 0)

    @patch("app.general_catalog_provider.requests.get")
    def test_500_returns_empty_fallback(self, mock_get):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_get.return_value = mock_resp

        items = self.provider.search_candidates("test")
        self.assertEqual(len(items), 0)

    @patch("app.general_catalog_provider.requests.get")
    def test_timeout_returns_empty_fallback(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("timeout")

        items = self.provider.search_candidates("test")
        self.assertEqual(len(items), 0)

    @patch("app.general_catalog_provider.requests.get")
    def test_connection_error_returns_empty_fallback(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("connection refused")

        items = self.provider.search_candidates("test")
        self.assertEqual(len(items), 0)

    # --- Basic functionality ---

    def test_search_empty_query_returns_empty(self):
        items = self.provider.search_candidates("")
        self.assertEqual(len(items), 0)

    def test_format_items_returns_text(self):
        items = [
            BackendCatalogItem(
                name="Sofa vai SFG041",
                source_code="gotrangtri",
                source_name="Go Trang Tri",
                category="Sofa",
                material="vai",
                price=6500000.0,
                currency="VND",
                source_url="https://gotrangtri.vn/sofa",
                score=23.0,
                score_reasons=["category_match", "price_within_budget"],
            )
        ]
        text = format_backend_catalog_items(items)
        self.assertIn("Sofa vai SFG041", text)
        self.assertIn("6.500.000", text)
        self.assertIn("category_match", text)

    def test_format_empty_items_returns_fallback(self):
        text = format_backend_catalog_items([])
        self.assertIn("no products found", text)

    def test_from_api_item_maps_fields(self):
        raw = {
            "name": "Test Product",
            "sourceCode": "gotrangtri",
            "sourceName": "Go Trang Tri",
            "category": "Sofa",
            "price": 5000000.0,
            "score": 10.0,
            "scoreReasons": ["category_match"],
        }
        item = BackendCatalogItem.from_api_item(raw)
        self.assertEqual(item.name, "Test Product")
        self.assertEqual(item.price, 5000000.0)

    def test_to_dict_roundtrip(self):
        item = BackendCatalogItem(
            name="Test", source_code="src", source_name="Source",
            category="Cat", price=100000.0,
        )
        d = item.to_dict()
        self.assertEqual(d["name"], "Test")
        self.assertEqual(d["price"], 100000.0)

    def test_build_provider_defaults(self):
        provider = build_backend_catalog_provider()
        self.assertIsNotNone(provider)


if __name__ == "__main__":
    unittest.main()
