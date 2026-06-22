package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.UUID;

public record TenantKbBindRequest(
        @JsonProperty("tenant_id")
        UUID tenantId,
        @JsonProperty("tenant_code")
        String tenantCode,
        @JsonProperty("artifact_id")
        UUID artifactId,
        @JsonProperty("update_policy")
        TenantKbBindingUpdatePolicy updatePolicy
) {
}
