package com.app.general;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class GeneralQualitySummaryService {

    private static final Logger log = LoggerFactory.getLogger(GeneralQualitySummaryService.class);

    private final JdbcTemplate jdbcTemplate;

    public GeneralQualitySummaryService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public GeneralQualitySummaryResponse getSummary(String sourceCode, String sourceId) {
        // Build filter clause
        StringBuilder filter = new StringBuilder("");
        List<Object> params = new ArrayList<>();

        if (sourceCode != null && !sourceCode.isBlank()) {
            filter.append(" AND s.source_code ILIKE ?");
            params.add(sourceCode.trim());
        }
        if (sourceId != null && !sourceId.isBlank()) {
            filter.append(" AND s.id = ?::uuid");
            params.add(sourceId.trim());
        }

        String filterStr = filter.toString();

        // Total products & sources
        String countSql = "SELECT COUNT(*), COUNT(DISTINCT s.source_code) FROM general_products p " +
                "JOIN general_sources s ON p.general_source_id = s.id WHERE 1=1 AND p.status = 'ACTIVE'" + filterStr;
        List<Object[]> totals = jdbcTemplate.query(countSql, params.toArray(), (rs, row) ->
                new Object[]{rs.getLong(1), rs.getLong(2)});
        long totalProducts = totals.isEmpty() ? 0 : (long) totals.get(0)[0];
        long sourceCount = totals.isEmpty() ? 0 : (long) totals.get(0)[1];

        // Coverage metrics
        Map<String, GeneralQualitySummaryResponse.CoverageMetric> coverage = new LinkedHashMap<>();
        coverage.put("price", calcCoverage("p.price IS NOT NULL AND p.price > 0", filterStr, params));
        coverage.put("category", calcCoverage("p.category IS NOT NULL", filterStr, params));
        coverage.put("material", calcCoverage("p.material IS NOT NULL", filterStr, params));
        coverage.put("dimensions", calcCoverage("p.dimensions_text IS NOT NULL", filterStr, params));
        coverage.put("imageUrl", calcCoverage("p.image_url IS NOT NULL", filterStr, params));
        coverage.put("sourceUrl", calcCoverage("p.source_url IS NOT NULL", filterStr, params));

        // Quality status
        String qualityStatus = calcQualityStatus(coverage, totalProducts);

        // Category distribution (top 15)
        List<GeneralQualitySummaryResponse.CategoryDist> categoryDist = fetchCategoryDistribution(filterStr, params);

        // Price stats
        GeneralQualitySummaryResponse.PriceStats priceStats = fetchPriceStats(filterStr, params);

        // Source breakdown
        List<GeneralQualitySummaryResponse.SourceBreakdown> sourceBreakdown = fetchSourceBreakdown(filterStr, params);

        // Warnings
        List<String> warnings = buildWarnings(coverage, totalProducts, sourceCount);

        return new GeneralQualitySummaryResponse(totalProducts, sourceCount, coverage,
                qualityStatus, categoryDist, priceStats, sourceBreakdown, warnings);
    }

    private GeneralQualitySummaryResponse.CoverageMetric calcCoverage(String condition, String filter, List<Object> baseParams) {
        String sql = "SELECT COUNT(*) FROM general_products p JOIN general_sources s ON p.general_source_id = s.id WHERE " + condition + " AND 1=1" + filter;
        List<Object> allParams = new ArrayList<>(baseParams);
        long count = jdbcTemplate.queryForObject(sql, Long.class, allParams.toArray());
        long total = getTotal(baseParams);
        double percent = total > 0 ? BigDecimal.valueOf(count * 100.0 / total).setScale(1, RoundingMode.HALF_UP).doubleValue() : 0.0;
        return new GeneralQualitySummaryResponse.CoverageMetric(count, percent);
    }

    private long getTotal(List<Object> baseParams) {
        String sql = "SELECT COUNT(*) FROM general_products p JOIN general_sources s ON p.general_source_id = s.id WHERE p.status = 'ACTIVE'";
        if (baseParams.isEmpty()) {
            Long result = jdbcTemplate.queryForObject(sql, Long.class);
            return result != null ? result : 0;
        }
        // Re-execute with proper params — simplified for static filter
        String fullSql = sql + " AND s.source_code ILIKE ?";
        if (baseParams.size() == 1) {
            Long result = jdbcTemplate.queryForObject(fullSql, Long.class, baseParams.get(0));
            return result != null ? result : 0;
        }
        Long result = jdbcTemplate.queryForObject(sql, Long.class);
        return result != null ? result : 0;
    }

    private String calcQualityStatus(Map<String, GeneralQualitySummaryResponse.CoverageMetric> coverage, long totalProducts) {
        if (totalProducts == 0) return "fail";
        double priceCov = coverage.getOrDefault("price", new GeneralQualitySummaryResponse.CoverageMetric(0, 0)).percent();
        double catCov = coverage.getOrDefault("category", new GeneralQualitySummaryResponse.CoverageMetric(0, 0)).percent();
        double urlCov = coverage.getOrDefault("sourceUrl", new GeneralQualitySummaryResponse.CoverageMetric(0, 0)).percent();

        if (priceCov >= 80 && catCov >= 80 && urlCov >= 95) return "pass";
        if (priceCov < 30 || urlCov < 50) return "fail";
        return "warn";
    }

    private List<GeneralQualitySummaryResponse.CategoryDist> fetchCategoryDistribution(String filter, List<Object> params) {
        String sql = "SELECT p.category, COUNT(*) AS cnt FROM general_products p " +
                "JOIN general_sources s ON p.general_source_id = s.id " +
                "WHERE 1=1 AND p.status = 'ACTIVE'" + filter + " AND p.category IS NOT NULL " +
                "GROUP BY p.category ORDER BY cnt DESC LIMIT 15";
        return jdbcTemplate.query(sql, params.toArray(), (rs, row) ->
                new GeneralQualitySummaryResponse.CategoryDist(
                        rs.getString("category"), rs.getLong("cnt")));
    }

    private GeneralQualitySummaryResponse.PriceStats fetchPriceStats(String filter, List<Object> params) {
        String sql = "SELECT MIN(p.price) AS min_p, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.price) AS med, " +
                "AVG(p.price) AS avg_p, MAX(p.price) AS max_p " +
                "FROM general_products p JOIN general_sources s ON p.general_source_id = s.id " +
                "WHERE 1=1 AND p.status = 'ACTIVE'" + filter + " AND p.price IS NOT NULL AND p.price > 0";
        List<GeneralQualitySummaryResponse.PriceStats> stats = jdbcTemplate.query(sql, params.toArray(), (rs, row) -> {
            BigDecimal min = rs.getBigDecimal("min_p");
            BigDecimal med = rs.getBigDecimal("med");
            BigDecimal avg = rs.getBigDecimal("avg_p");
            BigDecimal max = rs.getBigDecimal("max_p");
            return new GeneralQualitySummaryResponse.PriceStats(min, med, avg, max);
        });
        return stats.isEmpty() ? new GeneralQualitySummaryResponse.PriceStats(null, null, null, null) : stats.get(0);
    }

    private List<GeneralQualitySummaryResponse.SourceBreakdown> fetchSourceBreakdown(String filter, List<Object> params) {
        String sql = "SELECT s.source_code, COUNT(*) AS total, " +
                "SUM(CASE WHEN p.price IS NOT NULL AND p.price > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS price_cov, " +
                "SUM(CASE WHEN p.category IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS cat_cov, " +
                "SUM(CASE WHEN p.material IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS mat_cov, " +
                "SUM(CASE WHEN p.dimensions_text IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS dim_cov " +
                "FROM general_products p JOIN general_sources s ON p.general_source_id = s.id " +
                "WHERE 1=1 AND p.status = 'ACTIVE'" + filter + " GROUP BY s.source_code ORDER BY total DESC";
        return jdbcTemplate.query(sql, params.toArray(), (rs, row) ->
                new GeneralQualitySummaryResponse.SourceBreakdown(
                        rs.getString("source_code"),
                        rs.getLong("total"),
                        roundPct(rs.getDouble("price_cov")),
                        roundPct(rs.getDouble("cat_cov")),
                        roundPct(rs.getDouble("mat_cov")),
                        roundPct(rs.getDouble("dim_cov"))
                ));
    }

    private List<String> buildWarnings(Map<String, GeneralQualitySummaryResponse.CoverageMetric> coverage,
                                        long totalProducts, long sourceCount) {
        List<String> warnings = new ArrayList<>();
        if (totalProducts == 0) warnings.add("No products found");
        if (sourceCount == 0) warnings.add("No sources found");
        var mat = coverage.get("material");
        if (mat != null && mat.percent() < 80) {
            long missing = totalProducts - mat.count();
            warnings.add("material coverage " + mat.percent() + "% — " + missing + " products missing material");
        }
        var dim = coverage.get("dimensions");
        if (dim != null && dim.percent() < 80) {
            long missing = totalProducts - dim.count();
            warnings.add("dimensions coverage " + dim.percent() + "% — " + missing + " products missing dimensions");
        }
        var cat = coverage.get("category");
        if (cat != null && cat.percent() < 80) {
            long missing = totalProducts - cat.count();
            warnings.add("category coverage " + cat.percent() + "% — " + missing + " products missing category");
        }
        var price = coverage.get("price");
        if (price != null && price.percent() < 80) {
            long missing = totalProducts - price.count();
            warnings.add("price coverage " + price.percent() + "% — " + missing + " products missing price");
        }
        return warnings;
    }

    private double roundPct(double value) {
        return BigDecimal.valueOf(value).setScale(1, RoundingMode.HALF_UP).doubleValue();
    }
}
