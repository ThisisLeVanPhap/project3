import argparse
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlsplit, urlunsplit

from data_pipeline.crawling.adapters.gotrangtri import GoTrangTriAdapter
from data_pipeline.crawling.job import ProductCrawlJob


DEFAULT_STATE = {
    "success": [],
    "failed": [],
    "skipped": [],
    "last_run_at": None,
    "runs": [],
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def discover_all_product_urls(adapter: Any, max_urls: Optional[int] = None) -> list[str]:
    limit = max_urls if max_urls is not None else 1_000_000
    return _dedupe_preserve_order(adapter.discover_product_urls(max_urls=limit))


def write_url_manifest(urls: list[str], path: str | Path) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(_dedupe_preserve_order(urls)) + "\n",
        encoding="utf-8",
    )


def discover_and_write_manifest(
    adapter: Any,
    manifest_path: str | Path,
    max_urls: Optional[int] = None,
    merge_existing: bool = True,
    overwrite: bool = False,
) -> dict[str, int]:
    old_urls = [] if overwrite or not merge_existing else read_url_manifest(manifest_path)
    discovered_urls = discover_all_product_urls(adapter, max_urls=max_urls)
    merged_urls = discovered_urls if overwrite else _dedupe_preserve_order(old_urls + discovered_urls)
    write_url_manifest(merged_urls, manifest_path)

    old_set = set(old_urls)
    return {
        "old_count": len(old_urls),
        "discovered_count": len(discovered_urls),
        "new_count": len([url for url in discovered_urls if url not in old_set]),
        "total_count": len(merged_urls),
    }


def read_url_manifest(path: str | Path) -> list[str]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return []
    urls = [line.strip() for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    return _dedupe_preserve_order([url for url in urls if url and not url.startswith("#")])


def load_crawl_state(path: str | Path) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return _normalize_state({})
    with state_path.open("r", encoding="utf-8") as handle:
        return _normalize_state(json.load(handle))


def save_crawl_state(state: dict[str, Any], path: str | Path) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_normalize_state(state), handle, ensure_ascii=False, indent=2)


def select_next_batch(
    urls: list[str],
    state: dict[str, Any],
    batch_size: int,
    retry_failed: bool = False,
) -> list[str]:
    if batch_size <= 0:
        return []

    normalized_state = _normalize_state(state)
    success = {_url_key(url) for url in normalized_state["success"]}
    failed = {_url_key(url) for url in normalized_state["failed"]}
    selected: list[str] = []

    for url in _dedupe_preserve_order(urls):
        url_key = _url_key(url)
        if url_key in success:
            continue
        if url_key in failed and not retry_failed:
            continue
        selected.append(url)
        if len(selected) >= batch_size:
            break

    return selected


def run_product_batch(
    adapter: Any,
    manifest_path: str | Path,
    state_path: str | Path,
    output_path: str | Path,
    tenant_id: Optional[str] = None,
    batch_size: int = 100,
    retry_failed: bool = False,
    job_factory: Optional[Callable[[Any], Any]] = None,
) -> dict[str, Any]:
    urls = read_url_manifest(manifest_path)
    state = load_crawl_state(state_path)
    _extend_unique(state["success"], _read_output_urls(output_path))
    state["failed"] = _merge_without_success(state["failed"], [], state["success"])
    batch_urls = select_next_batch(urls, state, batch_size=batch_size, retry_failed=retry_failed)
    started_at = utc_now_iso()

    if not batch_urls:
        run_summary = {
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "batch_size": batch_size,
            "selected_count": 0,
            "fetched_count": 0,
            "extracted_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "output_appended_count": 0,
        }
        state["last_run_at"] = run_summary["finished_at"]
        state["runs"].append(run_summary)
        save_crawl_state(state, state_path)
        return {"batch_urls": [], "result": None, "state": state, "run": run_summary}

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    job_factory = job_factory or ProductCrawlJob

    with tempfile.TemporaryDirectory(prefix="product-batch-") as tmp_dir:
        batch_output = Path(tmp_dir) / "products.jsonl"
        source = adapter.build_source(
            batch_urls,
            tenant_id=tenant_id,
            output_path=str(batch_output),
        )
        source.max_pages = len(batch_urls)
        result = job_factory(source).run()
        appended_count = _append_file(batch_output, output_file)

    failed_urls = _error_urls(result, "failed")
    skipped_urls = _error_urls(result, "skipped")
    success_urls = [
        url for url in batch_urls
        if url not in failed_urls and url not in skipped_urls
    ]

    _extend_unique(state["success"], success_urls)
    state["failed"] = _merge_without_success(state["failed"], failed_urls, state["success"])
    _extend_unique(state["skipped"], skipped_urls)

    finished_at = utc_now_iso()
    run_summary = {
        "started_at": started_at,
        "finished_at": finished_at,
        "batch_size": batch_size,
        "selected_count": len(batch_urls),
        "fetched_count": int(getattr(result, "fetched_count", 0)),
        "extracted_count": int(getattr(result, "extracted_count", 0)),
        "failed_count": int(getattr(result, "failed_count", 0)),
        "skipped_count": int(getattr(result, "skipped_count", 0)),
        "output_appended_count": appended_count,
        "block_detected": _has_block_error(result),
    }
    state["last_run_at"] = finished_at
    state["runs"].append(run_summary)
    save_crawl_state(state, state_path)

    return {"batch_urls": batch_urls, "result": result, "state": state, "run": run_summary}


def run_until_done(
    adapter: Any,
    manifest_path: str | Path,
    state_path: str | Path,
    output_path: str | Path,
    tenant_id: Optional[str] = None,
    batch_size: int = 100,
    retry_failed: bool = False,
    sleep_between_batches: float = 5.0,
    max_batches: Optional[int] = None,
    stop_on_block: bool = True,
    job_factory: Optional[Callable[[Any], Any]] = None,
) -> dict[str, Any]:
    total_batches = 0
    total_fetched = 0
    total_extracted = 0
    total_failed = 0
    total_skipped = 0
    stopped_on_block = False
    last_run: Optional[dict[str, Any]] = None

    while True:
        if max_batches is not None and total_batches >= max_batches:
            break

        result = run_product_batch(
            adapter=adapter,
            manifest_path=manifest_path,
            state_path=state_path,
            output_path=output_path,
            tenant_id=tenant_id,
            batch_size=batch_size,
            retry_failed=retry_failed,
            job_factory=job_factory,
        )
        run = result["run"]
        last_run = run

        if run["selected_count"] <= 0:
            break

        total_batches += 1
        total_fetched += run["fetched_count"]
        total_extracted += run["extracted_count"]
        total_failed += run["failed_count"]
        total_skipped += run["skipped_count"]

        if stop_on_block and run.get("block_detected"):
            stopped_on_block = True
            break

        if max_batches is not None and total_batches >= max_batches:
            break

        if sleep_between_batches > 0:
            time.sleep(sleep_between_batches)

    remaining_count = count_remaining(
        manifest_path=manifest_path,
        state_path=state_path,
        output_path=output_path,
        retry_failed=retry_failed,
    )
    return {
        "total_batches": total_batches,
        "total_fetched": total_fetched,
        "total_extracted": total_extracted,
        "total_failed": total_failed,
        "total_skipped": total_skipped,
        "remaining_count": remaining_count,
        "stopped_on_block": stopped_on_block,
        "last_run": last_run,
    }


def count_remaining(
    manifest_path: str | Path,
    state_path: str | Path,
    output_path: str | Path,
    retry_failed: bool = False,
) -> int:
    urls = read_url_manifest(manifest_path)
    state = load_crawl_state(state_path)
    _extend_unique(state["success"], _read_output_urls(output_path))
    state["failed"] = _merge_without_success(state["failed"], [], state["success"])
    return len(select_next_batch(urls, state, batch_size=len(urls), retry_failed=retry_failed))


def audit_crawl_progress(
    manifest_path: str | Path,
    state_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    manifest_urls = read_url_manifest(manifest_path)
    state = load_crawl_state(state_path)
    output_stats = _read_output_url_stats(output_path)
    output_urls = output_stats["unique_urls"]

    success_keys = {_url_key(url) for url in state["success"]}
    failed_keys = {_url_key(url) for url in state["failed"]}
    skipped_keys = {_url_key(url) for url in state["skipped"]}
    output_keys = {_url_key(url) for url in output_urls}

    success_missing = [url for url in state["success"] if _url_key(url) not in output_keys]
    output_missing = [url for url in output_urls if _url_key(url) not in success_keys]
    remaining = [
        url for url in manifest_urls
        if _url_key(url) not in success_keys
        and _url_key(url) not in failed_keys
        and _url_key(url) not in skipped_keys
    ]

    return {
        "manifest_count": len(manifest_urls),
        "output_line_count": output_stats["line_count"],
        "output_unique_url_count": len(output_urls),
        "state_success_count": len(state["success"]),
        "state_failed_count": len(state["failed"]),
        "state_skipped_count": len(state["skipped"]),
        "success_missing_from_output_count": len(success_missing),
        "output_missing_from_success_count": len(output_missing),
        "duplicate_output_url_count": len(output_stats["duplicate_urls"]),
        "remaining_count": len(remaining),
        "sample_success_missing_from_output": success_missing[:10],
        "sample_output_missing_from_success": output_missing[:10],
        "sample_duplicate_output_urls": output_stats["duplicate_urls"][:10],
    }


def repair_state_from_output(
    manifest_path: str | Path,
    state_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    before = audit_crawl_progress(manifest_path, state_path, output_path)
    state = load_crawl_state(state_path)
    output_urls = _read_output_url_stats(output_path)["unique_urls"]

    backup_path = _backup_state_file(state_path)
    state["success"] = output_urls
    state["failed"] = _merge_without_success(state["failed"], [], state["success"])
    success_keys = {_url_key(url) for url in state["success"]}
    state["skipped"] = [url for url in state["skipped"] if _url_key(url) not in success_keys]
    save_crawl_state(state, state_path)
    after = audit_crawl_progress(manifest_path, state_path, output_path)

    return {
        "backup_path": str(backup_path) if backup_path else None,
        "before": before,
        "after": after,
    }


def _adapter_for_site(site: str) -> Any:
    if site == "gotrangtri":
        return GoTrangTriAdapter()
    raise ValueError(f"Unsupported site: {site}")


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _dedupe_preserve_url_key(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = _url_key(text)
        if not text or key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def _url_key(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return text.rstrip("/")
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.query,
            "",
        )
    )


def _normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "success": [],
        "failed": [],
        "skipped": [],
        "last_run_at": None,
        "runs": [],
    }
    normalized.update(state or {})
    for key in ("success", "failed", "skipped"):
        value = normalized.get(key)
        normalized[key] = _dedupe_preserve_order(value if isinstance(value, list) else [])
    runs = normalized.get("runs")
    normalized["runs"] = runs if isinstance(runs, list) else []
    return normalized


def _append_file(source_path: Path, output_path: Path) -> int:
    if not source_path.exists():
        return 0
    lines = source_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return 0
    with output_path.open("a", encoding="utf-8") as handle:
        for line in lines:
            if line.strip():
                handle.write(line.rstrip("\n") + "\n")
    return len([line for line in lines if line.strip()])


def _read_output_urls(output_path: str | Path) -> list[str]:
    return _read_output_url_stats(output_path)["unique_urls"]


def _read_output_url_stats(output_path: str | Path) -> dict[str, Any]:
    path = Path(output_path)
    if not path.exists():
        return {"line_count": 0, "unique_urls": [], "duplicate_urls": []}

    urls: list[str] = []
    line_count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            line_count += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            for key in ("source_url", "canonical_url", "url"):
                url = str(item.get(key) or "").strip()
                if url:
                    urls.append(url)
                    break

    seen_keys: set[str] = set()
    duplicate_keys: set[str] = set()
    duplicates = []
    unique = []
    for url in urls:
        key = _url_key(url)
        if key in seen_keys:
            if key not in duplicate_keys:
                duplicates.append(url)
                duplicate_keys.add(key)
            continue
        seen_keys.add(key)
        unique.append(url)
    return {"line_count": line_count, "unique_urls": unique, "duplicate_urls": duplicates}


def _backup_state_file(state_path: str | Path) -> Optional[Path]:
    path = Path(state_path)
    if not path.exists():
        return None
    backup_path = path.with_suffix(path.suffix + ".bak")
    backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def _error_urls(result: Any, kind: str) -> list[str]:
    urls: list[str] = []
    for error in getattr(result, "errors", []) or []:
        if not isinstance(error, dict):
            continue
        url = str(error.get("url") or "").strip()
        if not url:
            continue
        error_value = str(error.get("error") or "").lower()
        if kind == "skipped" and "outside_allowed_domains" in error_value:
            urls.append(url)
        elif kind == "failed" and "outside_allowed_domains" not in error_value:
            urls.append(url)
    return _dedupe_preserve_order(urls)


def _has_block_error(result: Any) -> bool:
    for error in getattr(result, "errors", []) or []:
        if not isinstance(error, dict):
            continue
        values = " ".join(str(value) for value in error.values()).lower()
        if "403" in values or "429" in values:
            return True
    return False


def _extend_unique(target: list[str], values: list[str]) -> None:
    seen = {_url_key(url) for url in target}
    for value in values:
        key = _url_key(value)
        if key in seen:
            continue
        target.append(value)
        seen.add(key)


def _merge_without_success(existing: list[str], new_values: list[str], success: list[str]) -> list[str]:
    success_keys = {_url_key(url) for url in success}
    merged = _dedupe_preserve_url_key(existing + new_values)
    return [url for url in merged if _url_key(url) not in success_keys]


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover and crawl product URLs in resumable batches.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("--site", default="gotrangtri")
    discover_parser.add_argument("--max-urls", type=int, default=None)
    discover_parser.add_argument("--manifest", required=True)
    discover_parser.add_argument("--merge-existing", action=argparse.BooleanOptionalAction, default=True)
    discover_parser.add_argument("--overwrite", action="store_true")

    crawl_parser = subparsers.add_parser("crawl")
    crawl_parser.add_argument("--site", default="gotrangtri")
    crawl_parser.add_argument("--manifest", required=True)
    crawl_parser.add_argument("--state", required=True)
    crawl_parser.add_argument("--output", required=True)
    crawl_parser.add_argument("--tenant-id", default=None)
    crawl_parser.add_argument("--batch-size", type=int, default=100)
    crawl_parser.add_argument("--retry-failed", action="store_true")
    crawl_parser.add_argument("--until-done", action="store_true")
    crawl_parser.add_argument("--sleep-between-batches", type=float, default=5.0)
    crawl_parser.add_argument("--max-batches", type=int, default=None)
    crawl_parser.add_argument("--stop-on-block", action=argparse.BooleanOptionalAction, default=True)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--manifest", required=True)
    audit_parser.add_argument("--state", required=True)
    audit_parser.add_argument("--output", required=True)
    audit_parser.add_argument("--repair-state-from-output", action="store_true")

    args = parser.parse_args()

    if args.command == "audit":
        if args.repair_state_from_output:
            print(json.dumps(repair_state_from_output(args.manifest, args.state, args.output), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(audit_crawl_progress(args.manifest, args.state, args.output), ensure_ascii=False, indent=2))
        return

    adapter = _adapter_for_site(args.site)

    if args.command == "discover":
        summary = discover_and_write_manifest(
            adapter=adapter,
            manifest_path=args.manifest,
            max_urls=args.max_urls,
            merge_existing=args.merge_existing,
            overwrite=args.overwrite,
        )
        summary["manifest"] = args.manifest
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.until_done:
        summary = run_until_done(
            adapter=adapter,
            manifest_path=args.manifest,
            state_path=args.state,
            output_path=args.output,
            tenant_id=args.tenant_id,
            batch_size=args.batch_size,
            retry_failed=args.retry_failed,
            sleep_between_batches=args.sleep_between_batches,
            max_batches=args.max_batches,
            stop_on_block=args.stop_on_block,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    result = run_product_batch(
        adapter=adapter,
        manifest_path=args.manifest,
        state_path=args.state,
        output_path=args.output,
        tenant_id=args.tenant_id,
        batch_size=args.batch_size,
        retry_failed=args.retry_failed,
    )
    print(json.dumps(result["run"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
