package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.UUID;

public record TenantKbBindingResponse(
        UUID id,
        @JsonProperty("tenant_id")
        UUID tenantId,
        @JsonProperty("artifact_id")
        UUID artifactId,
        @JsonProperty("dataset_id")
        String datasetId,
        boolean active,
        @JsonProperty("update_policy")
        TenantKbBindingUpdatePolicy updatePolicy,
        @JsonProperty("active_kb_version_id")
        UUID activeKbVersionId,
        @JsonProperty("bound_at")
        Instant boundAt,
        @JsonProperty("unbound_at")
        Instant unboundAt,
        @JsonProperty("created_at")
        Instant createdAt,
        @JsonProperty("updated_at")
        Instant updatedAt
) {
    static TenantKbBindingResponse from(TenantKbBinding binding) {
        return new TenantKbBindingResponse(
                binding.getId(),
                binding.getTenantId(),
                binding.getArtifactId(),
                binding.getDatasetId(),
                binding.isActive(),
                binding.getUpdatePolicy(),
                binding.getActiveKbVersionId(),
                binding.getBoundAt(),
                binding.getUnboundAt(),
                binding.getCreatedAt(),
                binding.getUpdatedAt()
        );
    }
}
