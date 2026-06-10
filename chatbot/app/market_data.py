import json
import os
import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote_plus


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


def _plain_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D").lower()


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", _plain_text(text)) if len(token) >= 2}


def _score_record(query_tokens: set[str], record: Dict[str, Any]) -> int:
    haystack = " ".join(
        str(value)
        for value in record.values()
        if value is not None and not isinstance(value, (dict, list))
    )
    record_tokens = _tokens(haystack)
    return len(query_tokens & record_tokens)


def _product_ids_in_query(query: str, records: Iterable[Dict[str, Any]]) -> set[str]:
    lowered_query = (query or "").lower()
    matches: set[str] = set()
    for record in records:
        product_id = _first(record, "product_id", "sku", "code", "id")
        if product_id and str(product_id).lower() in lowered_query:
            matches.add(str(product_id))
    return matches


def _query_product_type(query: str) -> Optional[str]:
    plain = _plain_text(query)
    if "sofa" in plain:
        return "sofa"
    if "ban an" in plain:
        return "ban an"
    if "ban tra" in plain:
        return "ban tra"
    if "tu quan ao" in plain or "tu ao" in plain:
        return "tu quan ao"
    if "giuong" in plain:
        return "giuong"
    return None


def _query_material(query: str) -> Optional[str]:
    plain = _plain_text(query)
    if "go soi" in plain:
        return "go soi"
    if "mdf" in plain:
        return "mdf"
    if "go tu nhien" in plain:
        return "go tu nhien"
    if "da cong nghiep" in plain:
        return "da cong nghiep"
    if "vai ni" in plain:
        return "vai ni"
    return None


def _record_plain_haystack(record: Dict[str, Any]) -> str:
    return _plain_text(" ".join(
        str(value)
        for value in record.values()
        if value is not None and not isinstance(value, (dict, list))
    ))


def _record_matches_product_type(record: Dict[str, Any], product_type: str) -> bool:
    haystack = _plain_text(" ".join(
        str(value)
        for value in (
            _first(record, "category", "type"),
            _first(record, "name", "title", "product_name"),
        )
        if value
    ))
    if product_type == "sofa":
        return "sofa" in haystack
    if product_type == "ban an":
        return "ban an" in haystack
    if product_type == "ban tra":
        return "ban tra" in haystack
    if product_type == "tu quan ao":
        return "tu quan ao" in haystack or "tu ao" in haystack
    if product_type == "giuong":
        return "giuong" in haystack
    return True


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

        exact_product_ids = _product_ids_in_query(query, self.records)
        records = [
            record for record in self.records
            if not exact_product_ids
            or str(_first(record, "product_id", "sku", "code", "id")) in exact_product_ids
        ]
        if not exact_product_ids:
            product_type = _query_product_type(query)
            if product_type:
                typed_records = [
                    record for record in records
                    if _record_matches_product_type(record, product_type)
                ]
                if typed_records:
                    records = typed_records
            material = _query_material(query)
            if material:
                material_records = [
                    record for record in records
                    if material in _record_plain_haystack(record)
                ]
                if material_records:
                    records = material_records
        scored = [
            (_score_record(query_tokens, record), record)
            for record in records
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


class DatabaseMarketPriceProvider(ExternalPriceProvider):
    """Market price provider backed by Postgres observations."""

    provider_name = "database_market_price"

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or _database_url_from_env()

    def _load_records(self) -> List[Dict[str, Any]]:
        if not self.database_url:
            return []
        try:
            import psycopg
            from psycopg.rows import dict_row
        except Exception:
            return []

        query = """
            SELECT
                product_id,
                name,
                product_type AS category,
                price,
                currency,
                COALESCE(source_url, source_name) AS source,
                material,
                dimensions,
                brand,
                condition,
                confidence,
                observed_at
            FROM market_price_observations
            WHERE status = 'ACTIVE'
            ORDER BY observed_at DESC, created_at DESC
            LIMIT 1000
        """
        try:
            with psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []

    def get_price_references(self, query: str, limit: int = 5) -> List[PriceReference]:
        records = self._load_records()
        return _records_to_price_references(
            records,
            query,
            limit=max(1, limit),
            provider_name=self.provider_name,
            is_mock=False,
        )


def _database_url_from_env() -> Optional[str]:
    direct = os.getenv("MARKET_PRICE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if direct:
        return direct

    host = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST")
    if not host:
        return None
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "global_admin")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{db}"


def _records_to_price_references(
    records: List[Dict[str, Any]],
    query: str,
    *,
    limit: int,
    provider_name: str,
    is_mock: bool,
) -> List[PriceReference]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    exact_product_ids = _product_ids_in_query(query, records)
    filtered = [
        record for record in records
        if not exact_product_ids
        or str(_first(record, "product_id", "sku", "code", "id")) in exact_product_ids
    ]
    if not exact_product_ids:
        product_type = _query_product_type(query)
        if product_type:
            typed_records = [
                record for record in filtered
                if _record_matches_product_type(record, product_type)
            ]
            if typed_records:
                filtered = typed_records
        material = _query_material(query)
        if material:
            material_records = [
                record for record in filtered
                if material in _record_plain_haystack(record)
            ]
            if material_records:
                filtered = material_records

    scored = [
        (_score_record(query_tokens, record), record)
        for record in filtered
    ]
    scored = [(score, record) for score, record in scored if score > 0]
    scored.sort(key=lambda item: item[0], reverse=True)

    refs: List[PriceReference] = []
    for _, record in scored[:limit]:
        refs.append(PriceReference(
            product_id=_first(record, "product_id", "sku", "code", "id"),
            name=_first(record, "name", "title", "product_name"),
            category=_first(record, "category", "type", "product_type"),
            price=_coerce_float(_first(record, "price", "price_vnd", "amount")),
            currency=_first(record, "currency"),
            source=_first(record, "source", "source_url", "source_name", "url"),
            provider=provider_name,
            is_mock=is_mock,
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
    provider = os.getenv("MARKET_PRICE_PROVIDER", "").strip().lower()
    if provider in {"db", "database", "postgres", "postgresql"}:
        return DatabaseMarketPriceProvider()
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
