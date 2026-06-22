import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, TypeVar

from .retrievers.text import fold_accents, repair_mojibake


T = TypeVar("T")


@dataclass(frozen=True)
class PriceConstraint:
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    target_price: Optional[int] = None
    sort: Optional[str] = None

    def has_constraint(self) -> bool:
        return any(
            value is not None
            for value in (self.min_price, self.max_price, self.target_price, self.sort)
        )

    def as_dict(self) -> Dict[str, Optional[int] | Optional[str]]:
        return {
            "min_price": self.min_price,
            "max_price": self.max_price,
            "target_price": self.target_price,
            "sort": self.sort,
        }


NUMBER_WITH_UNIT_RE = re.compile(
    r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>trieu|tr|m|k|nghin|ngan|000)?\b",
    re.IGNORECASE,
)

CATEGORY_PATTERNS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Bàn làm việc", (r"\bban lam viec\b", r"\bban hoc\b", r"\bban may tinh\b")),
    ("Bàn ăn", (r"\bban ghe an\b", r"\bbo ban an\b", r"\bban an\b")),
    ("Bàn trà", (r"\bban tra\b", r"\bban sofa\b")),
    ("Sofa", (r"\bghe sofa\b", r"\bsofa\b")),
    ("Kệ", (r"\bke tivi\b", r"\bke sach\b", r"\bke\b")),
    ("Đồ trang trí", (r"\bdo trang tri\b", r"\bdo decor\b", r"\bphu kien trang tri\b", r"\bdecor\b", r"\bbinh hoa\b", r"\blo hoa\b", r"\bdong ho\b")),
    ("Rèm", (r"\brem\b", r"\bmanh\b")),
    ("Đèn", (r"\bden\b",)),
    ("Thảm", (r"\btham\b",)),
    ("Tranh", (r"\btranh\b",)),
    ("Gương", (r"\bguong\b",)),
    ("Ghế", (r"\bghe\b",)),
    ("Giường", (r"\bgiuong\b",)),
    ("Tủ", (r"\btu quan ao\b", r"\btu ao\b", r"\bwardrobe\b", r"\bcabinet\b", r"\btu\b(?!\s+van)\b")),
)


def _normalize_query(query: str) -> str:
    folded = fold_accents(query or "").lower()
    return re.sub(r"\s+", " ", folded).strip()


def _unit_multiplier(unit: Optional[str]) -> int:
    if unit in ("trieu", "tr", "m"):
        return 1_000_000
    if unit in ("k", "nghin", "ngan"):
        return 1_000
    return 1


def _parse_price_token(number_text: str, unit: Optional[str]) -> int:
    value = float(number_text.replace(",", "."))
    return int(value * _unit_multiplier(unit))


def _first_price(pattern: str, query: str) -> Optional[int]:
    match = re.search(pattern, query, flags=re.IGNORECASE)
    if not match:
        return None
    return _parse_price_token(match.group("number"), match.groupdict().get("unit"))


def parse_price_constraint(query: str) -> PriceConstraint:
    normalized = _normalize_query(query)
    if not normalized:
        return PriceConstraint()

    sort = None
    if re.search(r"\b(re nhat|gia re nhat)\b", normalized):
        sort = "asc"
    elif re.search(r"\b(dat nhat|cao cap nhat)\b", normalized):
        sort = "desc"

    range_match = re.search(
        r"\btu\s+(?P<min_number>\d+(?:[.,]\d+)?)\s*(?P<min_unit>trieu|tr|m|k|nghin|ngan|000)?"
        r"\s+(?:den|toi|-)\s+"
        r"(?P<max_number>\d+(?:[.,]\d+)?)\s*(?P<max_unit>trieu|tr|m|k|nghin|ngan|000)?\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if range_match:
        min_unit = range_match.group("min_unit") or range_match.group("max_unit")
        max_unit = range_match.group("max_unit") or range_match.group("min_unit")
        return PriceConstraint(
            min_price=_parse_price_token(range_match.group("min_number"), min_unit),
            max_price=_parse_price_token(range_match.group("max_number"), max_unit),
            sort=sort,
        )

    max_price = _first_price(
        r"\b(?:duoi|nho hon|khong qua|toi da|duoi muc)\s+"
        r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>trieu|tr|m|k|nghin|ngan|000)?\b",
        normalized,
    )
    min_price = _first_price(
        r"\b(?:tren|lon hon|tu|toi thieu)\s+"
        r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>trieu|tr|m|k|nghin|ngan|000)?\b",
        normalized,
    )
    target_price = _first_price(
        r"\b(?:tam|khoang|khoang tam|gan)\s+"
        r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>trieu|tr|m|k|nghin|ngan|000)?\b",
        normalized,
    )

    return PriceConstraint(
        min_price=min_price,
        max_price=max_price,
        target_price=target_price,
        sort=sort,
    )


def parse_product_categories(query: str) -> List[str]:
    normalized = _normalize_query(query)
    if not normalized:
        return []

    matches: List[Tuple[int, int, str]] = []
    for category, patterns in CATEGORY_PATTERNS:
        for pattern in patterns:
            for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                matches.append((match.start(), -(match.end() - match.start()), category))

    matches.sort(key=lambda item: (item[0], item[1]))
    categories: List[str] = []
    seen: Set[str] = set()
    for _, _, category in matches:
        if category in seen:
            continue
        categories.append(category)
        seen.add(category)
    return categories


def _metadata(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        metadata = result.get("metadata") or {}
    else:
        metadata = getattr(result, "metadata", {}) or {}
    return metadata if isinstance(metadata, dict) else {}


def _category(result: Any) -> str:
    value = _metadata(result).get("category") or ""
    return repair_mojibake(str(value)).strip()


def _category_matches(value: str, category: str) -> bool:
    value_folded = fold_accents(value).lower()
    category_folded = fold_accents(category).lower()
    return bool(value_folded) and (
        value_folded == category_folded
        or category_folded in value_folded
        or value_folded in category_folded
    )


def _price(result: Any) -> Optional[float]:
    value = _metadata(result).get("price")
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d,.]", "", value).replace(",", ".")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _matches_price_range(price: float, constraint: PriceConstraint) -> bool:
    if constraint.min_price is not None and price < constraint.min_price:
        return False
    if constraint.max_price is not None and price > constraint.max_price:
        return False
    return True


def _sort_priced(
    items: List[Tuple[int, T, float]],
    constraint: PriceConstraint,
) -> List[Tuple[int, T, float]]:
    if constraint.target_price is not None:
        return sorted(items, key=lambda item: (abs(item[2] - constraint.target_price), item[0]))
    if constraint.sort == "asc":
        return sorted(items, key=lambda item: (item[2], item[0]))
    if constraint.sort == "desc":
        return sorted(items, key=lambda item: (-item[2], item[0]))
    return items


def apply_price_constraint(results: Sequence[T], constraint: PriceConstraint | Dict[str, Any] | None) -> List[T]:
    original = list(results)
    if constraint is None:
        return original
    if isinstance(constraint, dict):
        constraint = PriceConstraint(
            min_price=constraint.get("min_price"),
            max_price=constraint.get("max_price"),
            target_price=constraint.get("target_price"),
            sort=constraint.get("sort"),
        )
    if not constraint.has_constraint():
        return original

    priced: List[Tuple[int, T, float]] = []
    unknown_price: List[Tuple[int, T]] = []
    for idx, result in enumerate(original):
        price = _price(result)
        if price is None:
            unknown_price.append((idx, result))
        else:
            priced.append((idx, result, price))

    has_range_filter = constraint.min_price is not None or constraint.max_price is not None
    if has_range_filter:
        matching = [item for item in priced if _matches_price_range(item[2], constraint)]
        if not matching:
            return original
        ranked = _sort_priced(matching, constraint)
        return [item[1] for item in ranked] + [item[1] for item in unknown_price]

    ranked = _sort_priced(priced, constraint)
    return [item[1] for item in ranked] + [item[1] for item in unknown_price]


def diversify_by_category(results: Sequence[T], categories: Sequence[str], k: int) -> List[T]:
    original = list(results)
    if len(categories) < 2 or k <= 0:
        return original

    selected_indexes: Set[int] = set()
    diversified: List[T] = []

    for category in categories:
        for idx, result in enumerate(original):
            if idx in selected_indexes:
                continue
            if _category_matches(_category(result), category):
                diversified.append(result)
                selected_indexes.add(idx)
                break
        if len(diversified) >= k:
            return diversified

    for idx, result in enumerate(original):
        if idx in selected_indexes:
            continue
        diversified.append(result)
        selected_indexes.add(idx)
        if len(diversified) >= k:
            break

    return diversified
