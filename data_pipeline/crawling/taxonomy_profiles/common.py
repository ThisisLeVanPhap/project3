from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TaxonomyDecision:
    category: str | None
    rule: str | None
    confidence: float = 0.0


def no_decision(product: dict[str, Any]) -> TaxonomyDecision:
    return TaxonomyDecision(None, None, 0.0)
