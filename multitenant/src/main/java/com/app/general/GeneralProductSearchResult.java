package com.app.general;

import java.math.BigDecimal;
import java.util.List;
import java.util.Set;
import java.util.UUID;

public record GeneralProductSearchResult(
        String query,
        String mode,
        GeneralScope scope,
        int totalCandidates,
        List<SearchResultItem> items
) {
    public record SearchResultItem(
            UUID id,
            String sourceCode,
            String sourceName,
            String name,
            String category,
            String productType,
            String material,
            BigDecimal price,
            BigDecimal originalPrice,
            String currency,
            String sourceUrl,
            String imageUrl,
            String dimensionsText,
            String description,
            String visibility,
            double score,
            List<String> scoreReasons
    ) {}
}

class SearchCriteria {
    final String q;
    final String mode;
    final UUID tenantId;
    final String role;
    final String category;
    final String material;
    final BigDecimal minPrice;
    final BigDecimal maxPrice;
    final String sourceCode;
    final int limit;
    final int offset;

    SearchCriteria(String q, String mode, UUID tenantId, String role,
                   String category, String material,
                   BigDecimal minPrice, BigDecimal maxPrice,
                   String sourceCode, int limit, int offset) {
        this.q = q;
        this.mode = mode;
        this.tenantId = tenantId;
        this.role = role;
        this.category = category;
        this.material = material;
        this.minPrice = minPrice;
        this.maxPrice = maxPrice;
        this.sourceCode = sourceCode;
        this.limit = Math.min(Math.max(1, limit), 20);
        this.offset = Math.max(0, offset);
    }
}
