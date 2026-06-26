"""
BackendMarketPriceInsightProvider — goi backend Spring Boot internal market-price insight API
cho mode MARKET_PRICE.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

_logger = logging.getLogger(__name__)

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://app:8080")
MARKET_PRICE_TIMEOUT = int(os.getenv("MARKET_PRICE_TIMEOUT_SECONDS", "10"))
_INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")


@dataclass
class PriceInsight:
    stats: Dict[str, Any]
    samples: List[Dict[str, Any]]
    assessment: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    material: Optional[str] = None


class BackendMarketPriceInsightProvider:
    """Market price insight provider using backend internal API."""

    provider_name = "backend_market_price_insight"

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or BACKEND_BASE_URL).rstrip("/")
        self.timeout = MARKET_PRICE_TIMEOUT
        self._internal_secret = _INTERNAL_API_SECRET

    def get_insight(
        self,
        query: str,
        category: Optional[str] = None,
        material: Optional[str] = None,
        input_price: Optional[float] = None,
    ) -> Optional[PriceInsight]:
        if not query or not query.strip():
            return None

        params: Dict[str, str] = {
            "q": query.strip(),
            "mode": "MARKET_PRICE",
            "role": "USER",
        }
        if category:
            params["category"] = category
        if material:
            params["material"] = material
        if input_price is not None:
            params["inputPrice"] = str(input_price)

        try:
            resp = requests.get(
                f"{self.base_url}/api/internal/market-price/insight",
                params=params,
                timeout=self.timeout,
                headers=self._build_headers(),
            )
        except requests.exceptions.Timeout:
            _logger.warning("MarketPriceInsightProvider timeout after %ss", self.timeout)
            return None
        except requests.exceptions.RequestException as e:
            _logger.warning("MarketPriceInsightProvider request error: %s", e)
            return None

        if resp.status_code in (401, 403):
            _logger.warning("MarketPriceInsightProvider auth error %d", resp.status_code)
            return None
        if resp.status_code != 200:
            _logger.warning("MarketPriceInsightProvider status %d", resp.status_code)
            return None

        try:
            data = resp.json()
        except Exception as e:
            _logger.warning("MarketPriceInsightProvider JSON error: %s", e)
            return None

        stats = data.get("stats") or {}
        samples = data.get("samples") or []
        if stats.get("sampleCount", 0) == 0:
            return None

        return PriceInsight(
            stats=stats,
            samples=samples,
            assessment=data.get("assessment"),
            category=data.get("category"),
            material=data.get("material"),
        )

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._internal_secret:
            headers["X-Internal-Api-Key"] = self._internal_secret
        return headers


def build_market_price_insight_provider() -> BackendMarketPriceInsightProvider:
    return BackendMarketPriceInsightProvider()
