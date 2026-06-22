import json
import tempfile
import unittest
from pathlib import Path

from data_pipeline.crawling.taxonomy_normalize import decide_category, normalize_dataset_taxonomy


class TaxonomyNormalizeTests(unittest.TestCase):
    def test_taxonomy_rules(self):
        cases = [
            ("Tủ quần áo gỗ", "https://gotrangtri.vn/shop/tu-quan-ao-go", "Tủ"),
            ("Kệ tivi phòng khách", "https://gotrangtri.vn/shop/ke-tivi-phong-khach", "Kệ"),
            ("Ghế sofa phòng khách", "https://gotrangtri.vn/shop/ghe-sofa-phong-khach", "Sofa"),
            ("Giường ngủ gỗ", "https://gotrangtri.vn/shop/giuong-ngu-go", "Giường"),
            ("Rèm cửa đẹp", "https://gotrangtri.vn/shop/rem-cua-dep", "Rèm"),
            ("Bàn làm việc chân sắt", "https://gotrangtri.vn/shop/ban-lam-viec-chan-sat", "Bàn làm việc"),
            ("Bàn trà gỗ", "https://gotrangtri.vn/shop/ban-tra-go", "Bàn trà"),
            ("Ghế thư giãn", "https://gotrangtri.vn/shop/ghe-thu-gian", "Ghế"),
            ("Đèn bàn trang trí", "https://gotrangtri.vn/shop/den-ban-trang-tri", "Đèn"),
            ("Gương treo tường", "https://gotrangtri.vn/shop/guong-treo-tuong", "Gương"),
        ]
        for title, url, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(decide_category({"product_name": title, "source_url": url}).category, expected)

    def test_desktop_clock_does_not_map_to_work_desk(self):
        self.assertEqual(
            decide_category({"product_name": "Đồng hồ để bàn trang trí", "source_url": "https://gotrangtri.vn/shop/dong-ho-de-ban"}).category,
            "Đồ trang trí",
        )

    def test_table_lamp_does_not_map_to_work_desk(self):
        self.assertEqual(
            decide_category({"product_name": "Đèn bàn học", "source_url": "https://gotrangtri.vn/shop/den-ban-hoc"}).category,
            "Đèn",
        )

    def test_dry_run_does_not_change_files_and_apply_preserves_line_count(self):
        dataset = self.make_dataset(source="gotrangtri")
        catalog = dataset / "catalog.jsonl"
        before = catalog.read_text(encoding="utf-8")

        dry = normalize_dataset_taxonomy(dataset, dataset / "changes.jsonl", apply=False)

        self.assertEqual(dry["taxonomy_profile_used"], "gotrangtri")
        self.assertEqual(dry["normalization_mode"], "dry-run")
        self.assertEqual(dry["change_count"], 1)
        self.assertEqual(catalog.read_text(encoding="utf-8"), before)

        applied = normalize_dataset_taxonomy(dataset, dataset / "changes.jsonl", apply=True)

        self.assertEqual(applied["taxonomy_profile_used"], "gotrangtri")
        self.assertEqual(applied["normalization_mode"], "apply")
        self.assertEqual(applied["applied_count"], 1)
        rows = [json.loads(line) for line in catalog.read_text(encoding="utf-8").splitlines() if line.strip()]
        rag_rows = [json.loads(line) for line in (dataset / "rag_products.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        report = json.loads((dataset / "quality_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rag_rows), 2)
        self.assertEqual(rows[0]["category"], "Tủ")
        self.assertIn("Danh mục: Tủ", rag_rows[0]["text"])
        self.assertEqual(report["taxonomy_profile_used"], "gotrangtri")
        self.assertEqual(report["normalization_mode"], "apply")
        self.assertEqual(report["applied_changes_count"], 1)

    def test_unknown_source_uses_report_only_and_does_not_apply_gotrangtri_rules(self):
        dataset = self.make_dataset(source="another-shop")
        catalog = dataset / "catalog.jsonl"
        before = catalog.read_text(encoding="utf-8")

        result = normalize_dataset_taxonomy(dataset, dataset / "changes.jsonl", apply=True)

        rows = [json.loads(line) for line in catalog.read_text(encoding="utf-8").splitlines() if line.strip()]
        report = json.loads((dataset / "quality_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(result["taxonomy_profile_used"], "global")
        self.assertEqual(result["normalization_mode"], "report-only")
        self.assertEqual(result["applied_count"], 0)
        self.assertIn("No source-specific taxonomy profile; report-only mode.", result["warnings"])
        self.assertEqual(catalog.read_text(encoding="utf-8"), before)
        self.assertEqual(rows[0]["category"], "Kệ")
        self.assertEqual(report["taxonomy_profile_used"], "global")
        self.assertEqual(report["normalization_mode"], "report-only")

    def test_explicit_gotrangtri_source_overrides_manifest(self):
        dataset = self.make_dataset(source="another-shop")

        result = normalize_dataset_taxonomy(dataset, dataset / "changes.jsonl", apply=True, source="gotrangtri")

        rows = [json.loads(line) for line in (dataset / "catalog.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(result["taxonomy_profile_used"], "gotrangtri")
        self.assertEqual(result["applied_count"], 1)
        self.assertEqual(rows[0]["category"], "Tủ")

    def make_dataset(self, source: str = "gotrangtri") -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dataset = Path(tmp.name)
        rows = [
            {
                "tenant_id": "demo",
                "product_name": "Tủ quần áo gỗ",
                "category": "Kệ",
                "price": 1,
                "source_url": "https://gotrangtri.vn/shop/tu-quan-ao-go",
            },
            {
                "tenant_id": "demo",
                "product_name": "Sofa gỗ",
                "category": "Sofa",
                "price": 2,
                "source_url": "https://gotrangtri.vn/shop/sofa-go",
            },
        ]
        with (dataset / "catalog.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        with (dataset / "rag_products.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps({"title": row["product_name"], "text": row["product_name"], "url": row["source_url"], "metadata": row}, ensure_ascii=False) + "\n")
        manifest = {
            "dataset_id": "test-dataset",
            "source": source,
            "product_count": len(rows),
            "rag_chunk_count": len(rows),
            "files": {"catalog": "catalog.jsonl", "rag_products": "rag_products.jsonl"},
        }
        (dataset / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return dataset


if __name__ == "__main__":
    unittest.main()
