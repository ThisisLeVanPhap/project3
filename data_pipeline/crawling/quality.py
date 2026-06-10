from dataclasses import dataclass, field

from data_pipeline.crawling.schema import ProductObservation


@dataclass
class ProductQualityResult:
    quality: str
    missing_fields: list[str] = field(default_factory=list)


def evaluate_product_quality(
    observation: ProductObservation,
    require_tenant: bool = False,
) -> ProductQualityResult:
    """Evaluate whether a product observation is ready enough for KB/RAG ingestion."""
    missing_fields = _missing_fields(observation, require_tenant=require_tenant)

    if "product_name" in missing_fields or "source_url" in missing_fields:
        return ProductQualityResult(quality="low", missing_fields=missing_fields)
    if require_tenant and "tenant_id" in missing_fields:
        return ProductQualityResult(quality="low", missing_fields=missing_fields)

    descriptive_fields = (
        observation.description,
        observation.category,
        observation.material,
        observation.dimensions,
    )
    has_descriptive_field = any(bool(value) for value in descriptive_fields)

    if observation.price is not None and has_descriptive_field:
        if observation.image_urls:
            return ProductQualityResult(quality="high", missing_fields=missing_fields)
        return ProductQualityResult(quality="medium", missing_fields=missing_fields)

    return ProductQualityResult(quality="medium", missing_fields=missing_fields)


def _missing_fields(observation: ProductObservation, require_tenant: bool) -> list[str]:
    missing: list[str] = []
    if require_tenant and not observation.tenant_id:
        missing.append("tenant_id")
    if not observation.product_name:
        missing.append("product_name")
    if not observation.source_url:
        missing.append("source_url")
    if observation.price is None:
        missing.append("price")
    if not observation.image_urls:
        missing.append("image_urls")
    if not any((observation.description, observation.category, observation.material, observation.dimensions)):
        missing.append("descriptive_fields")
    return missing
