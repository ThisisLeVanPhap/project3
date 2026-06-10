import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


CONTACT_PRICE_WORDS = {
    "lien he",
    "lienhe",
    "bao gia",
    "call",
    "contact",
    "thoa thuan",
}

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "yclid", "mc_cid", "mc_eid"}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D")


def normalize_text(value: Any) -> Optional[str]:
    """Normalize scraped text by trimming and collapsing whitespace."""
    if value is None:
        return None
    text = str(value).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_price(value: Any) -> Optional[int]:
    """Normalize common Vietnamese VND price strings.

    Handles explicit VND amounts and simple "triệu/trieu" values such as
    "1.2 triệu" -> 1200000. It intentionally does not infer ranges; callers
    should pass a single selected price when a page shows "1-2 triệu".
    """
    text = normalize_text(value)
    if not text:
        return None

    plain = _strip_accents(text).lower()
    compact_plain = re.sub(r"\s+", " ", plain)
    if any(word in compact_plain for word in CONTACT_PRICE_WORDS):
        return None

    number_match = re.search(r"\d+(?:[.,]\d+)*", compact_plain)
    if not number_match:
        return None

    number_text = number_match.group(0)
    if "trieu" in compact_plain:
        decimal_text = number_text.replace(",", ".")
        try:
            return int(round(float(decimal_text) * 1_000_000))
        except ValueError:
            return None

    digits = re.sub(r"\D", "", number_text)
    if not digits:
        return None
    return int(digits)


def normalize_currency(value: Any) -> str:
    """Return a compact currency code. Defaults to VND for local crawling."""
    text = normalize_text(value)
    if not text:
        return "VND"

    plain = _strip_accents(text).upper()
    if "USD" in plain or "$" in plain:
        return "USD"
    if "EUR" in plain:
        return "EUR"
    return "VND"


def canonicalize_url(url: Any) -> Optional[str]:
    """Canonicalize URL for dedupe without crashing on bad scraped input."""
    text = normalize_text(url)
    if not text:
        return None

    parts = urlsplit(text)
    if not parts.scheme and not parts.netloc:
        if not parts.path or re.search(r"\s", parts.path):
            return None
        scheme = ""
        netloc = ""
    else:
        scheme = (parts.scheme or "https").lower()
        netloc = parts.netloc.lower()
        if not netloc:
            return None

    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")

    query_items = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower in TRACKING_QUERY_KEYS or key_lower.startswith(TRACKING_QUERY_PREFIXES):
            continue
        query_items.append((key, val))
    query_items.sort()

    return urlunsplit((scheme, netloc, path, urlencode(query_items), ""))


def make_content_hash(data: Any) -> str:
    """Create a stable SHA-256 hash for dict/list/string data."""
    if isinstance(data, (dict, list, tuple)):
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        payload = str(data or "")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_image_urls(urls: Iterable[Any], base_url: Optional[str] = None) -> list[str]:
    """Normalize, absolutize, canonicalize, and deduplicate image URLs."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in urls or []:
        text = normalize_text(raw)
        if not text:
            continue
        absolute_url = urljoin(base_url, text) if base_url else text
        normalized = canonicalize_url(absolute_url)
        if not normalized:
            continue
        if normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result
