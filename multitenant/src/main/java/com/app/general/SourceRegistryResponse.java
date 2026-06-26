package com.app.general;

import java.time.Instant;
import java.util.UUID;

public record SourceRegistryResponse(
        UUID id,
        String sourceCode,
        String sourceName,
        String rootUrl,
        String sitemapUrl,
        String domain,
        String visibility,
        String ownerTenantId,
        boolean enabled,
        String notes,
        Instant createdAt,
        Instant updatedAt
) {
    static SourceRegistryResponse from(SourceRegistry entity) {
        return new SourceRegistryResponse(
                entity.getId(),
                entity.getSourceCode(),
                entity.getSourceName(),
                entity.getRootUrl(),
                entity.getSitemapUrl(),
                entity.getDomain(),
                entity.getVisibility(),
                entity.getOwnerTenantId() != null ? entity.getOwnerTenantId().toString() : null,
                entity.isEnabled(),
                entity.getNotes(),
                entity.getCreatedAt(),
                entity.getUpdatedAt()
        );
    }
}
