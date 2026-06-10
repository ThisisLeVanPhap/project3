from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CrawlSource:
    """Simple crawl source config for a fixed list of product URLs."""

    name: str
    start_urls: list[str]
    tenant_id: Optional[str] = None
    allowed_domains: list[str] = field(default_factory=list)
    selectors: dict[str, list[str]] = field(default_factory=dict)
    max_pages: int = 20
    output_path: str = "data_pipeline/output/products.jsonl"
    metadata: dict[str, Any] = field(default_factory=dict)
