from abc import ABC, abstractmethod
from typing import Optional

from data_pipeline.crawling.schema import ProductObservation


class BaseProductExtractor(ABC):
    """Base interface for product extractors that parse already-fetched HTML."""

    @abstractmethod
    def extract(
        self,
        html: str,
        source_url: str,
        tenant_id: Optional[str] = None,
    ) -> list[ProductObservation]:
        raise NotImplementedError
