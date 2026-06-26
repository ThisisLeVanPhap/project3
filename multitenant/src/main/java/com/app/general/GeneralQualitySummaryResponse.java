package com.app.general;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

public record GeneralQualitySummaryResponse(
        long totalProducts,
        long sourceCount,
        Map<String, CoverageMetric> coverage,
        String qualityStatus,
        List<CategoryDist> categoryDistribution,
        PriceStats priceStats,
        List<SourceBreakdown> sourceBreakdown,
        List<String> warnings
) {
    public record CoverageMetric(long count, double percent) {}

    public record CategoryDist(String category, long count) {}

    public record PriceStats(BigDecimal min, BigDecimal median, BigDecimal avg, BigDecimal max) {}

    public record SourceBreakdown(
            String sourceCode,
            long totalProducts,
            double priceCoverage,
            double categoryCoverage,
            double materialCoverage,
            double dimensionsCoverage
    ) {}
}
