import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from app.answer_evaluator import extract_answer_citations, extract_context_facts
from app.retrievers.text import fold_accents, repair_mojibake


FORBIDDEN_FIELDS = {
    "warranty": [r"bảo hành", r"bao hanh"],
    "shipping": [r"vận chuyển", r"van chuyen", r"ship", r"giao hàng", r"giao hang", r"miễn phí", r"mien phi"],
    "installation": [r"lắp đặt", r"lap dat"],
    "showroom": [r"showroom"],
    "stock": [r"còn hàng", r"con hang", r"tồn kho", r"ton kho"],
    "address": [r"địa chỉ", r"dia chi"],
    "policy": [r"chính sách", r"chinh sach", r"đổi trả", r"doi tra"],
    "recruiting": [r"tuyển dụng", r"tuyen dung", r"nhân viên", r"nhan vien"],
}
MISSING_INFO_RE = re.compile(
    r"(chưa thấy|không thấy|chưa có|không có|không tìm thấy|không đủ|không có thông tin|"
    r"khong co thong tin|dữ liệu hiện có|du lieu hien co|không hỗ trợ|khong ho tro)",
    re.I,
)
PRICE_FALSE_POSITIVE_HINT_RE = re.compile(
    r"(dưới|duoi|không quá|khong qua|tối đa|toi da|ngân sách|ngan sach|"
    r"tầm giá|tam gia|trong tầm|trong tam|khoảng giá|khoang gia|~|từ\s+~?|tu\s+~?)",
    re.I,
)
PRODUCT_TYPES = {"product_listing", "price_constraint", "comparison", "matching"}


def _clean(value: Any) -> str:
    return repair_mojibake(str(value or "")).strip()


def _norm(value: Any) -> str:
    return fold_accents(_clean(value)).lower()


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(data: Mapping[str, Any], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _answer_excerpt(answer: str, max_chars: int = 900) -> str:
    text = " ".join(_clean(answer).split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def context_products(context: str, limit: int = 3) -> List[Dict[str, Any]]:
    facts = extract_context_facts(context)
    rows = []
    for pid, product in list(facts["products"].items())[:limit]:
        rows.append({
            "pid": pid,
            "name": product.get("product_name"),
            "price": product.get("price"),
            "source_url": product.get("source_url"),
        })
    return rows


def _context_has_field(context_norm: str, field: str) -> bool:
    patterns = FORBIDDEN_FIELDS[field]
    return any(re.search(pattern, context_norm, re.I) for pattern in patterns)


def detect_hallucinated_fields(answer: str, context: str) -> List[str]:
    answer_norm = _norm(answer)
    context_norm = _norm(context)
    if MISSING_INFO_RE.search(answer_norm):
        return []
    hallucinated = []
    for field, patterns in FORBIDDEN_FIELDS.items():
        if any(re.search(pattern, answer_norm, re.I) for pattern in patterns) and not _context_has_field(context_norm, field):
            hallucinated.append(field)
    return hallucinated


def _price_false_positive(answer: str, query: str, mismatched_prices: Sequence[int]) -> bool:
    if not mismatched_prices:
        return False
    text = _norm(f"{query}\n{answer}")
    for price in mismatched_prices:
        patterns = _price_patterns(price)
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                window = text[max(0, match.start() - 40): min(len(text), match.end() + 40)]
                if PRICE_FALSE_POSITIVE_HINT_RE.search(window):
                    return True
    return False


def _price_patterns(price: int) -> List[str]:
    patterns = [re.escape(f"{price:,}".replace(",", "."))]
    if price % 1_000_000 == 0:
        value = price // 1_000_000
        patterns.extend([rf"\b{value}\s*(?:trieu|triệu|tr|m)\b"])
    if price % 100_000 == 0:
        value = price / 1_000_000
        decimal = str(value).replace(".", "[,.]")
        patterns.extend([rf"\b{decimal}\s*(?:trieu|triệu|tr|m)\b"])
    if price % 1_000 == 0:
        value = price // 1_000
        patterns.extend([rf"\b{value}\s*k\b"])
    return sorted(set(patterns), key=len, reverse=True)


def _has_source_url(answer: str) -> bool:
    return bool(re.search(r"https?://", answer or ""))


def _needs_template(query_type: str, metrics: Mapping[str, Any], answer: str) -> bool:
    if query_type not in PRODUCT_TYPES:
        return False
    citations = extract_answer_citations(answer)
    has_product_evidence = bool(citations)
    missing_link = bool(metrics.get("source_link_missing"))
    missing_citation = not metrics.get("has_required_citation", True)
    missing_format = has_product_evidence and ("Giá:" not in answer or "Link" not in answer and not _has_source_url(answer))
    return bool(missing_link or missing_citation or missing_format)


def classify_failed_answer(
    answer_row: Mapping[str, Any],
    eval_row: Mapping[str, Any],
) -> Dict[str, Any]:
    metrics = eval_row.get("metrics") or {}
    answer = _clean(answer_row.get("answer"))
    query = _clean(eval_row.get("query") or answer_row.get("query"))
    query_type = _clean(answer_row.get("type") or "")
    context = _clean(answer_row.get("context"))
    price_details = metrics.get("price_details") or {}
    mismatched_prices = price_details.get("mismatched_prices") or []
    hallucinated_fields = detect_hallucinated_fields(answer, context)
    failure_types: Set[str] = set()

    if hallucinated_fields or not metrics.get("no_forbidden_hallucination", True) and not MISSING_INFO_RE.search(_norm(answer)):
        failure_types.add("real_hallucination")

    if not metrics.get("price_consistency", True):
        if price_details.get("query_constraint_prices"):
            failure_types.add("query_constraint_price_ignored")
        elif price_details.get("approximate_or_range_prices"):
            failure_types.add("approximate_range_price_ignored")
        elif _price_false_positive(answer, query, mismatched_prices):
            failure_types.add("price_evaluator_false_positive")
        else:
            failure_types.add("price_mismatch_real")

    citations = extract_answer_citations(answer)
    if citations and (metrics.get("source_link_missing") or not metrics.get("source_link_presence", True)):
        failure_types.add("source_link_missing")

    if not metrics.get("missing_field_handling", True):
        failure_types.add("missing_field_not_handled")

    if query_type in PRODUCT_TYPES and (
        not metrics.get("has_required_citation", True)
        or not metrics.get("product_name_grounded", True)
        or (citations and metrics.get("source_link_missing"))
    ):
        failure_types.add("prompt_contract_not_followed")

    if not metrics.get("product_name_grounded", True) and query_type.startswith("out_of_scope"):
        failure_types.add("evaluator_false_positive")
    if metrics.get("out_of_scope_fallback_valid"):
        failure_types.add("out_of_scope_fallback_valid")

    if _needs_template(query_type, metrics, answer):
        failure_types.add("answer_template_needed")

    if not failure_types:
        failure_types.add("unknown")

    if (
        "price_evaluator_false_positive" in failure_types
        or "evaluator_false_positive" in failure_types
        or "query_constraint_price_ignored" in failure_types
        or "approximate_range_price_ignored" in failure_types
    ):
        recommended_fix = "evaluator"
    elif "answer_template_needed" in failure_types or "prompt_contract_not_followed" in failure_types:
        recommended_fix = "answer_template"
    elif "real_hallucination" in failure_types or "missing_field_not_handled" in failure_types:
        recommended_fix = "answer_template"
    elif "source_link_missing" in failure_types:
        recommended_fix = "prompt"
    else:
        recommended_fix = "none"

    diagnosis = _diagnosis_text(failure_types, hallucinated_fields, mismatched_prices)
    return {
        "id": eval_row.get("id") or answer_row.get("id"),
        "query": query,
        "type": query_type,
        "failure_types": sorted(failure_types),
        "metrics": metrics,
        "context_products": context_products(context),
        "answer_excerpt": _answer_excerpt(answer),
        "detected_prices": price_details.get("detected_prices") or [],
        "context_prices": price_details.get("context_prices") or [],
        "hallucinated_fields": hallucinated_fields,
        "diagnosis": diagnosis,
        "recommended_fix": recommended_fix,
    }


def _diagnosis_text(failure_types: Set[str], hallucinated_fields: Sequence[str], mismatched_prices: Sequence[int]) -> str:
    parts = []
    if "real_hallucination" in failure_types:
        parts.append(f"Answer mentions unsupported fields: {', '.join(hallucinated_fields) or 'unknown'}.")
    if "price_mismatch_real" in failure_types:
        parts.append(f"Answer contains prices not found in context: {list(mismatched_prices)}.")
    if "price_evaluator_false_positive" in failure_types:
        parts.append("Price failure is likely a threshold/range/budget number rather than a product price.")
    if "query_constraint_price_ignored" in failure_types:
        parts.append("Query constraint price was identified and should be ignored by product price consistency.")
    if "approximate_range_price_ignored" in failure_types:
        parts.append("Approximate/range price was identified and should not be tied to one product.")
    if "source_link_missing" in failure_types:
        parts.append("Answer cites product ids but omits required source links.")
    if "prompt_contract_not_followed" in failure_types:
        parts.append("Answer does not follow the required grounded product format.")
    if "missing_field_not_handled" in failure_types:
        parts.append("Answer does not use the required missing-field fallback.")
    if "evaluator_false_positive" in failure_types:
        parts.append("Out-of-scope or policy fallback appears useful, but evaluator treated product words as ungrounded.")
    if "out_of_scope_fallback_valid" in failure_types:
        parts.append("Out-of-scope fallback is valid and should not require product citations.")
    if "answer_template_needed" in failure_types:
        parts.append("LLM formatting is unstable enough that rendering product cards in code is likely safer.")
    return " ".join(parts) or "Failure requires manual review."


def analyze_failures(answers_path: str, eval_report_path: str) -> Dict[str, Any]:
    answers = load_json(answers_path)
    eval_report = load_json(eval_report_path)
    answers_by_id = {row.get("id"): row for row in answers}
    failed = []
    counts: Counter[str] = Counter()
    recommended_counts: Counter[str] = Counter()
    ignored_price_counts: Counter[str] = Counter()

    for eval_row in eval_report.get("answers", []):
        details = ((eval_row.get("metrics") or {}).get("price_details") or {})
        if details.get("query_constraint_prices"):
            ignored_price_counts["query_constraint_price_ignored"] += 1
        if details.get("approximate_or_range_prices"):
            ignored_price_counts["approximate_range_price_ignored"] += 1
        if details.get("aggregate_prices"):
            ignored_price_counts["aggregate_price_ignored"] += 1
        if eval_row.get("pass"):
            continue
        answer_row = answers_by_id.get(eval_row.get("id"), {})
        row = classify_failed_answer(answer_row, eval_row)
        failed.append(row)
        counts.update(row["failure_types"])
        recommended_counts.update([row["recommended_fix"]])

    summary = {
        "total_failed": len(failed),
        "failure_type_counts": dict(sorted(counts.items())),
        "real_hallucination_count": counts.get("real_hallucination", 0),
        "evaluator_false_positive_count": counts.get("evaluator_false_positive", 0) + counts.get("price_evaluator_false_positive", 0),
        "price_mismatch_count": counts.get("price_mismatch_real", 0),
        "source_link_missing_count": counts.get("source_link_missing", 0),
        "missing_field_failure_count": counts.get("missing_field_not_handled", 0),
        "template_needed_count": counts.get("answer_template_needed", 0),
        "recommended_fix_counts": dict(sorted(recommended_counts.items())),
        "ignored_price_counts": dict(sorted(ignored_price_counts.items())),
    }
    return {"summary": summary, "failed_answers": failed}


def print_readable_summary(report: Mapping[str, Any], limit: int = 12) -> None:
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    for row in report["failed_answers"][:limit]:
        print("\n---")
        print(f"{row['id']} | {row['type']} | {row['query']}")
        print(f"failure_types: {', '.join(row['failure_types'])}")
        print(f"recommended_fix: {row['recommended_fix']}")
        print(f"diagnosis: {row['diagnosis']}")
        print(f"answer: {row['answer_excerpt'][:500]}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Analyze failed live answer grounding outputs.")
    parser.add_argument("--answers", required=True)
    parser.add_argument("--eval-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--print-examples", action="store_true")
    args = parser.parse_args(argv)

    report = analyze_failures(args.answers, args.eval_report)
    write_json(report, args.output)
    if args.print_examples:
        print_readable_summary(report)
    else:
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
