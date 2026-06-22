package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.UUID;

public record ProductDatasetArtifactResponse(
        UUID id,
        @JsonProperty("dataset_record_id")
        UUID datasetRecordId,
        @JsonProperty("dataset_id")
        String datasetId,
        @JsonProperty("build_tag")
        String buildTag,
        @JsonProperty("artifact_path")
        String artifactPath,
        @JsonProperty("artifact_count")
        Integer artifactCount,
        @JsonProperty("quality_status")
        String qualityStatus,
        ProductDatasetArtifactStatus status,
        @JsonProperty("build_message")
        String buildMessage,
        @JsonProperty("built_at")
        Instant builtAt,
        @JsonProperty("created_at")
        Instant createdAt
) {
    static ProductDatasetArtifactResponse from(ProductDatasetArtifact artifact) {
        return new ProductDatasetArtifactResponse(
                artifact.getId(),
                artifact.getDatasetRecordId(),
                artifact.getDatasetId(),
                artifact.getBuildTag(),
                artifact.getArtifactPath(),
                artifact.getArtifactCount(),
                artifact.getQualityStatus(),
                artifact.getStatus(),
                artifact.getBuildMessage(),
                artifact.getBuiltAt(),
                artifact.getCreatedAt()
        );
    }
}
