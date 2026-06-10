package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.UUID;

public record ResolvedTenantKbDirectory(
        @JsonProperty("tenant_id")
        UUID tenantId,
        @JsonProperty("kb_dir")
        String kbDir,
        TenantKbDirectorySource source,
        @JsonProperty("version_id")
        UUID versionId,
        @JsonProperty("version_tag")
        String versionTag,
        @JsonProperty("fallback_reason")
        String fallbackReason
) {
}
