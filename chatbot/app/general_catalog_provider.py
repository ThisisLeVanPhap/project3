"""
BackendGeneralCatalogProvider — gọi backend Spring Boot internal search API
cho mode GENERAL_COMPARE.

Hardening:
- Requests library (đã có sẵn) thay urlopen → UTF-8 encoding tự động.
- Internal API secret header nếu INTERNAL_API_SECRET set.
- Mặc định role=USER, không cho override từ input.
- 401/403 fallback rõ, không lộ secret.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

_logger = logging.getLogger(__name__)

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://app:8080")
INTERNAL_SEARCH_TIMEOUT = int(os.getenv("INTERNAL_SEARCH_TIMEOUT_SECONDS", "10"))
INTERNAL_SEARCH_LIMIT = int(os.getenv("INTERNAL_SEARCH_LIMIT", "5"))
_INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")


@dataclass
class BackendCatalogItem:
    name: str
    source_code: str
    source_name: str
    category: Optional[str] = None
    material: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    dimensions_text: Optional[str] = None
    description: Optional[str] = None
    score: float = 0.0
    score_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source_code": self.source_code,
            "source_name": self.source_name,
            "category": self.category,
            "material": self.material,
            "price": self.price,
            "currency": self.currency,
            "source_url": self.source_url,
            "image_url": self.image_url,
            "dimensions_text": self.dimensions_text,
            "description": self.description,
            "score": self.score,
            "score_reasons": self.score_reasons,
        }

    @staticmethod
    def from_api_item(item: Dict[str, Any]) -> "BackendCatalogItem":
        return BackendCatalogItem(
            name=item.get("name") or "",
            source_code=item.get("sourceCode") or item.get("source_code") or "",
            source_name=item.get("sourceName") or item.get("source_name") or "",
            category=item.get("category"),
            material=item.get("material"),
            price=item.get("price"),
            currency=item.get("currency"),
            source_url=item.get("sourceUrl") or item.get("source_url"),
            image_url=item.get("imageUrl") or item.get("image_url"),
            dimensions_text=item.get("dimensionsText") or item.get("dimensions_text"),
            description=item.get("description"),
            score=item.get("score", 0.0),
            score_reasons=item.get("scoreReasons") or item.get("score_reasons") or [],
        )


class BackendGeneralCatalogProvider:
    """Catalog provider using backend internal search API.

    - Luôn gọi với role=USER (không cho override từ input).
    - Gửi header X-Internal-Api-Key nếu env INTERNAL_API_SECRET được set.
    - 401/403 → log + fallback, không retry với role admin.
    """

    provider_name = "backend_general_catalog"

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or BACKEND_BASE_URL).rstrip("/")
        self.timeout = INTERNAL_SEARCH_TIMEOUT
        self.default_limit = INTERNAL_SEARCH_LIMIT
        self._internal_secret = _INTERNAL_API_SECRET

    def search_candidates(
        self,
        query: str,
        limit: int = 5,
        mode: str = "GENERAL_COMPARE",
    ) -> List[BackendCatalogItem]:
        """Search general products. Role/user luôn là USER để tránh leak."""
        if not query or not query.strip():
            return []

        params = {
            "q": query.strip(),
            "mode": mode,
            "role": "USER",
            "limit": str(max(1, min(limit, 20))),
        }

        try:
            resp = requests.get(
                f"{self.base_url}/api/internal/general-products/search",
                params=params,
                timeout=self.timeout,
                headers=self._build_headers(),
            )
        except requests.exceptions.Timeout:
            _logger.warning("BackendGeneralCatalogProvider timeout after %ss", self.timeout)
            return []
        except requests.exceptions.ConnectionError as e:
            _logger.warning("BackendGeneralCatalogProvider connection error: %s", e)
            return []
        except requests.exceptions.RequestException as e:
            _logger.warning("BackendGeneralCatalogProvider request error: %s", e)
            return []

        if resp.status_code == 401 or resp.status_code == 403:
            _logger.warning(
                "BackendGeneralCatalogProvider auth error %d (secret set=%s). "
                "Falling back to no public data.",
                resp.status_code,
                "yes" if bool(self._internal_secret) else "no",
            )
            return []

        if resp.status_code != 200:
            _logger.warning(
                "BackendGeneralCatalogProvider unexpected status %d: %s",
                resp.status_code,
                resp.text[:200],
            )
            return []

        try:
            data = resp.json()
        except Exception as e:
            _logger.warning("BackendGeneralCatalogProvider JSON parse error: %s", e)
            return []

        items_raw = data.get("items") or data.get("products") or []
        if not items_raw:
            return []

        items = []
        for item in items_raw:
            try:
                items.append(BackendCatalogItem.from_api_item(item))
            except Exception as e:
                _logger.debug("Skipping item parse error: %s", e)
        return items

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._internal_secret:
            headers["X-Internal-Api-Key"] = self._internal_secret
        return headers


def build_backend_catalog_provider() -> BackendGeneralCatalogProvider:
    return BackendGeneralCatalogProvider()


def format_backend_catalog_items(items: List[BackendCatalogItem]) -> str:
    """Format catalog items for LLM context."""
    if not items:
        return "(no products found in public catalog)"

    lines = [
        "BACKEND GENERAL PRODUCT CATALOG RESULTS "
        "(from general_products DB, ranked by relevance):"
    ]
    for i, item in enumerate(items, 1):
        parts = [f"{i}. {item.name}"]
        if item.price is not None:
            currency = item.currency or "VND"
            parts.append(f"Gia: {item.price:,.0f} {currency}".replace(",", "."))
        if item.material:
            parts.append(f"Chat lieu: {item.material}")
        if item.category:
            parts.append(f"Danh muc: {item.category}")
        if item.source_name:
            parts.append(f"Nguon: {item.source_name}")
        if item.source_url:
            parts.append(f"Link: {item.source_url}")
        if item.score_reasons:
            parts.append(f"Ly do phu hop: {', '.join(item.score_reasons)}")
        lines.append(" | ".join(parts))

    return "\n".join(lines)
