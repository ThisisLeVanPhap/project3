import json
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urljoin

from data_pipeline.crawling.extractors.base import BaseProductExtractor
from data_pipeline.crawling.normalize import normalize_text
from data_pipeline.crawling.schema import ProductObservation


class _JsonLdScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts: list[str] = []
        self._capture = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        if tag.lower() != "script":
            return
        attr_map = {key.lower(): (value or "") for key, value in attrs}
        if attr_map.get("type", "").lower() == "application/ld+json":
            self._capture = True
            self._parts = []

    def handle_endtag(self, tag: str):
        if tag.lower() == "script" and self._capture:
            self.scripts.append("".join(self._parts).strip())
            self._capture = False
            self._parts = []

    def handle_data(self, data: str):
        if self._capture:
            self._parts.append(data)


class JsonLdProductExtractor(BaseProductExtractor):
    """Extract Product objects from application/ld+json scripts."""

    def extract(
        self,
        html: str,
        source_url: str,
        tenant_id: Optional[str] = None,
    ) -> list[ProductObservation]:
        parser = _JsonLdScriptParser()
        parser.feed(html or "")

        products: list[ProductObservation] = []
        for script in parser.scripts:
            try:
                data = json.loads(script)
            except json.JSONDecodeError:
                continue
            for item in _iter_product_objects(data):
                observation = _product_to_observation(item, source_url, tenant_id)
                if observation:
                    products.append(observation)
        return products


def _iter_product_objects(data: Any):
    if isinstance(data, list):
        for item in data:
            yield from _iter_product_objects(item)
        return

    if not isinstance(data, dict):
        return

    if _is_product(data):
        yield data

    graph = data.get("@graph")
    if isinstance(graph, (list, dict)):
        yield from _iter_product_objects(graph)


def _is_product(item: dict[str, Any]) -> bool:
    raw_type = item.get("@type")
    if isinstance(raw_type, str):
        return raw_type.lower() == "product"
    if isinstance(raw_type, list):
        return any(isinstance(value, str) and value.lower() == "product" for value in raw_type)
    return False


def _product_to_observation(
    item: dict[str, Any],
    source_url: str,
    tenant_id: Optional[str],
) -> Optional[ProductObservation]:
    product_name = normalize_text(item.get("name"))
    if not product_name:
        return None

    offer = _first_offer(item.get("offers"))
    price = _first_value(offer, "price", "lowPrice") if offer else None
    currency = _first_value(offer, "priceCurrency") if offer else None
    availability = _first_value(offer, "availability") if offer else None

    raw_url = item.get("url") or source_url
    canonical_url = urljoin(source_url, str(raw_url)) if raw_url else None

    return ProductObservation(
        tenant_id=tenant_id,
        source_url=source_url,
        canonical_url=canonical_url,
        product_name=product_name,
        price=price,
        currency=currency or "VND",
        category=item.get("category"),
        brand=_brand_name(item.get("brand")),
        description=item.get("description"),
        image_urls=_image_urls(item.get("image")),
        availability=availability,
        sku=item.get("sku"),
        metadata={"extractor": "json_ld", "extractor_priority": 1},
    )


def _first_offer(raw_offers: Any) -> Optional[dict[str, Any]]:
    if isinstance(raw_offers, dict):
        return raw_offers
    if isinstance(raw_offers, list):
        for offer in raw_offers:
            if isinstance(offer, dict):
                return offer
    return None


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _brand_name(brand: Any) -> Optional[str]:
    if isinstance(brand, dict):
        return normalize_text(brand.get("name"))
    return normalize_text(brand)


def _image_urls(image: Any) -> list[str]:
    if isinstance(image, str):
        return [image]
    if isinstance(image, list):
        urls: list[str] = []
        for item in image:
            urls.extend(_image_urls(item))
        return urls
    if isinstance(image, dict):
        for key in ("url", "contentUrl"):
            if image.get(key):
                return [str(image[key])]
    return []
