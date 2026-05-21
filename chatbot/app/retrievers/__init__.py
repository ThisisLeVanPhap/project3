from .base import BaseRetriever
from .baseline import BaselineRetriever
from .hybrid import HybridRetriever
from .hybrid_rerank import HybridRerankRetriever
from .schemas import RetrievalResult
from .text import fold_accents, tokenize

__all__ = ["BaseRetriever", "BaselineRetriever", "HybridRetriever", "HybridRerankRetriever", "VectorRetriever", "RetrievalResult", "fold_accents", "tokenize"]


def __getattr__(name):
    if name == "VectorRetriever":
        from .vector import VectorRetriever

        return VectorRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
