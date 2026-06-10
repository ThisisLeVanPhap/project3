from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from .normalize import (
    canonicalize_url,
    make_content_hash,
    normalize_currency,
    normalize_image_urls,
    normalize_price,
    normalize_text,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ProductObservation(BaseModel):
    """Structured product data extracted from crawled furniture pages."""

    tenant_id: Optional[str] = None
    source_url: str
    canonical_url: Optional[str] = None
    product_name: str
    price: Optional[float] = None
    original_price: Optional[float] = None
    currency: str = "VND"
    category: Optional[str] = None
    brand: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    dimensions: Optional[str] = None
    description: Optional[str] = None
    image_urls: list[str] = Field(default_factory=list)
    availability: Optional[str] = None
    sku: Optional[str] = None
    observed_at: datetime = Field(default_factory=_now_utc)
    content_hash: Optional[str] = None
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data: Any):
        if "source_url" in data:
            canonical_source_url = canonicalize_url(data["source_url"])
            if canonical_source_url:
                data["source_url"] = canonical_source_url
        if data.get("canonical_url"):
            data["canonical_url"] = canonicalize_url(data["canonical_url"])
        if "product_name" in data:
            data["product_name"] = normalize_text(data["product_name"]) or data["product_name"]
        if "price" in data:
            data["price"] = normalize_price(data["price"])
        if "original_price" in data:
            data["original_price"] = normalize_price(data["original_price"])
        if "currency" in data:
            data["currency"] = normalize_currency(data["currency"])
        for key in (
            "category",
            "brand",
            "material",
            "color",
            "dimensions",
            "description",
            "availability",
            "sku",
        ):
            if key in data:
                data[key] = normalize_text(data[key])
        if "image_urls" in data:
            data["image_urls"] = normalize_image_urls(data["image_urls"], base_url=data.get("source_url"))
        super().__init__(**data)
        self.confidence = max(0.0, min(float(self.confidence), 1.0))
        if not self.content_hash:
            self.content_hash = make_content_hash(self.to_jsonl_dict(include_hash=False))

    def to_jsonl_dict(self, include_hash: bool = True) -> dict[str, Any]:
        """Export a compact dict suitable for JSONL catalog/RAG build steps."""
        row = {
            "tenant_id": self.tenant_id,
            "source_url": self.source_url,
            "canonical_url": self.canonical_url,
            "product_name": self.product_name,
            "price": self.price,
            "original_price": self.original_price,
            "currency": self.currency,
            "category": self.category,
            "brand": self.brand,
            "material": self.material,
            "color": self.color,
            "dimensions": self.dimensions,
            "description": self.description,
            "image_urls": list(self.image_urls),
            "availability": self.availability,
            "sku": self.sku,
            "observed_at": self.observed_at.isoformat(),
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }
        if include_hash:
            row["content_hash"] = self.content_hash
        return row
