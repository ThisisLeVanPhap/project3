package com.app.general;

import com.app.auth.AppRole;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class MarketPriceInsightService {

    private static final Logger log = LoggerFactory.getLogger(MarketPriceInsightService.class);

    private final JdbcTemplate jdbcTemplate;
    private final GeneralScopeResolver scopeResolver;

    public MarketPriceInsightService(JdbcTemplate jdbcTemplate, GeneralScopeResolver scopeResolver) {
        this.jdbcTemplate = jdbcTemplate;
        this.scopeResolver = scopeResolver;
    }

    public MarketPriceInsightResponse getInsight(MarketPriceInsightRequest req) {
        // Resolve scope
        GeneralScope scope = scopeResolver.resolve("market_price", req.tenantId(), parseRole(req.role()));
        if (!scope.canQueryGeneralProducts()) {
            return emptyResponse(req, scope, "Access denied");
        }

        // Extract filters from query
        String category = req.category() != null ? req.category() : extractCategory(req.q());
        String material = req.material() != null ? req.material() : extractMaterial(req.q());
        BigDecimal inputPrice = req.inputPrice();
        if (inputPrice == null && req.q() != null) {
            inputPrice = extractInputPrice(req.q());
        }

        if (category == null && material == null) {
            return emptyResponse(req, scope, "Please specify a product category like sofa, tủ, bàn...");
        }

        // Build query
        List<Object> params = new ArrayList<>();
        StringBuilder sql = new StringBuilder();
        sql.append("""
            SELECT MIN(p.price) AS min_p, PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY p.price) AS p25,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.price) AS med,
                   PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY p.price) AS p75,
                   MAX(p.price) AS max_p, COUNT(*) AS cnt,
                   COUNT(DISTINCT s.source_code) AS src_cnt
            FROM general_products p
            JOIN general_sources s ON p.general_source_id = s.id
            WHERE p.price IS NOT NULL AND p.price > 0 AND p.status = 'ACTIVE'
        """);

        // Visibility scope
        List<String> visPlaceholders = new ArrayList<>();
        for (SourceVisibility vis : scope.allowedVisibilities()) {
            visPlaceholders.add("?");
            params.add(vis.name());
        }
        if (!visPlaceholders.isEmpty()) {
            sql.append(" AND p.visibility IN (").append(String.join(",", visPlaceholders)).append(")");
        }
        if (scope.requireOwnerTenant() && scope.ownerTenantId() != null) {
            sql.append(" AND (p.visibility != 'TENANT_BOUND' OR s.tenant_id = ?)");
            params.add(scope.ownerTenantId().toString());
        }

        if (category != null) {
            sql.append(" AND (p.category ILIKE ? OR p.product_type ILIKE ?)");
            params.add("%" + category + "%");
            params.add("%" + category + "%");
        }
        if (material != null) {
            sql.append(" AND p.material ILIKE ?");
            params.add("%" + material + "%");
        }
        if (req.sourceCode() != null && !req.sourceCode().isBlank()) {
            sql.append(" AND s.source_code ILIKE ?");
            params.add(req.sourceCode().trim());
        }

        // Execute aggregate
        List<MarketPriceInsightResponse.Stats> statsResult = jdbcTemplate.query(sql.toString(), params.toArray(), (ResultSet rs, int rowNum) -> {
            BigDecimal min = rs.getBigDecimal("min_p");
            BigDecimal p25 = rs.getBigDecimal("p25");
            BigDecimal med = rs.getBigDecimal("med");
            BigDecimal p75 = rs.getBigDecimal("p75");
            BigDecimal max = rs.getBigDecimal("max_p");
            int cnt = rs.getInt("cnt");
            int srcCnt = rs.getInt("src_cnt");
            return new MarketPriceInsightResponse.Stats(min, p25, med, p75, max, cnt, srcCnt, "VND", calcConfidence(cnt, srcCnt));
        });

        if (statsResult.isEmpty() || statsResult.get(0).sampleCount() == 0) {
            return emptyResponse(req, scope, "No price data available for " + (category != null ? category : "this category"));
        }

        MarketPriceInsightResponse.Stats stats = statsResult.get(0);

        // Samples
        List<MarketPriceInsightResponse.SampleItem> samples = fetchSamples(category, material, req.sourceCode(), scope, stats.medianPrice());

        // Assessment
        MarketPriceInsightResponse.Assessment assessment = null;
        if (inputPrice != null && stats.minPrice() != null && stats.maxPrice() != null) {
            assessment = assessPrice(inputPrice, stats);
        }

        return new MarketPriceInsightResponse(req.q(), category, material, inputPrice, scope, stats, samples, assessment);
    }

    private List<MarketPriceInsightResponse.SampleItem> fetchSamples(String category, String material, String sourceCode, GeneralScope scope, BigDecimal medianPrice) {
        List<Object> params = new ArrayList<>();
        StringBuilder sql = new StringBuilder();
        sql.append("""
            SELECT p.id, p.name, p.price, s.source_name, p.source_url, p.material, p.category, s.source_code
            FROM general_products p
            JOIN general_sources s ON p.general_source_id = s.id
            WHERE p.price IS NOT NULL AND p.price > 0 AND p.status = 'ACTIVE'
        """);

        List<String> visPlaceholders = new ArrayList<>();
        for (SourceVisibility vis : scope.allowedVisibilities()) {
            visPlaceholders.add("?");
            params.add(vis.name());
        }
        if (!visPlaceholders.isEmpty()) {
            sql.append(" AND p.visibility IN (").append(String.join(",", visPlaceholders)).append(")");
        }
        if (scope.requireOwnerTenant() && scope.ownerTenantId() != null) {
            sql.append(" AND (p.visibility != 'TENANT_BOUND' OR s.tenant_id = ?)");
            params.add(scope.ownerTenantId().toString());
        }

        if (category != null) {
            sql.append(" AND (p.category ILIKE ? OR p.product_type ILIKE ?)");
            params.add("%" + category + "%");
            params.add("%" + category + "%");
        }
        if (material != null) {
            sql.append(" AND p.material ILIKE ?");
            params.add("%" + material + "%");
        }
        if (sourceCode != null && !sourceCode.isBlank()) {
            sql.append(" AND s.source_code ILIKE ?");
            params.add(sourceCode.trim());
        }

        // Order by price closest to median
        if (medianPrice != null) {
            sql.append(" ORDER BY ABS(p.price - ?)");
            params.add(medianPrice);
        } else {
            sql.append(" ORDER BY p.price");
        }
        sql.append(" LIMIT 5");

        return jdbcTemplate.query(sql.toString(), params.toArray(), (ResultSet rs, int rowNum) -> {
            UUID id = UUID.fromString(rs.getString("id"));
            return new MarketPriceInsightResponse.SampleItem(
                    id, rs.getString("name"), rs.getBigDecimal("price"),
                    rs.getString("source_name"), rs.getString("source_url"),
                    rs.getString("material"), rs.getString("category"),
                    rs.getString("source_code")
            );
        });
    }

    private String calcConfidence(int sampleCount, int sourceCount) {
        if (sampleCount >= 50 && sourceCount >= 2) return "HIGH";
        if (sampleCount >= 15) return "MEDIUM";
        if (sampleCount >= 5) return "LOW";
        return "INSUFFICIENT";
    }

    MarketPriceInsightResponse.Assessment assessPrice(BigDecimal inputPrice, MarketPriceInsightResponse.Stats stats) {
        String position;
        String label;
        int cmp = inputPrice.compareTo(stats.p25Price());
        int cmpMed = inputPrice.compareTo(stats.medianPrice());
        int cmpP75 = inputPrice.compareTo(stats.p75Price());
        int cmpMax = inputPrice.compareTo(stats.maxPrice());

        if (cmp < 0) {
            position = "below_p25";
            label = "khá thấp so với mặt bằng mẫu";
        } else if (cmpMed < 0) {
            position = "between_p25_and_median";
            label = "thấp hơn trung vị";
        } else if (cmpP75 <= 0) {
            position = "between_median_and_p75";
            label = "nằm trong khoảng phổ biến";
        } else if (cmpMax <= 0) {
            position = "between_p75_and_max";
            label = "hơi cao nhưng vẫn trong khoảng quan sát";
        } else {
            position = "above_max";
            label = "cao hơn mẫu hiện có";
        }
        return new MarketPriceInsightResponse.Assessment(inputPrice, position, label);
    }

    // --- Query understanding ---

    String extractCategory(String q) {
        if (q == null || q.isBlank()) return null;
        String lower = q.toLowerCase(Locale.ROOT).trim();
        // Reuse same logic from GeneralProductSearchService
        if (lower.contains("sofa") || lower.contains("ghế sofa") || lower.contains("ghế")) return "Sofa";
        if (lower.contains("tủ quần áo") || lower.contains("tủ áo") || lower.contains("tủ")) return "Tủ";
        if (lower.contains("bàn làm việc")) return "Bàn làm việc";
        if (lower.contains("bàn ăn")) return "Bàn ăn";
        if (lower.contains("bàn trà")) return "Bàn trà";
        if (lower.contains("bàn")) return "Bàn";
        if (lower.contains("giường")) return "Giường";
        if (lower.contains("kệ tivi") || lower.contains("kệ sách") || lower.contains("kệ")) return "Kệ";
        if (lower.contains("đèn")) return "Đèn";
        if (lower.contains("rèm")) return "Rèm";
        if (lower.contains("gương")) return "Gương";
        if (lower.contains("thảm")) return "Thảm";
        if (lower.contains("tranh")) return "Tranh";
        return null;
    }

    String extractMaterial(String q) {
        if (q == null || q.isBlank()) return null;
        String lower = q.toLowerCase(Locale.ROOT).trim();
        if (lower.contains("vải")) return "vải";
        if (lower.contains("da")) return "da";
        if (lower.contains("gỗ sồi")) return "gỗ sồi";
        if (lower.contains("mdf")) return "MDF";
        if (lower.contains("gỗ công nghiệp")) return "gỗ công nghiệp";
        if (lower.contains("gỗ")) return "gỗ";
        if (lower.contains("kim loại")) return "kim loại";
        if (lower.contains("kính")) return "kính";
        if (lower.contains("mây")) return "mây";
        return null;
    }

    BigDecimal extractInputPrice(String q) {
        if (q == null || q.isBlank()) return null;
        String lower = q.toLowerCase(Locale.ROOT).trim();
        // Match price patterns: X triệu, Xtr, X.Y00.000đ, X.000.000
        Pattern p = Pattern.compile("(\\d+(?:[.,]\\d+)?)\\s*(?:triệu|tr|tr\\.)");
        Matcher m = p.matcher(lower);
        if (m.find()) {
            return new BigDecimal(m.group(1).replace(",", ".")).multiply(new BigDecimal("1000000"));
        }
        return null;
    }

    private AppRole parseRole(String role) {
        if (role == null || role.isBlank()) return null;
        try { return AppRole.valueOf(role.trim().toUpperCase()); }
        catch (IllegalArgumentException e) { return null; }
    }

    private MarketPriceInsightResponse emptyResponse(MarketPriceInsightRequest req, GeneralScope scope, String reason) {
        return new MarketPriceInsightResponse(
                req != null ? req.q() : null, null, null, null, scope,
                new MarketPriceInsightResponse.Stats(null, null, null, null, null, 0, 0, "VND", "INSUFFICIENT"),
                List.of(), null
        );
    }

    record MarketPriceInsightRequest(String q, String mode, UUID tenantId, String role,
                                      String category, String material, BigDecimal inputPrice,
                                      String sourceCode, int limitSamples) {}
}
