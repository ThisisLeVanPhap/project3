import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from app.retrieval_service import load_kb, search_hits
from app.retrievers.schemas import RetrievalResult
from app.retrievers.text import fold_accents, repair_mojibake


PRICE_PASS_THRESHOLD = 0.6
DIAGNOSTIC_DEPTHS = (5, 10, 20, 50, 100)


def _is_out_of_scope_type(query_type: str) -> bool:
    return (query_type or "").startswith("out_of_scope")


def _normalize_text(value: Any) -> str:
    return fold_accents(repair_mojibake(str(value or ""))).lower().strip()


def _display_text(value: Any) -> str:
    return repair_mojibake(str(value or "")).strip()


def _hit_metadata(hit: RetrievalResult) -> Dict[str, Any]:
    return hit.metadata if isinstance(hit.metadata, dict) else {}


def hit_category(hit: RetrievalResult) -> str:
    return _display_text(_hit_metadata(hit).get("category"))


def hit_price(hit: RetrievalResult) -> Optional[float]:
    value = _hit_metadata(hit).get("price")
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def hit_url(hit: RetrievalResult) -> str:
    metadata = _hit_metadata(hit)
    return _display_text(
        metadata.get("canonical_url")
        or metadata.get("source_url")
        or metadata.get("url")
        or hit.source
    )


def product_record_url(record: Dict[str, Any]) -> str:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return _display_text(
        metadata.get("canonical_url")
        or metadata.get("source_url")
        or metadata.get("url")
        or record.get("url")
        or record.get("source")
    )


def product_record_category(record: Dict[str, Any]) -> str:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return _display_text(metadata.get("category"))


def product_record_price(record: Dict[str, Any]) -> Optional[float]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    value = metadata.get("price")
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def product_record_text(record: Dict[str, Any]) -> str:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    parts = [
        record.get("title"),
        record.get("text"),
        record.get("content"),
        record.get("url"),
        metadata.get("product_name"),
        metadata.get("sku"),
        metadata.get("category"),
        metadata.get("material"),
        metadata.get("color"),
        metadata.get("brand"),
    ]
    return " ".join(_display_text(part) for part in parts if part not in (None, ""))


def category_matches(actual: str, expected: str) -> bool:
    actual_norm = _normalize_text(actual)
    expected_norm = _normalize_text(expected)
    return bool(actual_norm and expected_norm) and (
        actual_norm == expected_norm
        or actual_norm in expected_norm
        or expected_norm in actual_norm
    )


def price_matches(price: Optional[float], price_label: Dict[str, Any]) -> bool:
    if not price_label:
        return True
    if price is None:
        return False
    min_price = price_label.get("min")
    max_price = price_label.get("max")
    if min_price is not None and price < float(min_price):
        return False
    if max_price is not None and price > float(max_price):
        return False
    return True


def terms_match(text: str, required_terms_any: Sequence[str]) -> bool:
    terms = [_normalize_text(term) for term in (required_terms_any or []) if _normalize_text(term)]
    if not terms:
        return True
    haystack = _normalize_text(text)
    return any(term in haystack for term in terms)


def represented_categories(
    hits: Sequence[RetrievalResult],
    expected_categories: Sequence[str],
) -> List[str]:
    represented: List[str] = []
    for expected in expected_categories:
        if any(category_matches(hit_category(hit), expected) for hit in hits):
            represented.append(expected)
    return represented


def category_coverage(
    hits: Sequence[RetrievalResult],
    expected_categories: Sequence[str],
) -> Tuple[int, float, List[str]]:
    expected = list(expected_categories or [])
    if not expected:
        return 0, 0.0, []
    represented = represented_categories(hits, expected)
    return len(represented), len(represented) / len(expected), represented


def price_satisfaction(hits: Sequence[RetrievalResult], price_label: Dict[str, Any]) -> Optional[float]:
    if not price_label:
        return None

    product_hits = [
        hit for hit in hits
        if _normalize_text(_hit_metadata(hit).get("doc_type")) == "product"
    ]
    if not product_hits:
        return 0.0

    min_price = price_label.get("min")
    max_price = price_label.get("max")
    satisfied = 0
    for hit in product_hits:
        price = hit_price(hit)
        if price is None:
            continue
        if min_price is not None and price < float(min_price):
            continue
        if max_price is not None and price > float(max_price):
            continue
        satisfied += 1
    return satisfied / len(product_hits)


def duplicate_rate(hits: Sequence[RetrievalResult]) -> float:
    if not hits:
        return 0.0
    urls = [hit_url(hit) for hit in hits if hit_url(hit)]
    if not urls:
        return 0.0
    duplicate_count = len(urls) - len(set(urls))
    return duplicate_count / len(hits)


def required_terms_hit(hits: Sequence[RetrievalResult], required_terms_any: Sequence[str]) -> bool:
    haystack = "\n".join(
        " ".join([
            hit.title,
            hit.text,
            hit.source,
            json.dumps(_hit_metadata(hit), ensure_ascii=False, default=str),
        ])
        for hit in hits
    )
    return terms_match(haystack, required_terms_any)


def serialize_hit(hit: RetrievalResult, rank: int) -> Dict[str, Any]:
    metadata = _hit_metadata(hit)
    return {
        "rank": rank,
        "title": _display_text(hit.title),
        "score": round(hit.score, 6),
        "category": hit_category(hit),
        "price": hit_price(hit),
        "url": hit_url(hit),
        "doc_type": _display_text(metadata.get("doc_type")),
    }


def evaluate_query(query_spec: Dict[str, Any], hits: Sequence[RetrievalResult], latency_ms: float) -> Dict[str, Any]:
    expected_categories = query_spec.get("expected_categories") or []
    price_label = query_spec.get("price") or {}
    coverage_count, coverage_ratio, represented = category_coverage(hits, expected_categories)
    category_hit = coverage_count > 0 if expected_categories else None
    price_ratio = price_satisfaction(hits, price_label)
    dup_rate = duplicate_rate(hits)
    terms_hit = required_terms_hit(hits, query_spec.get("required_terms_any") or [])

    query_type = query_spec.get("type") or "unknown"
    if _is_out_of_scope_type(query_type):
        weak_success = None
    else:
        checks = []
        if expected_categories:
            checks.append(bool(category_hit))
        if price_label:
            checks.append(price_ratio is not None and price_ratio >= PRICE_PASS_THRESHOLD)
        if len(expected_categories) >= 2:
            checks.append(coverage_count >= 2)
        weak_success = all(checks) if checks else True

    return {
        "id": query_spec.get("id"),
        "query": query_spec.get("query"),
        "type": query_type,
        "expected_categories": expected_categories,
        "represented_categories": represented,
        "required_terms_any": query_spec.get("required_terms_any") or [],
        "required_terms_hit": terms_hit,
        "price": price_label,
        "category_hit_at_k": category_hit,
        "category_coverage_count": coverage_count,
        "category_coverage": round(coverage_ratio, 6),
        "price_satisfaction": None if price_ratio is None else round(price_ratio, 6),
        "duplicate_rate": round(dup_rate, 6),
        "latency_ms": round(latency_ms, 3),
        "result_count": len(hits),
        "weak_success": weak_success,
        "notes": query_spec.get("notes", ""),
        "hits": [serialize_hit(hit, idx + 1) for idx, hit in enumerate(hits)],
    }


def load_product_records(kb_dir: str) -> List[Dict[str, Any]]:
    chunks_path = Path(kb_dir) / "chunks.jsonl"
    records: List[Dict[str, Any]] = []
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
            if _normalize_text(metadata.get("doc_type")) == "product":
                records.append(record)
    return records


def _record_matches_query_spec(record: Dict[str, Any], query_spec: Dict[str, Any]) -> bool:
    expected_categories = query_spec.get("expected_categories") or []
    if expected_categories and not any(
        category_matches(product_record_category(record), expected)
        for expected in expected_categories
    ):
        return False
    if not price_matches(product_record_price(record), query_spec.get("price") or {}):
        return False
    if not terms_match(product_record_text(record), query_spec.get("required_terms_any") or []):
        return False
    return True


def scan_oracle_products(
    query_spec: Dict[str, Any],
    product_records: Sequence[Dict[str, Any]],
    sample_limit: int = 5,
) -> Dict[str, Any]:
    matches = [record for record in product_records if _record_matches_query_spec(record, query_spec)]
    category_counts: Dict[str, int] = defaultdict(int)
    for record in matches:
        category_counts[product_record_category(record)] += 1
    samples = [
        {
            "title": _display_text(record.get("title")),
            "category": product_record_category(record),
            "price": product_record_price(record),
            "url": product_record_url(record),
        }
        for record in matches[:sample_limit]
    ]
    return {
        "oracle_match_count": len(matches),
        "oracle_urls": {product_record_url(record) for record in matches if product_record_url(record)},
        "oracle_category_counts": dict(sorted(category_counts.items())),
        "oracle_samples": samples,
    }


def hit_matches_query_spec(hit: RetrievalResult, query_spec: Dict[str, Any]) -> bool:
    expected_categories = query_spec.get("expected_categories") or []
    if expected_categories and not any(category_matches(hit_category(hit), expected) for expected in expected_categories):
        return False
    if not price_matches(hit_price(hit), query_spec.get("price") or {}):
        return False
    text = " ".join([
        hit.title,
        hit.text,
        hit.source,
        json.dumps(_hit_metadata(hit), ensure_ascii=False, default=str),
    ])
    if not terms_match(text, query_spec.get("required_terms_any") or []):
        return False
    return True


def candidate_recall_at_depths(
    query_spec: Dict[str, Any],
    hits_by_depth: Dict[int, Sequence[RetrievalResult]],
    oracle_urls: Set[str],
    oracle_match_count: int,
    depths: Sequence[int] = DIAGNOSTIC_DEPTHS,
) -> Dict[str, Optional[float]]:
    recalls: Dict[str, Optional[float]] = {}
    for depth in depths:
        hits = hits_by_depth.get(depth, [])
        if oracle_match_count <= 0:
            recalls[str(depth)] = None
            continue
        if oracle_urls:
            hit_urls = {hit_url(hit) for hit in hits if hit_url(hit)}
            recalls[str(depth)] = round(len(hit_urls & oracle_urls) / oracle_match_count, 6)
        else:
            matched = sum(1 for hit in hits if hit_matches_query_spec(hit, query_spec))
            recalls[str(depth)] = round(matched / oracle_match_count, 6)
    return recalls


def category_distribution(hits: Sequence[RetrievalResult]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for hit in hits:
        counts[hit_category(hit)] += 1
    return dict(sorted(counts.items()))


def _full_category_coverage(report: Dict[str, Any]) -> bool:
    expected = report.get("expected_categories") or []
    if not expected:
        return True
    return report.get("category_coverage_count", 0) >= len(expected)


def diagnose_failure(
    query_spec: Dict[str, Any],
    depth_reports: Dict[int, Dict[str, Any]],
    hits_by_depth: Dict[int, Sequence[RetrievalResult]],
    oracle: Dict[str, Any],
) -> Tuple[Optional[str], str]:
    top5 = depth_reports[5]
    if top5["weak_success"] is None or top5["weak_success"]:
        return None, "No retrieval fix needed for this query at top5."

    oracle_count = oracle["oracle_match_count"]
    query_type = query_spec.get("type") or "unknown"
    expected = query_spec.get("expected_categories") or []
    top100 = depth_reports[100]
    top100_hits = hits_by_depth.get(100, [])
    top100_has_match = any(hit_matches_query_spec(hit, query_spec) for hit in top100_hits)
    top5_has_category = bool(top5["category_hit_at_k"])
    has_price = bool(query_spec.get("price") or {})

    if oracle_count == 0:
        return "data_missing", "Inspect data coverage or relax the weak label; no direct metadata oracle match was found."

    if len(expected) >= 2 and not _full_category_coverage(top5):
        missing = [category for category in expected if category not in top5["represented_categories"]]
        top100_represented = set(top100["represented_categories"])
        if all(category in top100_represented for category in missing):
            return "multi_intent_coverage_failure", "Add query decomposition or fusion so each requested category is represented in top results."

    if has_price and top5_has_category and (top5["price_satisfaction"] or 0.0) < PRICE_PASS_THRESHOLD:
        return "constraint_filter_failure", "Investigate price-aware candidate widening/filter ordering; category matches but top results violate the price label."

    if top100_has_match:
        for depth in (10, 20, 50, 100):
            if depth_reports[depth]["weak_success"]:
                return "reranking_failure", f"Relevant candidates appear by top{depth}; improve reranking or fusion before top5."
        if query_type == "room_style":
            return "semantic_gap", "Add synonym/semantic mappings for room and style intent before changing storage."
        return "reranking_failure", "Oracle-like candidates appear in top100 but the top5 ranking still fails."

    if query_type == "room_style":
        if top5["result_count"] > 0:
            return "semantic_gap", "Keyword retrieval is not mapping room/style wording to the intended product categories."
        return "candidate_generation_failure", "No oracle-like candidate appears in top100."

    if top5["result_count"] > 0 and not top5["required_terms_hit"] and top5["category_hit_at_k"]:
        return "benchmark_label_issue", "Top results match the category but not the weak text terms; review whether labels are too narrow."

    return "candidate_generation_failure", "Oracle matches exist in the KB but no oracle-like candidate appears in top100."


def evaluate_query_depths(
    query_spec: Dict[str, Any],
    hits_by_depth: Dict[int, Sequence[RetrievalResult]],
    latency_by_depth: Dict[int, float],
    product_records: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    depth_reports = {
        depth: evaluate_query(query_spec, hits_by_depth.get(depth, []), latency_by_depth.get(depth, 0.0))
        for depth in DIAGNOSTIC_DEPTHS
    }
    oracle = scan_oracle_products(query_spec, product_records)
    recall = candidate_recall_at_depths(
        query_spec,
        hits_by_depth,
        oracle["oracle_urls"],
        oracle["oracle_match_count"],
    )
    diagnosis, recommendation = diagnose_failure(query_spec, depth_reports, hits_by_depth, oracle)
    return {
        "id": query_spec.get("id"),
        "query": query_spec.get("query"),
        "type": query_spec.get("type") or "unknown",
        "expected_categories": query_spec.get("expected_categories") or [],
        "price": query_spec.get("price") or {},
        "pass_by_depth": {
            str(depth): depth_reports[depth]["weak_success"]
            for depth in DIAGNOSTIC_DEPTHS
        },
        "metrics_by_depth": {
            str(depth): {
                "category_hit_at_k": depth_reports[depth]["category_hit_at_k"],
                "category_coverage": depth_reports[depth]["category_coverage"],
                "category_coverage_count": depth_reports[depth]["category_coverage_count"],
                "represented_categories": depth_reports[depth]["represented_categories"],
                "price_satisfaction": depth_reports[depth]["price_satisfaction"],
                "duplicate_rate": depth_reports[depth]["duplicate_rate"],
                "result_count": depth_reports[depth]["result_count"],
                "latency_ms": depth_reports[depth]["latency_ms"],
            }
            for depth in DIAGNOSTIC_DEPTHS
        },
        "oracle_match_count": oracle["oracle_match_count"],
        "oracle_category_counts": oracle["oracle_category_counts"],
        "oracle_recall_by_depth": recall,
        "oracle_samples": oracle["oracle_samples"],
        "top5": depth_reports[5]["hits"],
        "top20_category_distribution": category_distribution(hits_by_depth.get(20, [])),
        "top100_category_distribution": category_distribution(hits_by_depth.get(100, [])),
        "diagnosis": diagnosis,
        "recommendation": recommendation,
        "notes": query_spec.get("notes", ""),
    }


def build_diagnostic_report(query_reports: Sequence[Dict[str, Any]], kb_dir: str) -> Dict[str, Any]:
    product_reports = [report for report in query_reports if not _is_out_of_scope_type(report["type"])]
    diagnosis_counts: Dict[str, int] = defaultdict(int)
    for report in product_reports:
        if report["diagnosis"]:
            diagnosis_counts[report["diagnosis"]] += 1
    summary = {
        "total_queries": len(query_reports),
        "evaluated_product_queries": len(product_reports),
        "diagnosis_counts": dict(sorted(diagnosis_counts.items())),
    }
    for depth in DIAGNOSTIC_DEPTHS:
        values = [
            report["pass_by_depth"][str(depth)]
            for report in product_reports
            if report["pass_by_depth"][str(depth)] is not None
        ]
        summary[f"pass_at_{depth}"] = (
            round(sum(1 for value in values if value) / len(values), 6)
            if values else None
        )
    return {
        "kb_dir": kb_dir,
        "depths": list(DIAGNOSTIC_DEPTHS),
        "summary": summary,
        "queries": list(query_reports),
    }


def run_diagnostic_evaluation(kb_dir: str, queries_path: str) -> Dict[str, Any]:
    kb = load_kb(kb_dir)
    if kb is None:
        raise ValueError(f"Could not load KB from: {kb_dir}")
    product_records = load_product_records(kb_dir)

    query_reports: List[Dict[str, Any]] = []
    for query_spec in load_queries(queries_path):
        hits_by_depth: Dict[int, Sequence[RetrievalResult]] = {}
        latency_by_depth: Dict[int, float] = {}
        for depth in DIAGNOSTIC_DEPTHS:
            started = time.perf_counter()
            hits_by_depth[depth] = search_hits(kb, query_spec.get("query", ""), k=depth)
            latency_by_depth[depth] = (time.perf_counter() - started) * 1000
        query_reports.append(
            evaluate_query_depths(query_spec, hits_by_depth, latency_by_depth, product_records)
        )
    return build_diagnostic_report(query_reports, kb_dir=kb_dir)


def summarize_by_type(query_reports: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for report in query_reports:
        grouped[report["type"]].append(report)

    summary: Dict[str, Any] = {}
    for query_type, reports in sorted(grouped.items()):
        passable = [report for report in reports if report["weak_success"] is not None]
        price_values = [
            report["price_satisfaction"]
            for report in reports
            if report["price_satisfaction"] is not None
        ]
        category_values = [
            1.0 if report["category_hit_at_k"] else 0.0
            for report in reports
            if report["category_hit_at_k"] is not None
        ]
        summary[query_type] = {
            "query_count": len(reports),
            "pass_rate": (
                round(sum(1 for report in passable if report["weak_success"]) / len(passable), 6)
                if passable else None
            ),
            "category_hit_rate": round(mean(category_values), 6) if category_values else None,
            "avg_category_coverage": round(mean(report["category_coverage"] for report in reports), 6),
            "avg_price_satisfaction": round(mean(price_values), 6) if price_values else None,
            "avg_duplicate_rate": round(mean(report["duplicate_rate"] for report in reports), 6),
            "avg_latency_ms": round(mean(report["latency_ms"] for report in reports), 3),
            "avg_result_count": round(mean(report["result_count"] for report in reports), 3),
        }
    return summary


def build_report(query_reports: Sequence[Dict[str, Any]], k: int, kb_dir: str) -> Dict[str, Any]:
    passable = [report for report in query_reports if report["weak_success"] is not None]
    failed = [report for report in passable if not report["weak_success"]]
    return {
        "kb_dir": kb_dir,
        "k": k,
        "total_queries": len(query_reports),
        "evaluated_product_queries": len(passable),
        "overall_pass_rate": (
            round(sum(1 for report in passable if report["weak_success"]) / len(passable), 6)
            if passable else None
        ),
        "avg_latency_ms": round(mean(report["latency_ms"] for report in query_reports), 3)
        if query_reports else 0.0,
        "metrics_by_type": summarize_by_type(query_reports),
        "failed_queries": [
            {
                "id": report["id"],
                "query": report["query"],
                "type": report["type"],
                "category_coverage": report["category_coverage"],
                "represented_categories": report["represented_categories"],
                "price_satisfaction": report["price_satisfaction"],
                "result_count": report["result_count"],
                "top_categories": [hit["category"] for hit in report["hits"]],
                "top_titles": [hit["title"] for hit in report["hits"][:3]],
            }
            for report in failed
        ],
        "queries": list(query_reports),
    }


def load_queries(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Benchmark query file must contain a JSON list.")
    return data


def run_evaluation(kb_dir: str, queries_path: str, k: int) -> Dict[str, Any]:
    kb = load_kb(kb_dir)
    if kb is None:
        raise ValueError(f"Could not load KB from: {kb_dir}")

    query_reports: List[Dict[str, Any]] = []
    for query_spec in load_queries(queries_path):
        started = time.perf_counter()
        hits = search_hits(kb, query_spec.get("query", ""), k=k)
        latency_ms = (time.perf_counter() - started) * 1000
        query_reports.append(evaluate_query(query_spec, hits, latency_ms))
    return build_report(query_reports, k=k, kb_dir=kb_dir)


def write_report(report: Dict[str, Any], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Evaluate product retrieval quality against weak labels.")
    parser.add_argument("--kb-dir", required=True, help="KB directory containing chunks.jsonl and index.json.")
    parser.add_argument("--queries", required=True, help="Benchmark query JSON file.")
    parser.add_argument("--k", type=int, default=5, help="Top-k retrieval depth.")
    parser.add_argument("--output", required=True, help="Output report JSON path.")
    parser.add_argument(
        "--diagnostic-output",
        help="Optional diagnostic report JSON path with depth/oracle/failure labels.",
    )
    parser.add_argument(
        "--diagnostic-only",
        action="store_true",
        help="Only write the diagnostic report. Requires --diagnostic-output.",
    )
    args = parser.parse_args(argv)

    report = None
    if not args.diagnostic_only:
        report = run_evaluation(args.kb_dir, args.queries, args.k)
        write_report(report, args.output)

    diagnostic_report = None
    if args.diagnostic_output:
        diagnostic_report = run_diagnostic_evaluation(args.kb_dir, args.queries)
        write_report(diagnostic_report, args.diagnostic_output)

    if args.diagnostic_only and not args.diagnostic_output:
        parser.error("--diagnostic-only requires --diagnostic-output")

    console: Dict[str, Any]
    if diagnostic_report is not None and report is None:
        console = {
            **diagnostic_report["summary"],
            "output": args.diagnostic_output,
        }
    elif diagnostic_report is not None and report is not None:
        console = {
            "total_queries": report["total_queries"],
            "evaluated_product_queries": report["evaluated_product_queries"],
            "overall_pass_rate": report["overall_pass_rate"],
            "avg_latency_ms": report["avg_latency_ms"],
            "failed_query_count": len(report["failed_queries"]),
            "output": args.output,
            "diagnostic_output": args.diagnostic_output,
            "diagnosis_counts": diagnostic_report["summary"]["diagnosis_counts"],
            "pass_at_5": diagnostic_report["summary"]["pass_at_5"],
            "pass_at_20": diagnostic_report["summary"]["pass_at_20"],
            "pass_at_50": diagnostic_report["summary"]["pass_at_50"],
            "pass_at_100": diagnostic_report["summary"]["pass_at_100"],
        }
    else:
        console = {
            "total_queries": report["total_queries"],
            "evaluated_product_queries": report["evaluated_product_queries"],
            "overall_pass_rate": report["overall_pass_rate"],
            "avg_latency_ms": report["avg_latency_ms"],
            "failed_query_count": len(report["failed_queries"]),
            "output": args.output,
        }
    print(
        json.dumps(
            console,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
