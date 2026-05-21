"""Generic HTML product parser.

This parser only extracts values present in the page. Missing values stay None
so the JSONL writer emits null instead of invented data.
"""

from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser


PRODUCT_FIELDS = [
    "tenant_id",
    "store",
    "category",
    "source_type",
    "visibility",
    "source_url",
    "product_id",
    "name",
    "brand",
    "sku",
    "price",
    "currency",
    "sale_price",
    "availability",
    "description",
    "attributes",
    "images",
    "crawled_at",
    "raw_path",
]


class MetadataHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.links = []
        self.scripts = []
        self._capture_script = False
        self._script_type = None
        self._script_chunks = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = {key.lower(): value for key, value in attrs if key}
        tag = tag.lower()

        if tag == "meta":
            name = attrs_dict.get("property") or attrs_dict.get("name")
            content = attrs_dict.get("content")
            if name and content is not None:
                self.meta[name.lower()] = unescape(content).strip()

        if tag == "link":
            href = attrs_dict.get("href")
            rel = (attrs_dict.get("rel") or "").lower()
            if href and "canonical" in rel:
                self.links.append(("canonical", href))

        if tag == "script":
            self._script_type = (attrs_dict.get("type") or "").lower()
            if self._script_type == "application/ld+json":
                self._capture_script = True
                self._script_chunks = []

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._capture_script:
            text = "".join(self._script_chunks).strip()
            if text:
                self.scripts.append(text)
            self._capture_script = False
            self._script_type = None
            self._script_chunks = []

    def handle_data(self, data):
        if self._capture_script:
            self._script_chunks.append(data)


def empty_product(metadata):
    return {
        "tenant_id": metadata.get("tenant_id"),
        "store": metadata.get("store"),
        "category": metadata.get("category"),
        "source_type": metadata.get("source_type"),
        "visibility": metadata.get("visibility"),
        "source_url": metadata.get("url"),
        "product_id": None,
        "name": None,
        "brand": None,
        "sku": None,
        "price": None,
        "currency": None,
        "sale_price": None,
        "availability": None,
        "description": None,
        "attributes": {},
        "images": [],
        "crawled_at": metadata.get("crawled_at"),
        "raw_path": metadata.get("raw_path"),
    }


def parse_product(html, metadata):
    parser = MetadataHTMLParser()
    parser.feed(html or "")

    product = empty_product(metadata)
    apply_open_graph(product, parser.meta)

    json_ld_nodes = []
    for script in parser.scripts:
        json_ld_nodes.extend(load_json_ld(script))

    for node in flatten_json_ld(json_ld_nodes):
        if is_product_node(node):
            apply_json_ld_product(product, node)
            break

    product["attributes"] = product["attributes"] or {}
    product["images"] = product["images"] or []
    return {field: product.get(field) for field in PRODUCT_FIELDS}


def apply_open_graph(product, meta):
    product["name"] = first_present(
        product.get("name"),
        meta.get("og:title"),
        meta.get("twitter:title"),
    )
    product["description"] = first_present(
        product.get("description"),
        meta.get("og:description"),
        meta.get("description"),
        meta.get("twitter:description"),
    )
    product["source_url"] = first_present(product.get("source_url"), meta.get("og:url"))

    image = first_present(meta.get("og:image"), meta.get("twitter:image"))
    if image:
        product["images"] = [image]

    amount = first_present(
        meta.get("product:price:amount"),
        meta.get("og:price:amount"),
    )
    currency = first_present(
        meta.get("product:price:currency"),
        meta.get("og:price:currency"),
    )
    if amount is not None:
        product["price"] = parse_number(amount)
    if currency:
        product["currency"] = currency


def load_json_ld(text):
    cleaned = text.strip()
    if not cleaned:
        return []
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else [data]


def flatten_json_ld(nodes):
    stack = list(nodes)
    while stack:
        node = stack.pop(0)
        if isinstance(node, list):
            stack = node + stack
            continue
        if not isinstance(node, dict):
            continue
        graph = node.get("@graph")
        if isinstance(graph, list):
            stack = graph + stack
        yield node


def is_product_node(node):
    value = node.get("@type")
    if isinstance(value, list):
        return any(str(item).lower() == "product" for item in value)
    return str(value).lower() == "product"


def apply_json_ld_product(product, node):
    product["product_id"] = first_present(product.get("product_id"), node.get("@id"))
    product["name"] = first_present(product.get("name"), node.get("name"))
    product["description"] = first_present(product.get("description"), node.get("description"))
    product["sku"] = first_present(product.get("sku"), node.get("sku"), node.get("mpn"))

    brand = node.get("brand")
    if isinstance(brand, dict):
        product["brand"] = first_present(product.get("brand"), brand.get("name"))
    elif isinstance(brand, str):
        product["brand"] = first_present(product.get("brand"), brand)

    images = node.get("image")
    if isinstance(images, str):
        product["images"] = merge_unique(product.get("images"), [images])
    elif isinstance(images, list):
        product["images"] = merge_unique(
            product.get("images"),
            [item for item in images if isinstance(item, str)],
        )

    offers = node.get("offers")
    offer = first_offer(offers)
    if offer:
        product["price"] = first_present(product.get("price"), parse_number(offer.get("price")))
        product["currency"] = first_present(product.get("currency"), offer.get("priceCurrency"))
        product["availability"] = first_present(product.get("availability"), offer.get("availability"))
        product["source_url"] = first_present(product.get("source_url"), offer.get("url"))

    attributes = {}
    for key in ("material", "color", "width", "height", "depth", "weight"):
        if node.get(key) is not None:
            attributes[key] = node.get(key)
    product["attributes"] = {**(product.get("attributes") or {}), **attributes}


def first_offer(offers):
    if isinstance(offers, dict):
        return offers
    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                return offer
    return None


def first_present(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def merge_unique(left, right):
    seen = set()
    merged = []
    for value in (left or []) + (right or []):
        if value and value not in seen:
            seen.add(value)
            merged.append(value)
    return merged


def parse_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"[^0-9,.]", "", text)
    if not text:
        return None
    text = normalize_number_separators(text)
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def normalize_number_separators(text):
    comma_count = text.count(",")
    dot_count = text.count(".")

    if comma_count and dot_count:
        if text.rfind(",") > text.rfind("."):
            return text.replace(".", "").replace(",", ".")
        return text.replace(",", "")

    if comma_count:
        if comma_count > 1:
            return text.replace(",", "")
        before, after = text.split(",", 1)
        if len(after) == 3 and before:
            return before + after
        return before + "." + after

    if dot_count:
        if dot_count > 1:
            return text.replace(".", "")
        before, after = text.split(".", 1)
        if len(after) == 3 and before:
            return before + after

    return text
