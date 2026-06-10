import json
import tempfile
import unittest
from pathlib import Path

from data_pipeline.crawling.dedupe_output import (
    audit_product_jsonl,
    dedupe_product_jsonl,
    get_product_record_key,
)


def _record(url=None, canonical_url=None, quality="medium", observed_at="2026-01-01T00:00:00+00:00", **extra):
    record = {
        "source_url": url,
        "canonical_url": canonical_url,
        "product_name": extra.pop("product_name", "Product"),
        "sku": extra.pop("sku", "SKU-1"),
        "price": extra.pop("price", 100000),
        "image_urls": extra.pop("image_urls", []),
        "observed_at": observed_at,
        "metadata": {"data_quality": quality},
    }
    record.update(extra)
    return record


def _write_jsonl(path: Path, records):
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class DedupeOutputTests(unittest.TestCase):
    def test_trailing_slash_and_no_trailing_slash_share_key(self):
        self.assertEqual(
            get_product_record_key(_record(url="https://example.test/shop/a/")),
            get_product_record_key(_record(url="https://example.test/shop/a")),
        )

    def test_dedupe_keeps_more_complete_record(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.jsonl"
            output_path = Path(tmp_dir) / "output.jsonl"
            _write_jsonl(
                input_path,
                [
                    _record(url="https://example.test/a", quality="high"),
                    _record(
                        url="https://example.test/a/",
                        quality="high",
                        description="full description",
                        brand="Brand",
                        image_urls=["one.jpg", "two.jpg"],
                    ),
                ],
            )

            report = dedupe_product_jsonl(input_path, output_path)
            records = _read_jsonl(output_path)

            self.assertEqual(report["removed_duplicates"], 1)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["brand"], "Brand")

    def test_dedupe_prefers_high_quality_over_more_complete_low_quality(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.jsonl"
            output_path = Path(tmp_dir) / "output.jsonl"
            _write_jsonl(
                input_path,
                [
                    _record(url="https://example.test/a", quality="low", description="full", brand="Brand"),
                    _record(url="https://example.test/a", quality="high"),
                ],
            )

            dedupe_product_jsonl(input_path, output_path)
            records = _read_jsonl(output_path)

            self.assertEqual(records[0]["metadata"]["data_quality"], "high")
            self.assertNotIn("brand", records[0])

    def test_dedupe_prefers_newer_observed_at_when_other_scores_tie(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.jsonl"
            output_path = Path(tmp_dir) / "output.jsonl"
            _write_jsonl(
                input_path,
                [
                    _record(url="https://example.test/a", observed_at="2026-01-01T00:00:00+00:00", price=1),
                    _record(url="https://example.test/a", observed_at="2026-01-02T00:00:00+00:00", price=2),
                ],
            )

            dedupe_product_jsonl(input_path, output_path)
            records = _read_jsonl(output_path)

            self.assertEqual(records[0]["price"], 2)

    def test_missing_url_records_do_not_crash_and_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.jsonl"
            output_path = Path(tmp_dir) / "output.jsonl"
            _write_jsonl(input_path, [_record(url=None, canonical_url=None, sku="A"), _record(url=None, canonical_url=None, sku="B")])

            report = dedupe_product_jsonl(input_path, output_path)
            records = _read_jsonl(output_path)

            self.assertEqual(report["input_lines"], 2)
            self.assertEqual(report["output_lines"], 2)
            self.assertEqual([record["sku"] for record in records], ["A", "B"])

    def test_audit_reports_duplicates_and_output_is_jsonl_readable(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.jsonl"
            output_path = Path(tmp_dir) / "output.jsonl"
            _write_jsonl(input_path, [_record(url="https://example.test/a"), _record(url="https://example.test/a/")])

            audit = audit_product_jsonl(input_path)
            dedupe_product_jsonl(input_path, output_path)
            records = _read_jsonl(output_path)

            self.assertEqual(audit["duplicate_by_normalized_url_count"], 1)
            self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
