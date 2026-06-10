import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .retrievers.text import fold_accents, repair_mojibake


CONTEXT_BLOCK_RE = re.compile(r"^\[(P\d+)\]\s*$", re.MULTILINE)
ANSWER_CITATION_RE = re.compile(r"\[(P\d+)\]")
URL_RE = re.compile(r"https?://[^\s)\]]+")
PRODUCT_WORD_RE = re.compile(
    r"\b(sofa|rèm|rem|kệ|ke|bàn|ban|ghế|ghe|thảm|tham|đèn|den|tủ|tu|giường|giuong|tranh|gương|guong)\b",
    re.IGNORECASE,
)
MISSING_INFO_RE = re.compile(
    r"(chưa thấy|không thấy|chưa có|không có|không có thông tin|không tìm thấy|không đủ|không hỗ trợ|"
    r"dữ liệu hiện có|du lieu hien co|khong co thong tin|khong ho tro)",
    re.IGNORECASE,
)
FORBIDDEN_FIELD_RE = re.compile(
    r"(bảo hành|bao hanh|miễn phí vận chuyển|mien phi van chuyen|giao hàng miễn phí|giao hang mien phi|"
    r"lắp đặt tận nhà|lap dat tan nha|còn hàng|con hang|địa chỉ|dia chi|showroom|tuyển dụng|tuyen dung)",
    re.IGNORECASE,
)
PRICE_RE = re.compile(
    r"\d{1,3}(?:[.,]\d{3})+(?:\s*(?:VND|VNĐ|đ))?"
    r"|\d+(?:[.,]\d+)?\s*(?:triệu|trieu|tr|m|k|nghìn|nghin|VND|VNĐ|đ)\b",
    re.IGNORECASE,
)
AGGREGATE_PRICE_RE = re.compile(
    r"\b(tổng|tong|total|cộng|cong|ước tính|uoc tinh|ước lượng|uoc luong)\b",
    re.IGNORECASE,
)
QUERY_CONSTRAINT_PRICE_RE = re.compile(
    r"\b(dưới|duoi|không quá|khong qua|tối đa|toi da|tầm|tam|tầm giá|tam gia|"
    r"ngân sách|ngan sach|budget|yêu cầu|yeu cau|theo nhu cầu|theo nhu cau|trong tầm|trong tam)\b",
    re.IGNORECASE,
)
APPROXIMATE_OR_RANGE_PRICE_RE = re.compile(
    r"(~|khoảng|khoang|tầm|tam|dao động|dao dong|ước tính|uoc tinh|ước lượng|uoc luong|"
    r"từ\s+\d|tu\s+\d|\d+\s*(?:-|–|đến|den)\s*\d+)",
    re.IGNORECASE,
)


def _clean(value: Any) -> str:
    return repair_mojibake(str(value or "")).strip()


def _norm(value: Any) -> str:
    return fold_accents(_clean(value)).lower()


def _parse_price_to_int(text: str) -> Optional[int]:
    raw = _clean(text)
    if not raw:
        return None
    lowered = _norm(raw)
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(trieu|triệu|tr|m)\b", lowered)
    if match:
        return int(float(match.group(1).replace(",", ".")) * 1_000_000)
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(k|nghin|nghìn)\b", lowered)
    if match:
        return int(float(match.group(1).replace(",", ".")) * 1_000)
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _normalize_url(url: str) -> str:
    return _clean(url).rstrip(".,;:!?")


def _remove_with_ignored(text: str, pattern: re.Pattern, reason: str, ignored: List[Dict[str, Any]]) -> str:
    def replace(match: re.Match) -> str:
        ignored.append({"text": match.group(0), "reason": reason})
        return " "

    return pattern.sub(replace, text)


def _strip_price_noise(answer: str) -> Tuple[str, List[Dict[str, Any]]]:
    ignored: List[Dict[str, Any]] = []
    text = answer or ""
    text = _remove_with_ignored(text, URL_RE, "url", ignored)
    def replace_citation(match: re.Match) -> str:
        ignored.append({"text": match.group(0), "reason": "citation"})
        return " CITATION "

    text = ANSWER_CITATION_RE.sub(replace_citation, text)
    text = _remove_with_ignored(
        text,
        re.compile(
            r"\b\d+(?:[.,]\d+)?\s*(?:x|×)\s*\d+(?:[.,]\d+)?(?:\s*(?:x|×)\s*\d+(?:[.,]\d+)?)?\s*(?:mm|cm|m)?\b",
            re.IGNORECASE,
        ),
        "dimension",
        ignored,
    )
    text = _remove_with_ignored(text, re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:mm|cm)\b", re.IGNORECASE), "dimension", ignored)
    text = _remove_with_ignored(text, re.compile(r"\b[A-Z]{2,6}-?\d{2,}[A-Z0-9-]*\b", re.IGNORECASE), "sku", ignored)
    return text, ignored


def _price_window(text: str, start: int, end: int, before: int = 90, after: int = 50) -> str:
    return text[max(0, start - before): min(len(text), end + after)]


def _line_for_span(text: str, start: int, end: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    return text[line_start:line_end]


def _is_product_specific_price_context(text: str, start: int, end: int) -> bool:
    local_before = text[max(0, start - 70): start]
    has_citation = "CITATION" in local_before
    return bool(has_citation and re.search(r"\b(giá|gia|price)\s*:", _norm(local_before), re.I))


def _search_context(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(_clean(text).lower()) or pattern.search(_norm(text)))


def _is_aggregate_price_context(text: str, start: int, end: int) -> bool:
    return _search_context(AGGREGATE_PRICE_RE, _price_window(text, start, end, after=0))


def _is_query_constraint_price_context(text: str, start: int, end: int) -> bool:
    return _search_context(QUERY_CONSTRAINT_PRICE_RE, _price_window(text, start, end))


def _is_approximate_or_range_price_context(text: str, start: int, end: int) -> bool:
    return _search_context(APPROXIMATE_OR_RANGE_PRICE_RE, _price_window(text, start, end))


def _extract_answer_price_details(answer: str, query: str = "") -> Dict[str, Any]:
    cleaned, ignored = _strip_price_noise(answer)
    detected_prices: Set[int] = set()
    aggregate_prices: Set[int] = set()
    query_constraint_prices: Set[int] = set()
    approximate_or_range_prices: Set[int] = set()
    for match in PRICE_RE.finditer(cleaned):
        value = _parse_price_to_int(match.group(0))
        if value is None or value < 10_000:
            continue
        product_specific = _is_product_specific_price_context(cleaned, match.start(), match.end())
        if not product_specific and _is_aggregate_price_context(cleaned, match.start(), match.end()):
            aggregate_prices.add(value)
        elif not product_specific and _is_query_constraint_price_context(cleaned, match.start(), match.end()):
            query_constraint_prices.add(value)
        elif not product_specific and _is_approximate_or_range_price_context(cleaned, match.start(), match.end()):
            approximate_or_range_prices.add(value)
        else:
            detected_prices.add(value)
    return {
        "detected_prices": sorted(detected_prices),
        "aggregate_prices": sorted(aggregate_prices),
        "query_constraint_prices": sorted(query_constraint_prices),
        "approximate_or_range_prices": sorted(approximate_or_range_prices),
        "ignored_numbers": ignored,
    }


def _extract_answer_prices(answer: str) -> Set[int]:
    return set(_extract_answer_price_details(answer)["detected_prices"])


def extract_context_facts(context: str) -> Dict[str, Any]:
    text = _clean(context)
    facts: Dict[str, Any] = {"products": {}, "documents": {}, "source_urls": set(), "raw": text}
    matches = list(CONTEXT_BLOCK_RE.finditer(text))
    for idx, match in enumerate(matches):
        pid = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        product: Dict[str, Any] = {"pid": pid, "raw": block}
        field_map = {
            "Tên sản phẩm": "product_name",
            "Danh mục": "category",
            "Giá": "price",
            "Giá gốc": "original_price",
            "Chất liệu": "material",
            "Màu sắc": "color",
            "Kích thước": "dimensions",
            "SKU": "sku",
            "Tình trạng": "availability",
            "Link nguồn": "source_url",
        }
        for line in block.splitlines():
            if ":" not in line:
                continue
            label, value = line.split(":", 1)
            key = field_map.get(label.strip())
            if not key:
                continue
            cleaned = _clean(value)
            product[key] = cleaned
            if key in ("price", "original_price"):
                product[f"{key}_value"] = _parse_price_to_int(cleaned)
            if key == "source_url" and cleaned:
                facts["source_urls"].add(_normalize_url(cleaned))
        facts["products"][pid] = product
    return facts


def extract_answer_citations(answer: str) -> Set[str]:
    return set(ANSWER_CITATION_RE.findall(answer or ""))


def _known_product_mentioned(answer: str, products: Dict[str, Dict[str, Any]]) -> bool:
    answer_norm = _norm(answer)
    for product in products.values():
        name = product.get("product_name")
        if name and _norm(name) in answer_norm:
            return True
    return False


def _answer_mentions_product(answer: str, products: Dict[str, Dict[str, Any]]) -> bool:
    return bool(extract_answer_citations(answer)) or _known_product_mentioned(answer, products) or bool(PRODUCT_WORD_RE.search(answer or ""))


def _is_missing_info_fallback(answer: str) -> bool:
    return bool(MISSING_INFO_RE.search(_clean(answer).lower()) or MISSING_INFO_RE.search(_norm(answer)))


def _context_has_field(products: Dict[str, Dict[str, Any]], field_names: Sequence[str]) -> bool:
    return any(product.get(field) for product in products.values() for field in field_names)


def _query_asks_missing_field(query: str) -> bool:
    return bool(FORBIDDEN_FIELD_RE.search(query or ""))


def _answer_fabricates_forbidden_field(query: str, context: str, answer: str, products: Dict[str, Dict[str, Any]]) -> bool:
    if not FORBIDDEN_FIELD_RE.search(answer or ""):
        return False
    context_norm = _norm(context)
    answer_norm = _norm(answer)
    if _is_missing_info_fallback(answer):
        return False
    if "bao hanh" in answer_norm and "bao hanh" not in context_norm:
        return True
    if ("van chuyen" in answer_norm or "giao hang" in answer_norm or "lap dat" in answer_norm) and not re.search(
        r"van chuyen|giao hang|lap dat", context_norm
    ):
        return True
    if ("dia chi" in answer_norm or "showroom" in answer_norm) and not re.search(r"dia chi|showroom", context_norm):
        return True
    if ("tuyen dung" in answer_norm) and "tuyen dung" not in context_norm:
        return True
    if "con hang" in answer_norm and not _context_has_field(products, ["availability"]):
        return True
    return False


def _price_consistency_details(answer: str, products: Dict[str, Dict[str, Any]], query: str = "") -> Dict[str, Any]:
    details = _extract_answer_price_details(answer, query=query)
    answer_prices = set(details["detected_prices"])
    context_prices = sorted({
        product.get("price_value")
        for product in products.values()
        if isinstance(product.get("price_value"), int)
    })
    details["context_prices"] = context_prices
    details["reason"] = "ok"
    details["mismatched_prices"] = []
    if not answer_prices:
        details["consistent"] = True
        ignored_price_kinds = []
        if details["aggregate_prices"]:
            ignored_price_kinds.append("aggregate_price_not_compared_to_product_prices")
        if details["query_constraint_prices"]:
            ignored_price_kinds.append("query_constraint_price_ignored")
        if details["approximate_or_range_prices"]:
            ignored_price_kinds.append("approximate_or_range_price_ignored")
        if ignored_price_kinds:
            details["reason"] = ",".join(ignored_price_kinds)
        return details
    if not context_prices:
        details["consistent"] = False
        details["reason"] = "answer_has_price_but_context_has_no_product_prices"
        details["mismatched_prices"] = sorted(answer_prices)
        return details
    mismatches = sorted(price for price in answer_prices if price not in set(context_prices))
    details["consistent"] = not mismatches
    details["mismatched_prices"] = mismatches
    if mismatches:
        details["reason"] = "answer_price_not_found_in_context_prices"
    return details


def _price_consistency(answer: str, products: Dict[str, Dict[str, Any]]) -> bool:
    return bool(_price_consistency_details(answer, products)["consistent"])


def _is_out_of_scope_or_policy(query_spec: Dict[str, Any]) -> bool:
    query_type = str(query_spec.get("type") or "").lower()
    return query_type.startswith("out_of_scope") or query_type.startswith("policy")


def _has_specific_product_claim(answer: str, products: Dict[str, Dict[str, Any]]) -> bool:
    return bool(extract_answer_citations(answer)) or _known_product_mentioned(answer, products)


def evaluate_answer_grounding(query_spec: Dict[str, Any], context: str, answer: str) -> Dict[str, Any]:
    behavior = query_spec.get("expected_behavior") or {}
    facts = extract_context_facts(context)
    products = facts["products"]
    citations = extract_answer_citations(answer)
    valid_citations = set(products.keys())
    answer_urls = {_normalize_url(url) for url in URL_RE.findall(answer or "")}
    context_urls = {_normalize_url(url) for url in facts["source_urls"]}

    is_out_scope = _is_out_of_scope_or_policy(query_spec)
    mentions_product = _answer_mentions_product(answer, products)
    mentions_specific_product = _has_specific_product_claim(answer, products)
    missing_info_fallback = _is_missing_info_fallback(answer)
    out_scope_valid_fallback = bool(is_out_scope and missing_info_fallback and not mentions_specific_product)
    has_required_citation = True
    if not out_scope_valid_fallback and ((behavior.get("must_have_citation") and not missing_info_fallback) or mentions_specific_product):
        has_required_citation = bool(citations & valid_citations)

    citation_validity = all(citation in valid_citations for citation in citations)
    source_link_presence = True
    if behavior.get("should_include_source_link"):
        source_link_presence = bool(answer_urls & context_urls)

    price_details = _price_consistency_details(answer, products, query_spec.get("query", ""))
    price_consistency = bool(price_details["consistent"])
    product_name_grounded = True
    if mentions_specific_product and not (citations & valid_citations):
        product_name_grounded = bool(missing_info_fallback and not _known_product_mentioned(answer, products))
    elif not out_scope_valid_fallback and PRODUCT_WORD_RE.search(answer or "") and not (citations & valid_citations) and not _known_product_mentioned(answer, products):
        product_name_grounded = bool(missing_info_fallback)

    asks_missing = _query_asks_missing_field(query_spec.get("query", ""))
    missing_field_handling = True
    if asks_missing:
        context_has_forbidden_field = bool(FORBIDDEN_FIELD_RE.search(context or ""))
        if not context_has_forbidden_field:
            missing_field_handling = bool(missing_info_fallback)

    no_forbidden_hallucination = not _answer_fabricates_forbidden_field(
        query_spec.get("query", ""), context, answer, products
    )
    answer_usefulness = bool((answer or "").strip())
    if products and behavior.get("must_have_citation"):
        answer_usefulness = answer_usefulness and (mentions_product or bool(missing_info_fallback))
    if not products:
        answer_usefulness = answer_usefulness and bool(missing_info_fallback)
    if out_scope_valid_fallback:
        answer_usefulness = bool((answer or "").strip())
        product_name_grounded = True

    checks = {
        "has_required_citation": has_required_citation,
        "citation_validity": citation_validity,
        "source_link_presence": source_link_presence,
        "price_consistency": price_consistency,
        "product_name_grounded": product_name_grounded,
        "missing_field_handling": missing_field_handling,
        "no_forbidden_hallucination": no_forbidden_hallucination,
        "answer_usefulness": answer_usefulness,
    }
    return {
        **checks,
        "pass": all(checks.values()),
        "citations": sorted(citations),
        "valid_context_citations": sorted(valid_citations),
        "context_product_count": len(products),
        "context_source_count": len(context_urls),
        "source_link_missing": bool(behavior.get("should_include_source_link") and not source_link_presence),
        "price_details": price_details,
        "failure_reasons": [name for name, ok in checks.items() if not ok],
        "out_of_scope_fallback_valid": out_scope_valid_fallback,
    }
