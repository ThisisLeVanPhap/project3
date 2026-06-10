package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.UUID;

public record ProductDatasetAssignResponse(
        boolean success,
        @JsonProperty("dataset_id")
        String datasetId,
        @JsonProperty("tenant_id")
        UUID tenantId,
        @JsonProperty("tenant_code")
        String tenantCode,
        @JsonProperty("kb_dir")
        String kbDir,
        @JsonProperty("chunk_count")
        Integer chunkCount,
        @JsonProperty("kb_version_id")
        UUID kbVersionId,
        @JsonProperty("version_tag")
        String versionTag,
        @JsonProperty("assigned_at")
        Instant assignedAt,
        String message
) {
}
