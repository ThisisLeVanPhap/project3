import json
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urljoin

from data_pipeline.crawling.extractors.base import BaseProductExtractor
from data_pipeline.crawling.normalize import normalize_text
from data_pipeline.crawling.schema import ProductObservation


MAX_HTML_CHARS = 2_000_000
MAX_SCRIPT_CHARS = 500_000
MAX_JSON_SCAN_CHARS = 300_000
MAX_RECURSION_DEPTH = 60


class _ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts: list[dict[str, str]] = []
        self._current: Optional[dict[str, str]] = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        if tag.lower() != "script":
            return
        self._current = {key.lower(): (value or "") for key, value in attrs}
        self._parts = []

    def handle_endtag(self, tag: str):
        if tag.lower() == "script" and self._current is not None:
            self._current["content"] = "".join(self._parts).strip()
            self.scripts.append(self._current)
            self._current = None
            self._parts = []

    def handle_data(self, data: str):
        if self._current is not None:
            current_size = sum(len(part) for part in self._parts)
            if current_size >= MAX_SCRIPT_CHARS:
                return
            remaining = MAX_SCRIPT_CHARS - current_size
            data = data[:remaining]
            self._parts.append(data)


class HydrationProductExtractor(BaseProductExtractor):
    """Extract simple product objects from common frontend hydration payloads."""

    def extract(
        self,
        html: str,
        source_url: str,
        tenant_id: Optional[str] = None,
    ) -> list[ProductObservation]:
        payloads = _extract_payloads(html or "")
        products: list[ProductObservation] = []
        seen_hashes: set[str] = set()

        for payload in payloads:
            for item in _iter_candidate_products(payload):
                observation = _candidate_to_observation(item, source_url, tenant_id)
                if observation and observation.content_hash not in seen_hashes:
                    products.append(observation)
                    seen_hashes.add(observation.content_hash or "")
        return products


def _extract_payloads(html: str) -> list[Any]:
    parser = _ScriptParser()
    parser.feed((html or "")[:MAX_HTML_CHARS])

    payloads: list[Any] = []
    for script in parser.scripts:
        content = script.get("content", "")
        if not content or len(content) > MAX_SCRIPT_CHARS:
            continue
        if script.get("id") == "__NEXT_DATA__":
            parsed = _loads_json(content)
            if parsed is not None:
                payloads.append(parsed)
            continue

        for marker in ("window.__INITIAL_STATE__", "window.__NUXT__", "__NUXT__"):
            payload = _extract_assignment_payload(content, marker)
            if payload is not None:
                payloads.append(payload)
    return payloads


def _loads_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None


def _extract_assignment_payload(script: str, marker: str) -> Any:
    index = script.find(marker)
    if index < 0:
        return None
    equals = script.find("=", index + len(marker))
    if equals < 0:
        return None
    start = _find_json_start(script, equals + 1)
    if start < 0:
        return None
    end = _find_json_end(script, start)
    if end < 0:
        return None
    return _loads_json(script[start:end + 1])


def _find_json_start(text: str, start: int) -> int:
    scan_end = min(len(text), start + MAX_JSON_SCAN_CHARS)
    for index in range(start, scan_end):
        if text[index] in "{[":
            return index
    return -1


def _find_json_end(text: str, start: int) -> int:
    stack: list[str] = []
    in_string = False
    escaped = False

    scan_end = min(len(text), start + MAX_JSON_SCAN_CHARS)
    for index in range(start, scan_end):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
        elif char in "}]":
            if not stack or stack[-1] != char:
                return -1
            stack.pop()
            if not stack:
                return index
    return -1


def _iter_candidate_products(data: Any, depth: int = 0):
    if depth > MAX_RECURSION_DEPTH:
        return

    if isinstance(data, list):
        for item in data:
            yield from _iter_candidate_products(item, depth + 1)
        return

    if not isinstance(data, dict):
        return

    if _looks_like_product(data):
        yield data

    for value in data.values():
        if isinstance(value, (dict, list)):
            yield from _iter_candidate_products(value, depth + 1)


def _looks_like_product(item: dict[str, Any]) -> bool:
    has_name = any(normalize_text(item.get(key)) for key in ("name", "title", "productName"))
    has_price = any(item.get(key) not in (None, "") for key in ("price", "salePrice", "finalPrice", "regularPrice"))
    has_offer = isinstance(item.get("offers"), dict)
    has_sku = normalize_text(item.get("sku")) is not None
    return has_name and (has_price or has_offer or has_sku)


def _candidate_to_observation(
    item: dict[str, Any],
    source_url: str,
    tenant_id: Optional[str],
) -> Optional[ProductObservation]:
    product_name = _first_text(item, "name", "title", "productName")
    if not product_name:
        return None

    offer = item.get("offers") if isinstance(item.get("offers"), dict) else {}
    price = _first_value(item, "price", "salePrice", "finalPrice", "regularPrice")
    if price is None and offer:
        price = _first_value(offer, "price", "lowPrice")

    raw_url = _first_value(item, "url", "canonicalUrl", "href", "link")
    canonical_url = urljoin(source_url, str(raw_url)) if raw_url else source_url

    return ProductObservation(
        tenant_id=tenant_id,
        source_url=source_url,
        canonical_url=canonical_url,
        product_name=product_name,
        price=price,
        currency=_first_value(item, "currency", "priceCurrency") or _first_value(offer, "priceCurrency") or "VND",
        category=_first_text(item, "category", "productType"),
        brand=_brand_name(item.get("brand")),
        material=_first_text(item, "material"),
        color=_first_text(item, "color"),
        dimensions=_first_text(item, "dimensions", "size"),
        description=_first_text(item, "description", "shortDescription"),
        image_urls=_images_from_candidate(item),
        availability=_first_text(item, "availability", "stockStatus"),
        sku=_first_text(item, "sku", "id", "productId"),
        metadata={"extractor": "hydration", "extractor_priority": 2},
    )


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _first_text(data: dict[str, Any], *keys: str) -> Optional[str]:
    return normalize_text(_first_value(data, *keys))


def _brand_name(brand: Any) -> Optional[str]:
    if isinstance(brand, dict):
        return normalize_text(brand.get("name"))
    return normalize_text(brand)


def _images_from_candidate(item: dict[str, Any]) -> list[str]:
    images: list[str] = []
    for key in ("image", "images", "imageUrls", "gallery"):
        images.extend(_flatten_images(item.get(key)))
    return images


def _flatten_images(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        urls: list[str] = []
        for item in value:
            urls.extend(_flatten_images(item))
        return urls
    if isinstance(value, dict):
        for key in ("url", "src", "contentUrl"):
            if value.get(key):
                return [str(value[key])]
    return []
