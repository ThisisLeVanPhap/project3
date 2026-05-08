from typing import List

from .base import BaseRetriever
from .schemas import RetrievalResult
from .text import fold_accents, tokenize


class HybridRerankRetriever(BaseRetriever):
    def __init__(self, hybrid_retriever: BaseRetriever, candidate_pool: int = 10):
        self.hybrid_retriever = hybrid_retriever
        self.candidate_pool = candidate_pool

    def search(self, query: str, k: int = 4) -> List[RetrievalResult]:
        pool_size = max(k, self.candidate_pool)
        candidates = self.hybrid_retriever.search(query, k=pool_size)
        if not candidates:
            return []

        query_text = fold_accents((query or "").lower()).strip()
        query_tokens = tokenize(query)
        query_token_set = set(query_tokens)

        reranked: List[RetrievalResult] = []
        for hit in candidates:
            rerank_score = self._rerank_score(hit, query_text, query_token_set)
            reranked.append(hit.model_copy(update={"score": rerank_score}))

        reranked.sort(key=lambda hit: hit.score, reverse=True)
        return reranked[:k]

    def _rerank_score(
        self,
        hit: RetrievalResult,
        query_text: str,
        query_token_set: set[str],
    ) -> float:
        title_text = fold_accents(hit.title.lower())
        source_text = fold_accents(hit.source.lower())
        body_text = fold_accents(hit.text.lower())

        title_tokens = set(tokenize(hit.title))
        body_tokens = set(tokenize(hit.text))
        source_tokens = set(tokenize(hit.source))

        coverage = self._overlap_ratio(query_token_set, title_tokens | body_tokens | source_tokens)
        title_overlap = self._overlap_ratio(query_token_set, title_tokens)
        source_overlap = self._overlap_ratio(query_token_set, source_tokens)

        exact_title_phrase = 1.0 if query_text and query_text in title_text else 0.0
        exact_source_phrase = 1.0 if query_text and query_text in source_text else 0.0
        exact_body_phrase = 1.0 if query_text and query_text in body_text else 0.0

        return (
            0.45 * hit.score
            + 0.30 * coverage
            + 0.15 * title_overlap
            + 0.05 * source_overlap
            + 0.08 * exact_title_phrase
            + 0.04 * exact_source_phrase
            + 0.03 * exact_body_phrase
        )

    def _overlap_ratio(self, query_tokens: set[str], candidate_tokens: set[str]) -> float:
        if not query_tokens or not candidate_tokens:
            return 0.0
        return len(query_tokens & candidate_tokens) / len(query_tokens)
