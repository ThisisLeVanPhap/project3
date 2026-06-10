import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from data_pipeline.crawling.batch_crawl import (
    audit_crawl_progress,
    discover_and_write_manifest,
    load_crawl_state,
    read_url_manifest,
    repair_state_from_output,
    run_product_batch,
    run_until_done,
    save_crawl_state,
    select_next_batch,
    write_url_manifest,
)
from data_pipeline.crawling.source_config import CrawlSource


class FakeAdapter:
    name = "fake"

    def __init__(self, discovered_urls=None):
        self.discovered_urls = list(discovered_urls or [])

    def discover_product_urls(self, max_urls=100):
        return self.discovered_urls[:max_urls]

    def build_source(self, start_urls, tenant_id=None, output_path=None):
        return CrawlSource(
            name=self.name,
            start_urls=list(start_urls),
            tenant_id=tenant_id,
            allowed_domains=["example.test"],
            output_path=output_path or "products.jsonl",
        )


class FakeJob:
    def __init__(self, source):
        self.source = source

    def run(self):
        errors = []
        observations = []
        fetched_count = 0
        extracted_count = 0
        skipped_count = 0
        failed_count = 0

        for url in self.source.start_urls:
            if "block429" in url:
                failed_count += 1
                errors.append({"url": url, "error": "HTTP 429 too many requests"})
                continue
            if "block403" in url:
                failed_count += 1
                errors.append({"url": url, "error": "HTTP 403 forbidden"})
                continue
            if "skip" in url:
                skipped_count += 1
                errors.append({"url": url, "error": "outside_allowed_domains"})
                continue
            if "fail" in url:
                failed_count += 1
                errors.append({"url": url, "error": "boom"})
                continue
            fetched_count += 1
            extracted_count += 1
            observations.append({"url": url, "tenant_id": self.source.tenant_id})

        output_path = Path(self.source.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            for item in observations:
                handle.write(json.dumps(item) + "\n")

        return SimpleNamespace(
            fetched_count=fetched_count,
            extracted_count=extracted_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            errors=errors,
        )


class BatchCrawlTests(unittest.TestCase):
    def test_discover_merge_dedupes_existing_manifest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "urls.txt"
            write_url_manifest(["a", "b"], path)

            summary = discover_and_write_manifest(
                FakeAdapter(["b", "c", "d"]),
                path,
                max_urls=10,
            )

            self.assertEqual(read_url_manifest(path), ["a", "b", "c", "d"])
            self.assertEqual(
                summary,
                {"old_count": 2, "discovered_count": 3, "new_count": 2, "total_count": 4},
            )

    def test_discover_overwrite_replaces_manifest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "urls.txt"
            write_url_manifest(["a", "b"], path)

            summary = discover_and_write_manifest(
                FakeAdapter(["b", "c"]),
                path,
                max_urls=10,
                overwrite=True,
            )

            self.assertEqual(read_url_manifest(path), ["b", "c"])
            self.assertEqual(summary["old_count"], 0)
            self.assertEqual(summary["total_count"], 2)

    def test_write_and_read_manifest_dedupes_urls(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "urls.txt"
            write_url_manifest(["https://example.test/a", "https://example.test/a", "https://example.test/b"], path)

            self.assertEqual(
                read_url_manifest(path),
                ["https://example.test/a", "https://example.test/b"],
            )

    def test_select_next_batch_skips_success_and_failed_by_default(self):
        urls = ["a", "b", "c", "d"]
        state = {"success": ["a"], "failed": ["b"]}

        self.assertEqual(select_next_batch(urls, state, batch_size=2), ["c", "d"])

    def test_select_next_batch_can_retry_failed(self):
        urls = ["a", "b", "c"]
        state = {"success": ["a"], "failed": ["b"]}

        self.assertEqual(select_next_batch(urls, state, batch_size=2, retry_failed=True), ["b", "c"])

    def test_state_save_and_load_normalizes_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "state.json"
            save_crawl_state({"success": ["a", "a"]}, path)
            loaded = load_crawl_state(path)

            self.assertEqual(loaded["success"], ["a"])
            self.assertEqual(loaded["failed"], [])
            self.assertEqual(loaded["skipped"], [])
            self.assertEqual(loaded["runs"], [])

    def test_run_product_batch_updates_success_failed_and_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(
                [
                    "https://example.test/a",
                    "https://example.test/fail",
                    "https://example.test/skip",
                ],
                manifest,
            )

            result = run_product_batch(
                adapter=FakeAdapter(),
                manifest_path=manifest,
                state_path=state,
                output_path=output,
                tenant_id="tenant-a",
                batch_size=3,
                job_factory=FakeJob,
            )

            loaded = load_crawl_state(state)
            self.assertEqual(loaded["success"], ["https://example.test/a"])
            self.assertEqual(loaded["failed"], ["https://example.test/fail"])
            self.assertEqual(loaded["skipped"], ["https://example.test/skip"])
            self.assertEqual(result["run"]["fetched_count"], 1)
            self.assertEqual(result["run"]["extracted_count"], 1)
            self.assertEqual(result["run"]["failed_count"], 1)
            self.assertEqual(result["run"]["skipped_count"], 1)
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 1)

    def test_run_product_batch_does_not_duplicate_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(["https://example.test/a", "https://example.test/b"], manifest)
            save_crawl_state({"success": ["https://example.test/a"]}, state)

            run_product_batch(
                adapter=FakeAdapter(),
                manifest_path=manifest,
                state_path=state,
                output_path=output,
                tenant_id="tenant-a",
                batch_size=2,
                job_factory=FakeJob,
            )

            loaded = load_crawl_state(state)
            self.assertEqual(loaded["success"], ["https://example.test/a", "https://example.test/b"])

    def test_run_product_batch_uses_existing_output_as_success_cache(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(["https://example.test/a", "https://example.test/b"], manifest)
            output.write_text(
                json.dumps({"source_url": "https://example.test/a"}) + "\n",
                encoding="utf-8",
            )

            result = run_product_batch(
                adapter=FakeAdapter(),
                manifest_path=manifest,
                state_path=state,
                output_path=output,
                tenant_id="tenant-a",
                batch_size=2,
                job_factory=FakeJob,
            )

            loaded = load_crawl_state(state)
            self.assertEqual(result["batch_urls"], ["https://example.test/b"])
            self.assertEqual(loaded["success"], ["https://example.test/a", "https://example.test/b"])

    def test_run_until_done_runs_multiple_batches_until_manifest_exhausted(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(
                ["https://example.test/a", "https://example.test/b", "https://example.test/c"],
                manifest,
            )

            summary = run_until_done(
                adapter=FakeAdapter(),
                manifest_path=manifest,
                state_path=state,
                output_path=output,
                tenant_id="tenant-a",
                batch_size=2,
                sleep_between_batches=0,
                job_factory=FakeJob,
            )

            loaded = load_crawl_state(state)
            self.assertEqual(summary["total_batches"], 2)
            self.assertEqual(summary["total_fetched"], 3)
            self.assertEqual(summary["total_extracted"], 3)
            self.assertEqual(summary["remaining_count"], 0)
            self.assertEqual(len(loaded["success"]), 3)
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 3)

    def test_run_until_done_respects_max_batches(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(
                ["https://example.test/a", "https://example.test/b", "https://example.test/c"],
                manifest,
            )

            summary = run_until_done(
                adapter=FakeAdapter(),
                manifest_path=manifest,
                state_path=state,
                output_path=output,
                tenant_id="tenant-a",
                batch_size=1,
                max_batches=2,
                sleep_between_batches=0,
                job_factory=FakeJob,
            )

            self.assertEqual(summary["total_batches"], 2)
            self.assertEqual(summary["remaining_count"], 1)

    def test_run_until_done_stops_when_selected_count_zero(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(["https://example.test/a"], manifest)
            save_crawl_state({"success": ["https://example.test/a"]}, state)

            summary = run_until_done(
                adapter=FakeAdapter(),
                manifest_path=manifest,
                state_path=state,
                output_path=output,
                tenant_id="tenant-a",
                batch_size=1,
                sleep_between_batches=0,
                job_factory=FakeJob,
            )

            self.assertEqual(summary["total_batches"], 0)
            self.assertEqual(summary["remaining_count"], 0)

    def test_run_until_done_stops_on_block_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(
                ["https://example.test/a", "https://example.test/block429", "https://example.test/c"],
                manifest,
            )

            summary = run_until_done(
                adapter=FakeAdapter(),
                manifest_path=manifest,
                state_path=state,
                output_path=output,
                tenant_id="tenant-a",
                batch_size=2,
                sleep_between_batches=0,
                stop_on_block=True,
                job_factory=FakeJob,
            )

            self.assertEqual(summary["total_batches"], 1)
            self.assertTrue(summary["stopped_on_block"])
            self.assertEqual(summary["remaining_count"], 1)

    def test_audit_detects_state_success_missing_from_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(["a", "b", "c"], manifest)
            save_crawl_state({"success": ["a", "b"], "failed": ["c"]}, state)
            output.write_text(json.dumps({"source_url": "a"}) + "\n", encoding="utf-8")

            audit = audit_crawl_progress(manifest, state, output)

            self.assertEqual(audit["state_success_count"], 2)
            self.assertEqual(audit["output_unique_url_count"], 1)
            self.assertEqual(audit["success_missing_from_output_count"], 1)
            self.assertEqual(audit["sample_success_missing_from_output"], ["b"])
            self.assertEqual(audit["remaining_count"], 0)

    def test_audit_treats_trailing_slash_urls_as_same_product(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(["https://example.test/a/"], manifest)
            save_crawl_state({"success": ["https://example.test/a/"]}, state)
            output.write_text(
                json.dumps({"source_url": "https://example.test/a"}) + "\n",
                encoding="utf-8",
            )

            audit = audit_crawl_progress(manifest, state, output)

            self.assertEqual(audit["success_missing_from_output_count"], 0)
            self.assertEqual(audit["output_missing_from_success_count"], 0)
            self.assertEqual(audit["remaining_count"], 0)

    def test_select_next_batch_uses_url_key_for_output_seeded_success(self):
        urls = ["https://example.test/a/", "https://example.test/b/"]
        state = {"success": ["https://example.test/a"]}

        self.assertEqual(select_next_batch(urls, state, batch_size=2), ["https://example.test/b/"])

    def test_audit_detects_output_missing_from_success_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(["a", "b", "c"], manifest)
            save_crawl_state({"success": ["a"]}, state)
            output.write_text(
                json.dumps({"source_url": "a"}) + "\n"
                + json.dumps({"canonical_url": "b"}) + "\n"
                + json.dumps({"url": "b"}) + "\n",
                encoding="utf-8",
            )

            audit = audit_crawl_progress(manifest, state, output)

            self.assertEqual(audit["output_line_count"], 3)
            self.assertEqual(audit["output_unique_url_count"], 2)
            self.assertEqual(audit["output_missing_from_success_count"], 1)
            self.assertEqual(audit["sample_output_missing_from_success"], ["b"])
            self.assertEqual(audit["duplicate_output_url_count"], 1)
            self.assertEqual(audit["sample_duplicate_output_urls"], ["b"])

    def test_repair_state_from_output_updates_success_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "urls.txt"
            state = root / "state.json"
            output = root / "products.jsonl"
            write_url_manifest(["a", "b", "c"], manifest)
            save_crawl_state({"success": ["a", "missing"], "failed": ["b", "c"], "runs": [{"batch_size": 1}]}, state)
            output.write_text(
                json.dumps({"source_url": "a"}) + "\n"
                + json.dumps({"source_url": "b"}) + "\n",
                encoding="utf-8",
            )

            repair = repair_state_from_output(manifest, state, output)
            loaded = load_crawl_state(state)

            self.assertTrue(Path(repair["backup_path"]).exists())
            self.assertEqual(loaded["success"], ["a", "b"])
            self.assertEqual(loaded["failed"], ["c"])
            self.assertEqual(loaded["runs"], [{"batch_size": 1}])
            self.assertEqual(repair["after"]["success_missing_from_output_count"], 0)
            self.assertEqual(repair["after"]["output_missing_from_success_count"], 0)
            self.assertEqual(repair["after"]["remaining_count"], 0)


if __name__ == "__main__":
    unittest.main()
