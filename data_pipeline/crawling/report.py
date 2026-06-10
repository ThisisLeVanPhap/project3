import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from data_pipeline.crawling.schema import ProductObservation
from data_pipeline.crawling.source_config import CrawlSource


def build_crawl_report(result, products: list[ProductObservation], source: CrawlSource) -> dict:
    """Build a compact JSON-serializable crawl run report."""
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "run_id": _make_run_id(source.name),
        "source_name": result.source_name,
        "tenant_id": source.tenant_id,
        "generated_at": generated_at,
        "output_path": result.output_path,
        "counts": {
            "fetched_count": result.fetched_count,
            "extracted_count": result.extracted_count,
            "failed_count": result.failed_count,
            "skipped_count": result.skipped_count,
            "quality_high_count": result.quality_high_count,
            "quality_medium_count": result.quality_medium_count,
            "quality_low_count": result.quality_low_count,
        },
        "field_coverage": _field_coverage(products),
        "category_distribution": _counter_dict(item.category for item in products if item.category),
        "extractor_distribution": _counter_dict(item.metadata.get("extractor") for item in products if item.metadata.get("extractor")),
        "data_quality_distribution": _counter_dict(
            item.metadata.get("data_quality") for item in products if item.metadata.get("data_quality")
        ),
        "errors": list(result.errors),
        "sample_products": [_sample_product(item) for item in products[:5]],
    }


def write_crawl_report(report: dict, output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def default_report_path(output_path: str | Path) -> str:
    path = Path(output_path)
    if path.suffix:
        return str(path.with_suffix(f"{path.suffix}.report.json"))
    return str(path.with_name(f"{path.name}.report.json"))


def _field_coverage(products: list[ProductObservation]) -> dict[str, int]:
    return {
        "tenant_id": sum(1 for item in products if item.tenant_id),
        "product_name": sum(1 for item in products if item.product_name),
        "price": sum(1 for item in products if item.price is not None),
        "category": sum(1 for item in products if item.category),
        "material": sum(1 for item in products if item.material),
        "color": sum(1 for item in products if item.color),
        "dimensions": sum(1 for item in products if item.dimensions),
        "brand": sum(1 for item in products if item.brand),
        "image_urls": sum(1 for item in products if item.image_urls),
        "sku": sum(1 for item in products if item.sku),
        "availability": sum(1 for item in products if item.availability),
    }


def _counter_dict(values) -> dict[str, int]:
    return dict(Counter(value for value in values if value))


def _sample_product(item: ProductObservation) -> dict:
    return {
        "product_name": item.product_name,
        "price": item.price,
        "category": item.category,
        "material": item.material,
        "dimensions": item.dimensions,
        "data_quality": item.metadata.get("data_quality"),
        "source_url": item.source_url,
    }


def _make_run_id(source_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{source_name}-{uuid4().hex[:8]}"
