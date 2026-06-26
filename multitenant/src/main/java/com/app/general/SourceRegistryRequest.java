package com.app.general;

import java.util.List;

public record SourceRegistryRequest(
        String sourceCode,
        String sourceName,
        String rootUrl,
        String sitemapUrl,
        String visibility,
        String ownerTenantId,
        List<String> productUrlPatterns,
        List<String> excludePatterns,
        Boolean enabled,
        String notes
) {}
