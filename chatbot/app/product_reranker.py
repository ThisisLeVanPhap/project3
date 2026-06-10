from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypeVar

from .product_filters import PriceConstraint, parse_price_constraint, parse_product_categories
from .retrievers.schemas import RetrievalResult
from .retrievers.text import fold_accents, repair_mojibake


T = TypeVar("T")


MATERIAL_TERMS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("go soi", ("go soi", "oak")),
    ("go cong nghiep", ("go cong nghiep", "mdf", "mfc", "hdf")),
    ("go tu nhien", ("go tu nhien",)),
    ("go", ("go", "wood")),
    ("da", ("da", "leather")),
    ("ni", ("ni", "vai ni", "fabric")),
    ("mdf", ("mdf",)),
    ("kinh", ("kinh", "glass")),
)

ROOM_STYLE_TERMS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("phong khach", ("phong khach", "living room")),
    ("phong ngu", ("phong ngu", "bedroom")),
    ("phong an", ("phong an", "dining room")),
    ("tre em", ("tre em", "be", "kid")),
    ("toi gian", ("toi gian", "minimal")),
    ("hien dai", ("hien dai", "modern")),
    ("decor", ("decor", "do decor")),
    ("trang tri", ("trang tri", "decoration")),
    ("nho gon", ("nho gon", "compact")),
    ("can ho", ("can ho", "chung cu", "apartment")),
)

ROOM_STYLE_CATEGORY_HINTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("phong khach", ("Sofa", "Bàn trà", "Kệ", "Đồ trang trí", "Đèn", "Thảm", "Tranh")),
    ("phong ngu", ("Giường", "Tủ", "Đèn", "Rèm")),
    ("phong an", ("Bàn ăn", "Ghế", "Đèn")),
    ("decor", ("Đồ trang trí", "Đèn", "Gương", "Tranh")),
    ("trang tri", ("Đồ trang trí", "Đèn", "Thảm", "Tranh")),
    ("toi gian", ("Sofa", "Bàn trà", "Kệ", "Bàn ăn")),
)


@dataclass(frozen=True)
class ProductQueryAnalysis:
    price: PriceConstraint
    categories: List[str]
    materials: List[str]
    room_style_terms: List[str]
    inferred_categories: List[str]

    @property
    def has_complex_intent(self) -> bool:
        return (
            self.price.has_constraint()
            or len(self.categories) >= 2
            or bool(self.materials)
            or bool(self.room_style_terms)
        )


def _normalize(value: Any) -> str:
    return fold_accents(repair_mojibake(str(value or ""))).lower().strip()


def _display(value: Any) -> str:
    return repair_mojibake(str(value or "")).strip()


def _contains_any(text: str, patterns: Sequence[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def analyze_product_query(query: str) -> ProductQueryAnalysis:
    normalized = _normalize(query)
    materials = [
        material for material, patterns in MATERIAL_TERMS
        if _contains_any(normalized, patterns)
    ]
    room_style_terms = [
        term for term, patterns in ROOM_STYLE_TERMS
        if _contains_any(normalized, patterns)
    ]

    inferred_categories: List[str] = []
    seen = set()
    for term, categories in ROOM_STYLE_CATEGORY_HINTS:
        if term not in room_style_terms:
            continue
        for category in categories:
            category_key = _normalize(category)
            if category_key in seen:
                continue
            inferred_categories.append(category)
            seen.add(category_key)

    return ProductQueryAnalysis(
        price=parse_price_constraint(query),
        categories=parse_product_categories(query),
        materials=materials,
        room_style_terms=room_style_terms,
        inferred_categories=inferred_categories,
    )


def is_complex_product_query(query: str) -> bool:
    return analyze_product_query(query).has_complex_intent


def _metadata(result: Any) -> Dict[str, Any]:
    if isinstance(result, RetrievalResult):
        metadata = result.metadata
    elif isinstance(result, dict):
        metadata = result.get("metadata") or {}
    else:
        metadata = getattr(result, "metadata", {}) or {}
    return metadata if isinstance(metadata, dict) else {}


def _score(result: Any) -> float:
    if isinstance(result, RetrievalResult):
        return float(result.score or 0.0)
    if isinstance(result, dict):
        return float(result.get("score") or 0.0)
    return float(getattr(result, "score", 0.0) or 0.0)


def _title(result: Any) -> str:
    if isinstance(result, RetrievalResult):
        return result.title
    if isinstance(result, dict):
        return result.get("title") or ""
    return getattr(result, "title", "") or ""


def _text(result: Any) -> str:
    if isinstance(result, RetrievalResult):
        return result.text
    if isinstance(result, dict):
        return result.get("text") or result.get("content") or ""
    return getattr(result, "text", "") or ""


def _source(result: Any) -> str:
    if isinstance(result, RetrievalResult):
        return result.source
    if isinstance(result, dict):
        return result.get("source") or result.get("url") or ""
    return getattr(result, "source", "") or ""


def _is_product(result: Any) -> bool:
    return _normalize(_metadata(result).get("doc_type")) == "product"


def _category(result: Any) -> str:
    return _display(_metadata(result).get("category"))


def _price(result: Any) -> Optional[float]:
    value = _metadata(result).get("price")
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _url(result: Any) -> str:
    metadata = _metadata(result)
    return _normalize(
        metadata.get("canonical_url")
        or metadata.get("source_url")
        or metadata.get("url")
        or _source(result)
    )


def _combined_text(result: Any) -> str:
    metadata = _metadata(result)
    parts = [
        _title(result),
        _text(result),
        _source(result),
        metadata.get("product_name"),
        metadata.get("category"),
        metadata.get("material"),
        metadata.get("color"),
        metadata.get("brand"),
    ]
    return _normalize(" ".join(_display(part) for part in parts if part not in (None, "")))


def _category_matches(actual: str, expected: str) -> bool:
    actual_norm = _normalize(actual)
    expected_norm = _normalize(expected)
    return bool(actual_norm and expected_norm) and (
        actual_norm == expected_norm
        or actual_norm in expected_norm
        or expected_norm in actual_norm
    )


def _matches_any_category(result: Any, categories: Sequence[str]) -> bool:
    return any(_category_matches(_category(result), category) for category in categories)


def _price_in_range(price: Optional[float], constraint: PriceConstraint) -> bool:
    if price is None:
        return False
    if constraint.min_price is not None and price < constraint.min_price:
        return False
    if constraint.max_price is not None and price > constraint.max_price:
        return False
    return True


def _has_range_constraint(constraint: PriceConstraint) -> bool:
    return constraint.min_price is not None or constraint.max_price is not None


def _product_score(
    result: Any,
    rank_idx: int,
    pool_size: int,
    analysis: ProductQueryAnalysis,
    has_price_match: bool,
    seen_urls: Dict[str, int],
) -> float:
    score = (_score(result) * 0.02) + ((pool_size - rank_idx) / max(pool_size, 1))
    text = _combined_text(result)
    price = _price(result)

    if analysis.categories and _matches_any_category(result, analysis.categories):
        score += 6.0
    elif analysis.categories:
        score -= 1.0

    if analysis.inferred_categories and _matches_any_category(result, analysis.inferred_categories):
        score += 2.4

    if analysis.price.has_constraint():
        if _has_range_constraint(analysis.price):
            if _price_in_range(price, analysis.price):
                score += 8.0
            elif has_price_match:
                score -= 8.0
        if analysis.price.target_price is not None and price is not None:
            distance = abs(price - analysis.price.target_price)
            score += max(0.0, 3.0 - (distance / max(analysis.price.target_price, 1)) * 3.0)
        if analysis.price.sort == "asc" and price is not None:
            score += max(0.0, 2.0 - (price / 10_000_000))
        elif analysis.price.sort == "desc" and price is not None:
            score += min(2.0, price / 10_000_000)

    for material in analysis.materials:
        if material in text:
            score += 6.0

    for term in analysis.room_style_terms:
        if term in text:
            score += 1.4

    url = _url(result)
    if url and seen_urls.get(url, 0) > 0:
        score -= 3.0 * seen_urls[url]

    return score


def _coverage_order(scored: List[Tuple[float, int, T]], categories: Sequence[str], k: int) -> List[Tuple[float, int, T]]:
    if len(categories) < 2 or k <= 0:
        return scored

    selected_indexes = set()
    ordered: List[Tuple[float, int, T]] = []
    for category in categories:
        for idx, item in enumerate(scored):
            if idx in selected_indexes:
                continue
            if _category_matches(_category(item[2]), category):
                ordered.append(item)
                selected_indexes.add(idx)
                break
        if len(ordered) >= k:
            return ordered

    for idx, item in enumerate(scored):
        if idx in selected_indexes:
            continue
        ordered.append(item)
        selected_indexes.add(idx)
        if len(ordered) >= k:
            break
    return ordered


def rerank_product_results(results: Sequence[T], query: str, k: int) -> List[T]:
    original = list(results)
    if k <= 0 or not original:
        return []

    analysis = analyze_product_query(query)
    product_hits = [hit for hit in original if _is_product(hit)]
    non_product_hits = [hit for hit in original if not _is_product(hit)]
    if not product_hits:
        return original[:k]

    has_price_match = False
    if analysis.price.has_constraint() and _has_range_constraint(analysis.price):
        has_price_match = any(_price_in_range(_price(hit), analysis.price) for hit in product_hits)
    if has_price_match:
        product_hits = [hit for hit in product_hits if _price_in_range(_price(hit), analysis.price)]

    seen_urls: Dict[str, int] = {}
    scored: List[Tuple[float, int, T]] = []
    pool_size = len(product_hits)
    for idx, hit in enumerate(product_hits):
        rerank_score = _product_score(hit, idx, pool_size, analysis, has_price_match, seen_urls)
        url = _url(hit)
        if url:
            seen_urls[url] = seen_urls.get(url, 0) + 1
        scored.append((rerank_score, idx, hit))

    scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    coverage_categories = analysis.categories if len(analysis.categories) >= 2 else []
    if not coverage_categories and len(analysis.inferred_categories) >= 2:
        coverage_categories = analysis.inferred_categories
    ordered_products = [item[2] for item in _coverage_order(scored, coverage_categories, k)]

    return (ordered_products + non_product_hits)[:k]
