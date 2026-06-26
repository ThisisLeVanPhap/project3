package com.app.general;

import java.util.List;

public record CrawlAndMaterializeRequest(
        String sourceCode,
        String sourceName,
        String rootUrl,
        String sitemapUrl,
        List<String> productUrls,
        String datasetId,
        Integer maxUrls,
        Boolean productOnly,
        Boolean runQualityAudit,
        Boolean runTaxonomyNormalize,
        Boolean registerDataset,
        Boolean buildArtifact,
        Boolean importGeneral,
        String bindTenantId,
        String visibility
) {
    public int getMaxUrlsOrDefault() {
        return maxUrls != null && maxUrls > 0 ? Math.min(maxUrls, 50000) : 1000;
    }

    public boolean isProductOnly() {
        return productOnly == null || productOnly;
    }

    public boolean isRunQualityAudit() {
        return runQualityAudit == null || runQualityAudit;
    }

    public boolean isRunTaxonomyNormalize() {
        return runTaxonomyNormalize != null && runTaxonomyNormalize;
    }

    public boolean isRegisterDataset() {
        return registerDataset == null || registerDataset;
    }

    public boolean isBuildArtifact() {
        return buildArtifact != null && buildArtifact;
    }

    public boolean isBindTenant() {
        return bindTenantId != null && !bindTenantId.isBlank();
    }

    public boolean isImportGeneral() {
        return importGeneral != null && importGeneral;
    }

    public String getVisibilityOrDefault() {
        if (visibility != null && !visibility.isBlank()) {
            String v = visibility.trim().toUpperCase();
            if (List.of("GLOBAL_PUBLIC", "TENANT_BOUND", "PRIVATE", "ADMIN_ONLY").contains(v)) {
                return v;
            }
        }
        return "TENANT_BOUND";
    }
}
