package com.app.general;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

public record MarketPriceInsightResponse(
        String query,
        String category,
        String material,
        BigDecimal inputPrice,
        GeneralScope scope,
        Stats stats,
        List<SampleItem> samples,
        Assessment assessment
) {
    public record Stats(
            BigDecimal minPrice,
            BigDecimal p25Price,
            BigDecimal medianPrice,
            BigDecimal p75Price,
            BigDecimal maxPrice,
            int sampleCount,
            int sourceCount,
            String currency,
            String confidence
    ) {}

    public record SampleItem(
            UUID id,
            String name,
            BigDecimal price,
            String sourceName,
            String sourceUrl,
            String material,
            String category,
            String sourceCode
    ) {}

    public record Assessment(
            BigDecimal inputPrice,
            String position,
            String label
    ) {}
}
