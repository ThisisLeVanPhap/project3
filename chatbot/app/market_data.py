import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


TRUE_VALUES = {"1", "true", "yes", "on"}
DEFAULT_MOCK_PRICE_PATH = Path(__file__).resolve().parent / "data" / "mock_market_prices.demo.json"


@dataclass
class CatalogCandidate:
    product_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    source: Optional[str] = None
    material: Optional[str] = None
    dimensions: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PriceReference:
    product_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    source: Optional[str] = None
    provider: Optional[str] = None
    is_mock: bool = False
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_json_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []

    if path.suffix.lower() == ".jsonl":
        records = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append(value)
        return records

    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        if isinstance(value.get("records"), list):
            return [item for item in value["records"] if isinstance(item, dict)]
        if isinstance(value.get("items"), list):
            return [item for item in value["items"] if isinstance(item, dict)]
        if isinstance(value.get("references"), list):
            return [item for item in value["references"] if isinstance(item, dict)]
    return []


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_À-ỹ]+", text or "") if len(token) >= 2}


def _score_record(query_tokens: set[str], record: Dict[str, Any]) -> int:
    haystack = " ".join(
        str(value)
        for value in record.values()
        if value is not None and not isinstance(value, (dict, list))
    )
    record_tokens = _tokens(haystack)
    return len(query_tokens & record_tokens)


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(record: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record:
            return record.get(key)
    return None


class InternalCatalogProvider:
    """Reads optional structured catalog data without inventing missing fields."""

    provider_name = "internal_catalog"

    def __init__(self, catalog_path: Optional[str] = None, kb_dir: Optional[str] = None):
        self.catalog_path = catalog_path
        self.kb_dir = kb_dir
        self.records = self._load_records()

    def _candidate_paths(self) -> List[Path]:
        paths: List[Path] = []
        if self.catalog_path:
            paths.append(Path(self.catalog_path))
        if self.kb_dir:
            base = Path(self.kb_dir)
            paths.extend([
                base / "catalog.jsonl",
                base / "catalog.json",
                base / "products.jsonl",
                base / "products.json",
            ])
        return paths

    def _load_records(self) -> List[Dict[str, Any]]:
        for path in self._candidate_paths():
            records = _load_json_records(path)
            if records:
                return records
        return []

    def search_candidates(self, query: str, limit: int = 5) -> List[CatalogCandidate]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        scored = [
            (_score_record(query_tokens, record), record)
            for record in self.records
        ]
        scored = [(score, record) for score, record in scored if score > 0]
        scored.sort(key=lambda item: item[0], reverse=True)

        candidates: List[CatalogCandidate] = []
        for _, record in scored[:limit]:
            candidates.append(CatalogCandidate(
                product_id=_first(record, "product_id", "sku", "code", "id"),
                name=_first(record, "name", "title", "product_name"),
                category=_first(record, "category", "type"),
                price=_coerce_float(_first(record, "price", "price_vnd", "amount")),
                currency=_first(record, "currency"),
                source=_first(record, "source", "url"),
                material=_first(record, "material"),
                dimensions=_first(record, "dimensions", "size"),
                notes=_first(record, "notes", "description", "content"),
            ))
        return candidates


class ExternalPriceProvider:
    """Interface for future SerpAPI, Google Shopping, or crawler providers."""

    provider_name = "external_price"

    def get_price_references(self, query: str, limit: int = 5) -> List[PriceReference]:
        return []


class MockMarketPriceProvider(ExternalPriceProvider):
    """Demo/reference provider backed by an explicit mock JSON file."""

    provider_name = "mock_market_price"

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else DEFAULT_MOCK_PRICE_PATH
        self.records = _load_json_records(self.path)

    def get_price_references(self, query: str, limit: int = 5) -> List[PriceReference]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        scored = [
            (_score_record(query_tokens, record), record)
            for record in self.records
        ]
        scored = [(score, record) for score, record in scored if score > 0]
        scored.sort(key=lambda item: item[0], reverse=True)

        refs: List[PriceReference] = []
        for _, record in scored[:limit]:
            refs.append(PriceReference(
                product_id=_first(record, "product_id", "sku", "code", "id"),
                name=_first(record, "name", "title", "product_name"),
                category=_first(record, "category", "type"),
                price=_coerce_float(_first(record, "price", "price_vnd", "amount")),
                currency=_first(record, "currency"),
                source=_first(record, "source", "url"),
                provider=self.provider_name,
                is_mock=True,
                notes=_first(record, "notes", "description"),
            ))
        return refs


def is_mock_market_price_enabled() -> bool:
    provider = os.getenv("MARKET_PRICE_PROVIDER", "").strip().lower()
    flag = os.getenv("USE_MOCK_MARKET_PRICE", "0").strip().lower()
    return provider == "mock" or flag in TRUE_VALUES


def build_internal_catalog_provider(kb_dir: Optional[str]) -> InternalCatalogProvider:
    return InternalCatalogProvider(
        catalog_path=os.getenv("INTERNAL_CATALOG_PATH") or None,
        kb_dir=kb_dir,
    )


def build_price_provider() -> ExternalPriceProvider:
    if is_mock_market_price_enabled():
        return MockMarketPriceProvider(os.getenv("MOCK_MARKET_PRICE_PATH") or None)
    return ExternalPriceProvider()


def format_catalog_candidates(candidates: Iterable[CatalogCandidate]) -> str:
    lines = []
    for item in candidates:
        lines.append(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True))
    return "\n".join(lines)


def format_price_references(refs: Iterable[PriceReference]) -> str:
    lines = []
    for ref in refs:
        lines.append(json.dumps(ref.to_dict(), ensure_ascii=False, sort_keys=True))
    return "\n".join(lines)
