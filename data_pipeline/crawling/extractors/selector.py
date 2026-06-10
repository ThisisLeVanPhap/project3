from typing import Any, Optional

from bs4 import BeautifulSoup

from data_pipeline.crawling.extractors.base import BaseProductExtractor
from data_pipeline.crawling.normalize import normalize_image_urls, normalize_price, normalize_text
from data_pipeline.crawling.schema import ProductObservation


DEFAULT_SELECTORS = {
    "product_name": [
        "h1",
        ".product-title",
        ".product-name",
        '[itemprop="name"]',
        'meta[property="og:title"]',
    ],
    "price": [
        ".price",
        ".product-price",
        '[itemprop="price"]',
        'meta[property="product:price:amount"]',
    ],
    "description": [
        ".description",
        ".product-description",
        '[itemprop="description"]',
        'meta[name="description"]',
        'meta[property="og:description"]',
    ],
    "image": [
        'meta[property="og:image"]',
        '[itemprop="image"]',
        "img.product-image",
        ".product-image img",
    ],
    "availability": [
        '[itemprop="availability"]',
        ".availability",
        ".stock",
    ],
}


class SelectorProductExtractor(BaseProductExtractor):
    """Fallback extractor that reads common product fields from HTML selectors."""

    def __init__(self, selectors: Optional[dict[str, list[str]]] = None):
        merged = {key: list(value) for key, value in DEFAULT_SELECTORS.items()}
        for key, value in (selectors or {}).items():
            merged[key] = list(value)
        self.selectors = merged

    def extract(
        self,
        html: str,
        source_url: str,
        tenant_id: Optional[str] = None,
    ) -> list[ProductObservation]:
        soup = BeautifulSoup(html or "", "html.parser")
        product_name = _first_text_or_content(soup, self.selectors["product_name"])
        if not product_name:
            return []

        price = _first_text_or_content(soup, self.selectors["price"])
        description = _first_text_or_content(soup, self.selectors["description"])
        availability = _first_text_or_content(soup, self.selectors["availability"])
        images = _all_urls_or_content(soup, self.selectors["image"])

        return [
            ProductObservation(
                tenant_id=tenant_id,
                source_url=source_url,
                canonical_url=source_url,
                product_name=product_name,
                price=normalize_price(price),
                description=description,
                image_urls=normalize_image_urls(images, base_url=source_url),
                availability=availability,
                metadata={"extractor": "selector", "extractor_priority": 3},
            )
        ]


def _first_text_or_content(soup: BeautifulSoup, selectors: list[str]) -> Optional[str]:
    for selector in selectors:
        element = soup.select_one(selector)
        value = _element_value(element)
        if value:
            return value
    return None


def _all_urls_or_content(soup: BeautifulSoup, selectors: list[str]) -> list[str]:
    values: list[str] = []
    for selector in selectors:
        for element in soup.select(selector):
            value = _element_url_or_content(element)
            if value:
                values.append(value)
    return values


def _element_value(element: Any) -> Optional[str]:
    if element is None:
        return None
    if element.name == "meta":
        return normalize_text(element.get("content"))
    return normalize_text(element.get_text(" ", strip=True) or element.get("content"))


def _element_url_or_content(element: Any) -> Optional[str]:
    if element is None:
        return None
    for key in ("content", "src", "data-src", "href"):
        value = element.get(key)
        if value:
            return normalize_text(value)
    return normalize_text(element.get_text(" ", strip=True))
