import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from .retrievers.base import BaseRetriever
from .retrievers.baseline import BaselineRetriever
from .retrievers.hybrid import HybridRetriever
from .retrievers.hybrid_rerank import HybridRerankRetriever
from .retrievers.schemas import RetrievalResult
from .retrievers.text import fold_accents


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


def search_hits(kb: Optional[BaseRetriever], query: str, k: int = 4, tenant_id: Optional[str] = None) -> List[RetrievalResult]:
    if kb is None:
        return []
    return normalize_hits(kb.search(query, k=k), tenant_id=tenant_id)


def format_context(hits: List[RetrievalResult], max_chars: int = 900) -> str:
    ctx_blocks = []
    for hit in hits:
        context_block = hit.to_context_block(max_chars=max_chars)
        if context_block:
            ctx_blocks.append(context_block)
    return "\n".join(ctx_blocks)


def summarize_retrieval_debug(
    hits: List[RetrievalResult],
    context: str,
    max_scores: int = 4,
    max_snippets: int = 2,
    snippet_chars: int = 160,
) -> Dict[str, Any]:
    snippets: List[str] = []
    for hit in hits[:max_snippets]:
        block = hit.to_context_block(max_chars=snippet_chars).strip()
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
