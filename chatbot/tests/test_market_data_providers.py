import json
import tempfile
import unittest
from pathlib import Path

from app.market_data import (
    DatabaseMarketPriceProvider,
    ExternalPriceProvider,
    InternalCatalogProvider,
    MockMarketPriceProvider,
)


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class MarketDataProviderTests(unittest.TestCase):
    def test_internal_catalog_provider_loads_structured_candidates(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="catalog-provider-"))
        catalog_path = tmp_dir / "catalog.jsonl"
        _write_jsonl(catalog_path, [
            {
                "product_id": "SFG041",
                "name": "Sofa SFG041",
                "category": "sofa",
                "price": 12000000,
                "currency": "VND",
                "material": "go soi",
                "source": "internal://catalog/SFG041",
            }
        ])

        provider = InternalCatalogProvider(catalog_path=str(catalog_path))
        candidates = provider.search_candidates("sofa SFG041 go soi", limit=3)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].product_id, "SFG041")
        self.assertEqual(candidates[0].price, 12000000)
        self.assertEqual(candidates[0].currency, "VND")

    def test_mock_market_price_provider_returns_demo_refs(self):
        provider = MockMarketPriceProvider()
        refs = provider.get_price_references("Gia sofa SFG041 khoang bao nhieu?", limit=5)

        self.assertGreaterEqual(len(refs), 1)
        self.assertTrue(all(ref.is_mock for ref in refs))
        self.assertTrue(any(ref.product_id == "SFG041" for ref in refs))
        self.assertTrue(all((ref.source or "").startswith("mock://") for ref in refs))

    def test_mock_market_price_provider_keeps_product_type_filter(self):
        provider = MockMarketPriceProvider()
        refs = provider.get_price_references("So sánh giá sofa gỗ sồi với mặt bằng chung", limit=5)

        self.assertGreaterEqual(len(refs), 1)
        self.assertTrue(all((ref.category or "").lower() == "sofa" for ref in refs))
        self.assertTrue(all(ref.product_id == "SFG041" for ref in refs))
        self.assertFalse(any((ref.product_id or "").startswith("BAN-AN") for ref in refs))

    def test_database_market_price_provider_uses_structured_records(self):
        provider = DatabaseMarketPriceProvider(database_url="postgresql://unused")
        provider._load_records = lambda: [
            {
                "product_id": "SFG041",
                "name": "Sofa gỗ sồi SFG041",
                "category": "sofa",
                "material": "gỗ sồi",
                "price": 12000000,
                "currency": "VND",
                "source": "internal://price/SFG041",
            },
            {
                "product_id": "BAN-AN-GO-01",
                "name": "Bàn ăn gỗ sồi",
                "category": "bàn ăn",
                "material": "gỗ sồi",
                "price": 8500000,
                "currency": "VND",
                "source": "internal://price/BAN-AN-GO-01",
            },
        ]

        refs = provider.get_price_references("So sánh giá sofa gỗ sồi với mặt bằng chung", limit=5)

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].product_id, "SFG041")
        self.assertEqual(refs[0].provider, "database_market_price")
        self.assertFalse(refs[0].is_mock)

    def test_external_price_provider_interface_defaults_to_empty(self):
        provider = ExternalPriceProvider()
        self.assertEqual(provider.get_price_references("sofa SFG041"), [])


if __name__ == "__main__":
    unittest.main()
