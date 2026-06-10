package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.UUID;

public record ProductDatasetResponse(
        UUID id,
        @JsonProperty("dataset_id")
        String datasetId,
        String source,
        @JsonProperty("source_url")
        String sourceUrl,
        String version,
        String path,
        @JsonProperty("product_count")
        Integer productCount,
        @JsonProperty("rag_chunk_count")
        Integer ragChunkCount,
        @JsonProperty("content_hash")
        String contentHash,
        @JsonProperty("manifest_path")
        String manifestPath,
        @JsonProperty("created_at")
        Instant createdAt,
        @JsonProperty("registered_at")
        Instant registeredAt,
        ProductDatasetStatus status,
        @JsonProperty("last_assigned_tenant_id")
        UUID lastAssignedTenantId,
        @JsonProperty("last_assigned_at")
        Instant lastAssignedAt
) {
    static ProductDatasetResponse from(ProductDataset dataset) {
        return new ProductDatasetResponse(
                dataset.getId(),
                dataset.getDatasetId(),
                dataset.getSource(),
                dataset.getSourceUrl(),
                dataset.getVersion(),
                dataset.getPath(),
                dataset.getProductCount(),
                dataset.getRagChunkCount(),
                dataset.getContentHash(),
                dataset.getManifestPath(),
                dataset.getCreatedAt(),
                dataset.getRegisteredAt(),
                dataset.getStatus(),
                dataset.getLastAssignedTenantId(),
                dataset.getLastAssignedAt()
        );
    }
}
