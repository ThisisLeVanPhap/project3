package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.UUID;

public record ProductDatasetAssignRequest(
        @JsonProperty("tenant_code")
        String tenantCode,
        UUID tenantId
) {
}
