import json
import math
from collections import Counter
from typing import Any, Dict, List

from .base import BaseRetriever
from .schemas import RetrievalResult
from .text import fold_accents, tokenize


NOISE_MARKERS = (
    "ho tro khach hang",
    "doi tra - bao hanh",
    "hinh thuc thanh toan",
    "van chuyen - giao nhan",
    "map showroom",
    "showroom caco",
    "dang ky tu van mien phi",
    "cam ket bao mat thong tin",
    "tim kiem san pham",
    "menu",
    "checkout",
    "social :",
)
POLICY_MARKERS = (
    "chinh sach",
    "thanh toan",
    "giao hang",
    "doi tra",
    "bao hanh",
    "dieu khoan",
)
PRODUCT_MARKERS = (
    "sofa",
    "bo ban ghe sofa",
    "phong khach",
    "salon go",
    "sofa go",
    "sofa da",
    "collections",
    "concept",
    "danh muc",
)
COMPACT_QUERY_MARKERS = (
    "can ho nho",
    "chung cu nho",
    "phong khach nho",
)
COMPACT_STYLE_MARKERS = (
    "gon",
    "nho",
    "toi gian",
    "tiet kiem dien tich",
)
DESIGN_MARKERS = (
    "thiet ke",
    "thi cong",
    "phong cach",
    "hien dai",
    "toi gian",
    "chung cu",
)
PAYMENT_MARKERS = (
    "thanh toan",
    "tra gop",
    "dat coc",
)
DELIVERY_MARKERS = (
    "giao hang",
    "van chuyen",
    "giao nhan",
)
RETURN_MARKERS = (
    "doi tra",
    "kiem hang",
    "bao hanh",
)
ABOUT_MARKERS = (
    "gioi thieu",
    "ve chung toi",
    "noi that caco la don vi",
)


class BaselineRetriever(BaseRetriever):
    def __init__(self, chunks_jsonl: str, index_json: str, use_heuristics: bool = True):
        self.use_heuristics = use_heuristics
        self.chunks: List[Dict[str, Any]] = []
        self.chunk_content_frequencies: List[Counter[str]] = []
        self.chunk_title_frequencies: List[Counter[str]] = []
        self.chunk_url_frequencies: List[Counter[str]] = []
        self.chunk_profiles: List[Dict[str, Any]] = []
        with open(chunks_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                self.chunks.append(chunk)
                title = (chunk.get("title") or "").strip()
                content = (chunk.get("content") or "").strip()
                url = (chunk.get("url") or "").strip()

                title_tokens = tokenize(title)
                content_tokens = tokenize(content)
                url_tokens = tokenize(url.replace("/", " ").replace("-", " ").replace("_", " "))

                self.chunk_title_frequencies.append(Counter(title_tokens))
                self.chunk_content_frequencies.append(Counter(content_tokens))
                self.chunk_url_frequencies.append(Counter(url_tokens))
                self.chunk_profiles.append(self._build_chunk_profile(title, content, url, content_tokens))
        with open(index_json, "r", encoding="utf-8") as f:
            self.index = json.load(f)

    def search(self, query: str, k: int = 4) -> List[RetrievalResult]:
        query_terms = Counter(tokenize(query))
        idf = self.index["idf"]
        scored: List[RetrievalResult] = []
        query_profile = self._build_query_profile(query)

        for idx, chunk in enumerate(self.chunks):
            content_frequencies = self.chunk_content_frequencies[idx]
            title_frequencies = self.chunk_title_frequencies[idx]
            url_frequencies = self.chunk_url_frequencies[idx]
            profile = self.chunk_profiles[idx]

            score = self._base_score(query_terms, content_frequencies, title_frequencies, url_frequencies, idf)

            if score <= 0:
                continue

            score = self._apply_heuristics(score, query_profile, profile)

            if score > 0:
                scored.append(
                    RetrievalResult.from_hit(
                        {**chunk, "score": score},
                        idx=idx,
                    )
                )

        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:k]

    def _base_score(
        self,
        query_terms: Counter[str],
        content_frequencies: Counter[str],
        title_frequencies: Counter[str],
        url_frequencies: Counter[str],
        idf: Dict[str, float],
    ) -> float:
        score = self._score_terms(query_terms, content_frequencies, idf)

        if self.use_heuristics:
            score += 2.4 * self._score_terms(query_terms, title_frequencies, idf)
            score += 1.6 * self._score_terms(query_terms, url_frequencies, idf)
        else:
            score += self._score_terms(query_terms, title_frequencies, idf)
            score += self._score_terms(query_terms, url_frequencies, idf)

        return score

    def _apply_heuristics(
        self,
        score: float,
        query_profile: Dict[str, bool],
        chunk_profile: Dict[str, Any],
    ) -> float:
        if not self.use_heuristics:
            return score

        score *= self._length_factor(chunk_profile["content_token_count"])
        score *= self._noise_factor(chunk_profile["noise_hits"])
        score *= self._intent_factor(query_profile, chunk_profile)
        return score

    def _build_chunk_profile(
        self,
        title: str,
        content: str,
        url: str,
        content_tokens: List[str],
    ) -> Dict[str, Any]:
        title_folded = fold_accents(title.lower())
        content_folded = fold_accents(content.lower())
        url_folded = fold_accents(url.lower())
        combined = " ".join([title_folded, url_folded, content_folded])

        noise_hits = sum(1 for marker in NOISE_MARKERS if marker in content_folded)
        is_policy = any(marker in combined for marker in POLICY_MARKERS) or "/page/" in url_folded
        is_product = any(marker in combined for marker in PRODUCT_MARKERS)

        return {
            "content_token_count": len(content_tokens),
            "noise_hits": noise_hits,
            "is_policy": is_policy,
            "is_product": is_product,
            "is_about": any(marker in combined for marker in ABOUT_MARKERS),
            "matches_compact": any(marker in combined for marker in COMPACT_QUERY_MARKERS) or (
                "sofa" in combined and any(marker in combined for marker in COMPACT_STYLE_MARKERS)
            ),
            "matches_design": any(marker in combined for marker in DESIGN_MARKERS),
            "matches_payment": any(marker in combined for marker in PAYMENT_MARKERS),
            "matches_delivery": any(marker in combined for marker in DELIVERY_MARKERS),
            "matches_return": any(marker in combined for marker in RETURN_MARKERS),
        }

    def _build_query_profile(self, query: str) -> Dict[str, bool]:
        query_folded = fold_accents((query or "").lower())
        has_compact_phrase = any(marker in query_folded for marker in COMPACT_QUERY_MARKERS)
        has_sofa = "sofa" in query_folded
        return {
            "has_policy_intent": "chinh sach" in query_folded,
            "has_sofa_intent": has_sofa,
            "has_compact_intent": has_compact_phrase or (
                has_sofa and any(marker in query_folded for marker in ("gon", "nho", "chung cu", "can ho"))
            ),
            "has_design_intent": any(marker in query_folded for marker in ("thiet ke", "phong cach", "hien dai", "chung cu")),
            "has_payment_intent": any(marker in query_folded for marker in PAYMENT_MARKERS),
            "has_delivery_intent": any(marker in query_folded for marker in DELIVERY_MARKERS),
            "has_return_intent": any(marker in query_folded for marker in RETURN_MARKERS),
        }

    def _score_terms(
        self,
        query_terms: Counter[str],
        term_frequencies: Counter[str],
        idf: Dict[str, float],
    ) -> float:
        score = 0.0
        for term, query_count in query_terms.items():
            term_frequency = term_frequencies.get(term, 0)
            if term_frequency <= 0:
                continue
            tf_weight = 1.0 + math.log1p(term_frequency)
            score += tf_weight * query_count * idf.get(term, 0.0)
        return score

    def _length_factor(self, content_token_count: int) -> float:
        if content_token_count <= 80:
            return 1.12
        if content_token_count <= 180:
            return 1.0
        overflow = content_token_count - 180
        return max(0.62, 1.0 - min(0.38, overflow / 900.0))

    def _noise_factor(self, noise_hits: int) -> float:
        if noise_hits <= 0:
            return 1.0
        return max(0.55, 1.0 - (0.08 * noise_hits))

    def _intent_factor(self, query_profile: Dict[str, bool], chunk_profile: Dict[str, Any]) -> float:
        factor = 1.0
        if query_profile["has_policy_intent"]:
            if chunk_profile["is_policy"]:
                factor *= 1.35
            elif chunk_profile["is_product"]:
                factor *= 0.9
        if query_profile["has_sofa_intent"]:
            if chunk_profile["is_product"]:
                factor *= 1.2
            if chunk_profile["is_policy"]:
                factor *= 0.85
        if query_profile["has_compact_intent"]:
            if chunk_profile["matches_compact"]:
                factor *= 1.3
            elif chunk_profile["is_product"]:
                factor *= 1.08
            if chunk_profile["is_about"]:
                factor *= 0.82
        if query_profile["has_design_intent"]:
            if chunk_profile["matches_design"]:
                factor *= 1.26
            elif chunk_profile["is_about"]:
                factor *= 0.92
        if query_profile["has_payment_intent"]:
            if chunk_profile["matches_payment"]:
                factor *= 1.35
            elif chunk_profile["matches_return"] or chunk_profile["matches_delivery"]:
                factor *= 0.92
        if query_profile["has_delivery_intent"]:
            if chunk_profile["matches_delivery"]:
                factor *= 1.38
            elif chunk_profile["matches_return"] or chunk_profile["matches_payment"]:
                factor *= 0.9
        if query_profile["has_return_intent"]:
            if chunk_profile["matches_return"]:
                factor *= 1.38
            elif chunk_profile["matches_payment"] or chunk_profile["matches_delivery"]:
                factor *= 0.9
        return factor
