import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from .retrievers.base import BaseRetriever
from .retrievers.baseline import BaselineRetriever
from .retrievers.hybrid import HybridRetriever
from .retrievers.hybrid_rerank import HybridRerankRetriever
from .retrievers.schemas import RetrievalResult
from .retrievers.text import fold_accents
from .context_packing import format_grounded_context
from .product_filters import (
    apply_price_constraint,
    diversify_by_category,
    parse_price_constraint,
    parse_product_categories,
)
from .product_reranker import is_complex_product_query, rerank_product_results


PRODUCT_HINTS = [
    "model", "sku", "sectional", "abisko", "article", "castlery",
    "ma", "ma san pham", "ma hang",
]
POLICY_OR_COMPARE_HINTS = [
    "thanh toan", "chinh sach", "giao hang", "doi tra", "bao hanh",
    "payment", "policy", "delivery", "return", "refund",
    "so sanh", "vs", "chat lieu", "vai", "da", "go", "ni",
    "compare", "material", "fabric", "leather", "wood",
]


def normalize_retrieval_mode(mode: Optional[str], use_heuristics: bool = True) -> str:
    mode_value = (mode or "").strip().lower()
    if mode_value in ("", "improved"):
        return "keyword" if use_heuristics else "baseline"
    if mode_value in ("keyword", "baseline", "vector", "hybrid", "hybrid_rerank"):
        return mode_value
    raise ValueError(f"Unsupported retrieval mode: {mode}")


def load_kb(
    kb_dir: Optional[str],
    use_heuristics: bool = True,
    mode: Optional[str] = None,
) -> Optional[BaseRetriever]:
    if not kb_dir:
        return None

    chunks_path = os.path.join(kb_dir, "chunks.jsonl")
    index_path = os.path.join(kb_dir, "index.json")
    normalized_mode = normalize_retrieval_mode(mode, use_heuristics=use_heuristics)

    if normalized_mode == "vector":
        from .retrievers.vector import VectorRetriever

        return VectorRetriever(chunks_path)

    if normalized_mode == "hybrid":
        from .retrievers.vector import VectorRetriever

        return HybridRetriever(
            keyword_retriever=BaselineRetriever(chunks_path, index_path, use_heuristics=True),
            vector_retriever=VectorRetriever(chunks_path),
        )

    if normalized_mode == "hybrid_rerank":
        from .retrievers.vector import VectorRetriever

        return HybridRerankRetriever(
            hybrid_retriever=HybridRetriever(
                keyword_retriever=BaselineRetriever(chunks_path, index_path, use_heuristics=True),
                vector_retriever=VectorRetriever(chunks_path),
            )
        )

    return BaselineRetriever(
        chunks_path,
        index_path,
        use_heuristics=(normalized_mode == "keyword"),
    )


def should_allow_retrieval(message: str, stage: str, slots: Dict[str, Any]) -> bool:
    msg_raw = message or ""
    msg_low = msg_raw.lower()
    msg_folded = fold_accents(msg_low)
    words = [w for w in msg_raw.split() if w]

    has_link = bool(re.search(r"https?://|www\.", msg_raw, re.I))
    has_product_code = bool(re.search(r"\b[A-Z]{2,}\d{2,}\b", msg_raw, re.I))
    mentions_specific = has_product_code or (
        (len(words) >= 6) and any(
            hint in msg_low or fold_accents(hint) in msg_folded
            for hint in PRODUCT_HINTS
        )
    )
    asks_policy_or_compare = any(
        hint in msg_low or fold_accents(hint) in msg_folded
        for hint in POLICY_OR_COMPARE_HINTS
    )
    slot_count = len(slots or {})

    allow_rag = (
        has_link
        or mentions_specific
        or asks_policy_or_compare
        or stage in ("propose", "close")
        or slot_count >= 2
    )

    if stage == "discover" and not (has_link or mentions_specific or asks_policy_or_compare) and slot_count < 2:
        allow_rag = False

    return allow_rag


def normalize_hits(
    raw_hits: Iterable[Union[Dict[str, Any], RetrievalResult]],
    tenant_id: Optional[str] = None,
) -> List[RetrievalResult]:
    normalized = []
    for idx, hit in enumerate(raw_hits):
        if isinstance(hit, RetrievalResult):
            normalized.append(
                hit if tenant_id is None else hit.model_copy(update={"tenant_id": tenant_id})
            )
            continue
        normalized.append(RetrievalResult.from_hit(hit, idx=idx, tenant_id=tenant_id))
    return normalized


def _hit_metadata(hit: Union[Dict[str, Any], RetrievalResult]) -> Dict[str, Any]:
    metadata = hit.get("metadata") if isinstance(hit, dict) else hit.metadata
    return metadata if isinstance(metadata, dict) else {}


def _is_product_hit(hit: Union[Dict[str, Any], RetrievalResult]) -> bool:
    return _hit_metadata(hit).get("doc_type") == "product"


def _has_price_in_range(hit: Union[Dict[str, Any], RetrievalResult], constraint: Any) -> bool:
    price = _hit_metadata(hit).get("price")
    if price in (None, ""):
        return False
    try:
        numeric_price = float(price)
    except (TypeError, ValueError):
        return False
    if constraint.min_price is not None and numeric_price < constraint.min_price:
        return False
    if constraint.max_price is not None and numeric_price > constraint.max_price:
        return False
    return True


def _apply_product_price_constraint(
    raw_hits: List[Union[Dict[str, Any], RetrievalResult]],
    constraint: Any,
) -> List[Union[Dict[str, Any], RetrievalResult]]:
    product_hits = [hit for hit in raw_hits if _is_product_hit(hit)]
    if not product_hits:
        return raw_hits

    has_range_filter = constraint.min_price is not None or constraint.max_price is not None
    if has_range_filter and not any(_has_price_in_range(hit, constraint) for hit in product_hits):
        return raw_hits

    non_product_hits = [hit for hit in raw_hits if not _is_product_hit(hit)]
    filtered_products = apply_price_constraint(product_hits, constraint)
    return filtered_products + non_product_hits


def _diversify_product_categories(
    raw_hits: List[Union[Dict[str, Any], RetrievalResult]],
    categories: List[str],
    k: int,
) -> List[Union[Dict[str, Any], RetrievalResult]]:
    product_hits = [hit for hit in raw_hits if _is_product_hit(hit)]
    if not product_hits:
        return raw_hits

    non_product_hits = [hit for hit in raw_hits if not _is_product_hit(hit)]
    diversified_products = diversify_by_category(product_hits, categories, k)
    return diversified_products + non_product_hits


def search_hits(kb: Optional[BaseRetriever], query: str, k: int = 4, tenant_id: Optional[str] = None) -> List[RetrievalResult]:
    if kb is None:
        return []

    constraint = parse_price_constraint(query)
    categories = parse_product_categories(query)
    should_expand = constraint.has_constraint() or len(categories) >= 2
    should_rerank = is_complex_product_query(query)
    if not should_expand:
        if not should_rerank:
            return normalize_hits(kb.search(query, k=k), tenant_id=tenant_id)
        raw_hits = list(kb.search(query, k=max(k * 10, 200)))
        reranked_hits = rerank_product_results(raw_hits, query, k)
        return normalize_hits(reranked_hits, tenant_id=tenant_id)

    internal_k = max(k * 10, 200) if should_rerank else max(k * 5, 20)
    raw_hits = list(kb.search(query, k=internal_k))
    if should_rerank:
        reranked_hits = rerank_product_results(raw_hits, query, k)
        return normalize_hits(reranked_hits, tenant_id=tenant_id)

    filtered_hits = raw_hits
    if constraint.has_constraint():
        filtered_hits = _apply_product_price_constraint(filtered_hits, constraint)
    if len(categories) >= 2:
        filtered_hits = _diversify_product_categories(filtered_hits, categories, k)
    return normalize_hits(filtered_hits[:k], tenant_id=tenant_id)


def format_context(hits: List[RetrievalResult], max_chars: int = 900) -> str:
    return format_grounded_context(hits, max_products=5, max_chars_per_product=max_chars)


def summarize_retrieval_debug(
    hits: List[RetrievalResult],
    context: str,
    max_scores: int = 4,
    max_snippets: int = 2,
    snippet_chars: int = 160,
) -> Dict[str, Any]:
    snippets: List[str] = []
    for hit in hits[:max_snippets]:
        block = format_grounded_context([hit], max_products=1, max_chars_per_product=snippet_chars).strip()
        if block:
            snippets.append(block)

    return {
        "retrieved_docs": len(hits),
        "top_scores": [round(hit.score, 4) for hit in hits[:max_scores]],
        "selected_context_snippets": snippets,
        "context_chars": len(context),
    }


def top_similar_items(hits: List[RetrievalResult], limit: int = 3) -> List[Tuple[str, str]]:
    seen = set()
    items: List[Tuple[str, str]] = []

    for hit in hits:
        title = hit.title.strip()
        source = hit.source.strip()
        if title and title not in seen:
            seen.add(title)
            items.append((title, source))
        if len(items) >= limit:
            break

    return items
