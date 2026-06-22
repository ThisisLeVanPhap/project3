package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.UUID;

public record TenantKbUnbindRequest(
        @JsonProperty("tenant_id")
        UUID tenantId,
        @JsonProperty("tenant_code")
        String tenantCode
) {
}
