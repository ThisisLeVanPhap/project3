"""Parser entrypoint for Nha Xinh product pages."""

from __future__ import annotations

from .generic import parse_product as parse_generic_product


def parse_product(html, metadata):
    product = parse_generic_product(html, metadata)
    product["store"] = product.get("store") or "nhaxinh"
    return product
