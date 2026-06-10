package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.UUID;

public record TenantKbVersionResponse(
        UUID id,
        @JsonProperty("tenant_id")
        UUID tenantId,
        @JsonProperty("version_tag")
        String versionTag,
        @JsonProperty("kb_dir")
        String kbDir,
        @JsonProperty("source_type")
        String sourceType,
        @JsonProperty("dataset_id")
        String datasetId,
        TenantKbVersionStatus status,
        @JsonProperty("artifact_count")
        Integer artifactCount,
        @JsonProperty("build_message")
        String buildMessage,
        @JsonProperty("built_at")
        Instant builtAt,
        @JsonProperty("published_at")
        Instant publishedAt,
        @JsonProperty("created_at")
        Instant createdAt,
        boolean active
) {

    static TenantKbVersionResponse from(TenantKbVersion version, UUID activeKbVersionId) {
        return new TenantKbVersionResponse(
                version.getId(),
                version.getTenantId(),
                version.getVersionTag(),
                version.getKbDir(),
                version.getSourceType(),
                version.getDatasetId(),
                version.getStatus(),
                version.getArtifactCount(),
                version.getBuildMessage(),
                version.getBuiltAt(),
                version.getPublishedAt(),
                version.getCreatedAt(),
                version.getId() != null && version.getId().equals(activeKbVersionId)
        );
    }
}
