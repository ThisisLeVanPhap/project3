import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence

from app.answer_evaluator import evaluate_answer_grounding, extract_context_facts
from app.retrieval_service import format_context, load_kb, search_hits
from app.sales_flow import build_sales_prefix


def load_json_list(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    return data


def _is_price_query(query_spec: Dict[str, Any]) -> bool:
    behavior = query_spec.get("expected_behavior") or {}
    return query_spec.get("type") == "price_constraint" or bool(behavior.get("price"))


def _duplicate_product_blocks(context: str) -> int:
    facts = extract_context_facts(context)
    seen = set()
    duplicates = 0
    for product in facts["products"].values():
        source = product.get("source_url")
        if not source:
            continue
        if source in seen:
            duplicates += 1
        seen.add(source)
    return duplicates


def evaluate_context_readiness(kb: Any, query_spec: Dict[str, Any], k: int = 5) -> Dict[str, Any]:
    hits = search_hits(kb, query_spec.get("query", ""), k=k)
    context = format_context(hits)
    prefix = build_sales_prefix("propose", {})
    facts = extract_context_facts(context)
    products = facts["products"]

    context_has_products = bool(products)
    source_count = sum(1 for product in products.values() if product.get("source_url"))
    price_count = sum(1 for product in products.values() if product.get("price"))
    missing_required_context_fields: List[str] = []
    behavior = query_spec.get("expected_behavior") or {}
    if behavior.get("must_have_citation") and not context_has_products:
        missing_required_context_fields.append("products")
    if behavior.get("should_include_source_link") and context_has_products and source_count == 0:
        missing_required_context_fields.append("source_url")
    if _is_price_query(query_spec) and context_has_products and price_count == 0:
        missing_required_context_fields.append("price")

    context_ready = not missing_required_context_fields
    return {
        "id": query_spec.get("id"),
        "query": query_spec.get("query"),
        "type": query_spec.get("type"),
        "context_ready": context_ready,
        "context_has_products": context_has_products,
        "context_has_source_links": source_count > 0,
        "context_has_price_for_price_query": (price_count > 0) if _is_price_query(query_spec) else None,
        "context_product_count": len(products),
        "context_length": len(context),
        "duplicate_product_blocks": _duplicate_product_blocks(context),
        "missing_required_context_fields": missing_required_context_fields,
        "prompt_has_grounding_contract": "GROUNDED PRODUCT ANSWER CONTRACT" in prefix,
        "context_preview": context[:1200],
    }


def run_context_mode(kb_dir: str, queries_path: str, k: int = 5) -> Dict[str, Any]:
    query_specs = load_json_list(queries_path)
    kb = load_kb(kb_dir)
    if kb is None:
        raise ValueError(f"Could not load KB from: {kb_dir}")
    rows = [evaluate_context_readiness(kb, query_spec, k=k) for query_spec in query_specs]
    price_rows = [row for row in rows if row["context_has_price_for_price_query"] is not None]
    summary = {
        "total_queries": len(rows),
        "context_ready_rate": round(sum(1 for row in rows if row["context_ready"]) / len(rows), 6) if rows else None,
        "avg_context_products": round(mean(row["context_product_count"] for row in rows), 3) if rows else 0.0,
        "avg_context_length": round(mean(row["context_length"] for row in rows), 3) if rows else 0.0,
        "source_link_presence_rate": round(sum(1 for row in rows if row["context_has_source_links"]) / len(rows), 6) if rows else None,
        "price_presence_for_price_queries": (
            round(sum(1 for row in price_rows if row["context_has_price_for_price_query"]) / len(price_rows), 6)
            if price_rows else None
        ),
    }
    return {"summary": summary, "queries": rows}


def run_answers_mode(queries_path: str, answers_path: str) -> Dict[str, Any]:
    query_specs = {row["id"]: row for row in load_json_list(queries_path)}
    query_specs_by_text = {row.get("query"): row for row in query_specs.values() if row.get("query")}
    answer_rows = load_json_list(answers_path)
    evaluated = []
    for row in answer_rows:
        query_spec = query_specs.get(row.get("id")) or query_specs_by_text.get(row.get("query")) or {
            "id": row.get("id"),
            "query": row.get("query"),
            "type": "sample",
            "expected_behavior": {
                "must_have_citation": True,
                "should_include_source_link": True,
                "must_not_fabricate_missing_fields": True,
            },
        }
        metrics = evaluate_answer_grounding(query_spec, row.get("context", ""), row.get("answer", ""))
        evaluated.append({
            "id": row.get("id"),
            "query": row.get("query") or query_spec.get("query"),
            "pass": metrics["pass"],
            "metrics": metrics,
        })
    summary = {
        "total_answers": len(evaluated),
        "pass_rate": round(sum(1 for row in evaluated if row["pass"]) / len(evaluated), 6) if evaluated else None,
        "citation_validity_rate": round(sum(1 for row in evaluated if row["metrics"]["citation_validity"]) / len(evaluated), 6) if evaluated else None,
        "price_consistency_rate": round(sum(1 for row in evaluated if row["metrics"]["price_consistency"]) / len(evaluated), 6) if evaluated else None,
        "hallucination_failure_count": sum(
            1 for row in evaluated
            if not row["metrics"]["no_forbidden_hallucination"]
            or not row["metrics"]["price_consistency"]
            or not row["metrics"]["product_name_grounded"]
        ),
    }
    return {"summary": summary, "answers": evaluated}


def write_report(report: Dict[str, Any], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Evaluate answer grounding readiness or answer files.")
    parser.add_argument("--mode", choices=["context", "answers"], required=True)
    parser.add_argument("--queries", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--kb-dir")
    parser.add_argument("--answers")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args(argv)

    if args.mode == "context":
        if not args.kb_dir:
            parser.error("--kb-dir is required for --mode context")
        report = run_context_mode(args.kb_dir, args.queries, k=args.k)
    else:
        if not args.answers:
            parser.error("--answers is required for --mode answers")
        report = run_answers_mode(args.queries, args.answers)

    write_report(report, args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
