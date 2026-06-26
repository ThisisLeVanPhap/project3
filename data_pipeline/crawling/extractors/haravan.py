"""
HaravanProductExtractor — extract product from Haravan e-commerce platform.

Haravan (moho.com.vn) embeds product data in:
  window.HaravanAnalytics.meta.product = { price, sku, title, imageUrl, variants, ... }

No JSON-LD Product schema is present. This is a lightweight text-based
extractor that finds the HaravanAnalytics.meta.product assignment and
parses the JSON literal.
"""

import json
import logging
import re
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urljoin

from data_pipeline.crawling.extractors.base import BaseProductExtractor
from data_pipeline.crawling.normalize import normalize_price, normalize_text
from data_pipeline.crawling.schema import ProductObservation

_logger = logging.getLogger(__name__)


class _ScriptContentParser(HTMLParser):
    """Collect text content of all <script> tags."""

    def __init__(self):
        super().__init__()
        self.scripts: list[str] = []

    def handle_data(self, data: str):
        self.scripts.append(data)


HARAVAN_PRODUCT_PATTERN = re.compile(
    r"""window\.HaravanAnalytics\s*=\s*window\.HaravanAnalytics\s*\|\|\s*\{\}\s*;"""
    r"""\s*window\.HaravanAnalytics\.meta\s*=\s*window\.HaravanAnalytics\.meta\s*\|\|\s*\{\}\s*;"""
    r"""\s*(?:var\s+)?meta\s*=\s*(\{.+?\});"""
    r"""\s*for\s*\(?\s*(?:var\s+)?attr\s+in\s+meta\s*\)?""",
    re.DOTALL,
)


class HaravanProductExtractor(BaseProductExtractor):
    """Extract product from HaravanAnalytics.meta.product JS assignment."""

    def extract(
        self,
        html: str,
        source_url: str,
        tenant_id: Optional[str] = None,
    ) -> list[ProductObservation]:
        if not html:
            return []

        # Find the meta = {...} block
        match = HARAVAN_PRODUCT_PATTERN.search(html or "")
        if not match:
            return []

        raw_json = match.group(1)
        try:
            meta = json.loads(raw_json)
        except json.JSONDecodeError:
            return []

        product_data = meta.get("product") if isinstance(meta, dict) else None
        if not isinstance(product_data, dict):
            return []

        title = normalize_text(product_data.get("title"))
        if not title:
            return []

        price = product_data.get("price")
        if price is None:
            price = product_data.get("compare_at_price")

        variants = product_data.get("variants") or []
        first_variant = variants[0] if isinstance(variants, list) and variants else {}

        sku = product_data.get("sku") or first_variant.get("sku")

        raw_image = product_data.get("imageUrl") or ""
        if raw_image and not raw_image.startswith("http"):
            raw_image = "https:" + raw_image if raw_image.startswith("//") else raw_image
        images = [raw_image] if raw_image else []

        return [
            ProductObservation(
                tenant_id=tenant_id,
                source_url=source_url,
                canonical_url=source_url,
                product_name=title,
                price=price,
                currency="VND",
                category=product_data.get("type"),
                sku=sku,
                image_urls=images,
                brand=normalize_text(product_data.get("vendor")),
                availability="in_stock" if product_data.get("available") else "out_of_stock",
                metadata={"extractor": "haravan", "extractor_priority": 1},
            )
        ]
