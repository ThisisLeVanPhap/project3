from abc import ABC, abstractmethod
from typing import List

from .schemas import RetrievalResult


class BaseRetriever(ABC):
    @abstractmethod
    def search(self, query: str, k: int = 4) -> List[RetrievalResult]:
        """Return ranked retrieval results for a query."""
