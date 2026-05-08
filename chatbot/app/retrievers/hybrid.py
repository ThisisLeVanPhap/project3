from typing import Dict, List

from .base import BaseRetriever
from .schemas import RetrievalResult


class HybridRetriever(BaseRetriever):
    def __init__(
        self,
        keyword_retriever: BaseRetriever,
        vector_retriever: BaseRetriever,
        keyword_weight: float = 0.65,
        vector_weight: float = 0.35,
    ):
        self.keyword_retriever = keyword_retriever
        self.vector_retriever = vector_retriever
        self.keyword_weight = keyword_weight
        self.vector_weight = vector_weight

    def search(self, query: str, k: int = 4) -> List[RetrievalResult]:
        candidate_limit = max(k * 3, 10)
        keyword_hits = self.keyword_retriever.search(query, k=candidate_limit)
        vector_hits = self.vector_retriever.search(query, k=candidate_limit)

        combined: Dict[str, RetrievalResult] = {}

        self._merge_hits(combined, keyword_hits, self.keyword_weight)
        self._merge_hits(combined, vector_hits, self.vector_weight)

        ranked = sorted(combined.values(), key=lambda hit: hit.score, reverse=True)
        return ranked[:k]

    def _merge_hits(
        self,
        combined: Dict[str, RetrievalResult],
        hits: List[RetrievalResult],
        weight: float,
    ) -> None:
        if not hits:
            return

        top_score = max(hit.score for hit in hits) or 1.0
        for hit in hits:
            key = self._hit_key(hit)
            normalized_score = max(0.0, hit.score) / top_score
            weighted_score = weight * normalized_score

            if key not in combined:
                combined[key] = hit.model_copy(update={"score": weighted_score})
                continue

            existing = combined[key]
            combined[key] = existing.model_copy(update={"score": existing.score + weighted_score})

    def _hit_key(self, hit: RetrievalResult) -> str:
        for value in (hit.source, hit.doc_id, hit.chunk_id, hit.title):
            if value.strip():
                return value.strip().lower()
        return f"hit:{id(hit)}"
