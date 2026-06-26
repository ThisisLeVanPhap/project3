package com.app.general;

import com.app.auth.AppRole;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Service
public class GeneralProductSearchService {

    private static final Logger log = LoggerFactory.getLogger(GeneralProductSearchService.class);

    private final JdbcTemplate jdbcTemplate;
    private final GeneralScopeResolver scopeResolver;

    private static final Set<String> CATEGORY_KEYWORDS = Set.of(
            "sofa", "ghế sofa", "ghế", "tủ", "tủ quần áo", "tủ áo",
            "bàn làm việc", "bàn ăn", "bàn trà", "bàn",
            "giường", "kệ", "kệ tivi", "kệ sách",
            "đèn", "rèm", "gương", "thảm", "tranh"
    );

    private static final Set<String> MATERIAL_KEYWORDS = Set.of(
            "vải", "da", "gỗ", "gỗ sồi", "mdf", "gỗ công nghiệp",
            "kim loại", "kính", "mây", "nhựa", "sắt"
    );

    // Category → canonical category mapping
    private static final Map<String, String> CATEGORY_MAP = new HashMap<>();

    static {
        CATEGORY_MAP.put("sofa", "Sofa");
        CATEGORY_MAP.put("ghế sofa", "Sofa");
        CATEGORY_MAP.put("ghế", "Ghế");
        CATEGORY_MAP.put("tủ", "Tủ");
        CATEGORY_MAP.put("tủ quần áo", "Tủ");
        CATEGORY_MAP.put("tủ áo", "Tủ");
        CATEGORY_MAP.put("bàn làm việc", "Bàn làm việc");
        CATEGORY_MAP.put("bàn ăn", "Bàn ăn");
        CATEGORY_MAP.put("bàn trà", "Bàn trà");
        CATEGORY_MAP.put("bàn", "Bàn");
        CATEGORY_MAP.put("giường", "Giường");
        CATEGORY_MAP.put("kệ", "Kệ");
        CATEGORY_MAP.put("kệ tivi", "Kệ");
        CATEGORY_MAP.put("kệ sách", "Kệ");
        CATEGORY_MAP.put("đèn", "Đèn");
        CATEGORY_MAP.put("rèm", "Rèm");
        CATEGORY_MAP.put("gương", "Gương");
        CATEGORY_MAP.put("thảm", "Thảm");
        CATEGORY_MAP.put("tranh", "Tranh");
        CATEGORY_MAP.put("đồ trang trí", "Đồ trang trí");
    }

    public GeneralProductSearchService(JdbcTemplate jdbcTemplate, GeneralScopeResolver scopeResolver) {
        this.jdbcTemplate = jdbcTemplate;
        this.scopeResolver = scopeResolver;
    }

    public GeneralProductSearchResult search(SearchCriteria criteria) {
        // Resolve scope
        String normalizedMode = normalizeMode(criteria.mode);
        UUID tenantId = criteria.tenantId;
        AppRole role = parseRole(criteria.role);
        GeneralScope scope = scopeResolver.resolve(normalizedMode, tenantId, role);

        if (!scope.canQueryGeneralProducts()) {
            return new GeneralProductSearchResult(criteria.q, normalizedMode, scope, 0, List.of());
        }

        // Extract filters from query if not explicitly provided
        String queryCategory = criteria.category != null ? criteria.category : extractCategory(criteria.q);
        String queryMaterial = criteria.material != null ? criteria.material : extractMaterial(criteria.q);
        BigDecimal minPrice = criteria.minPrice;
        BigDecimal maxPrice = criteria.maxPrice;
        if (minPrice == null && maxPrice == null) {
            maxPrice = extractMaxPrice(criteria.q);
            minPrice = extractMinPrice(criteria.q);
        }

        // Build query
        List<Object> params = new ArrayList<>();
        StringBuilder sql = buildSearchQuery(scope, criteria, queryCategory, queryMaterial, minPrice, maxPrice, params);

        // Count total candidates
        int total = countTotal(sql, params);

        // Fetch extra candidates for Java-side scoring (cap at 200 to avoid slow queries)
        sql.append(" ORDER BY p.name LIMIT ?");
        int fetchLimit = Math.max(criteria.limit, Math.min(200, total > 0 ? total : 200));
        params.add(fetchLimit);

        // Execute
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql.toString(), params.toArray());

        // Map to results + calculate score + sort by score descending
        List<GeneralProductSearchResult.SearchResultItem> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            double score = calculateScore(row, queryCategory, queryMaterial, minPrice, maxPrice, criteria.q, criteria.sourceCode);
            List<String> reasons = buildScoreReasons(row, queryCategory, queryMaterial, minPrice, maxPrice, criteria.q, criteria.sourceCode);

            items.add(new GeneralProductSearchResult.SearchResultItem(
                    uuid(row, "p_id"),
                    str(row, "p_source_code"),
                    str(row, "p_source_name"),
                    str(row, "p_name"),
                    str(row, "p_category"),
                    str(row, "p_product_type"),
                    str(row, "p_material"),
                    decimal(row, "p_price"),
                    decimal(row, "p_original_price"),
                    str(row, "p_currency"),
                    str(row, "p_source_url"),
                    str(row, "p_image_url"),
                    str(row, "p_dimensions_text"),
                    str(row, "p_description"),
                    str(row, "p_visibility"),
                    score,
                    reasons
            ));
        }

        // Sort by score descending, then apply limit/offset
        items.sort((a, b) -> Double.compare(b.score(), a.score()));
        if (criteria.offset > 0 && criteria.offset < items.size()) {
            items = items.subList(criteria.offset, items.size());
        }
        if (criteria.limit > 0 && criteria.limit < items.size()) {
            items = items.subList(0, criteria.limit);
        }

        return new GeneralProductSearchResult(criteria.q, normalizedMode, scope, total, items);
    }

    private int countTotal(StringBuilder baseSql, List<Object> params) {
        String countSql = "SELECT COUNT(*) FROM (" + baseSql + ") cnt";
        try {
            Integer count = jdbcTemplate.queryForObject(countSql, Integer.class, params.toArray());
            return count != null ? count : 0;
        } catch (Exception ex) {
            log.debug("Count query failed, returning 0: {}", ex.getMessage());
            return 0;
        }
    }

    private StringBuilder buildSearchQuery(GeneralScope scope, SearchCriteria criteria,
                                            String queryCategory, String queryMaterial,
                                            BigDecimal minPrice, BigDecimal maxPrice,
                                            List<Object> params) {
        StringBuilder sql = new StringBuilder();
        sql.append("""
            SELECT p.id AS p_id, s.source_code AS p_source_code, s.source_name AS p_source_name,
                   p.name AS p_name, p.category AS p_category, p.product_type AS p_product_type,
                   p.material AS p_material, p.price AS p_price, p.original_price AS p_original_price,
                   p.currency AS p_currency, p.source_url AS p_source_url,
                   p.image_url AS p_image_url, p.dimensions_text AS p_dimensions_text,
                   p.description AS p_description, p.visibility AS p_visibility
            FROM general_products p
            JOIN general_sources s ON p.general_source_id = s.id
            WHERE p.status = 'ACTIVE'
        """);

        // Scope: visibility filtering
        List<String> visPlaceholders = new ArrayList<>();
        for (SourceVisibility vis : scope.allowedVisibilities()) {
            visPlaceholders.add("?");
            params.add(vis.name());
        }
        if (!visPlaceholders.isEmpty()) {
            sql.append(" AND p.visibility IN (").append(String.join(",", visPlaceholders)).append(")");
        }

        // Scope: owner tenant for TENANT_BOUND
        if (scope.requireOwnerTenant() && scope.ownerTenantId() != null) {
            sql.append(" AND (p.visibility != 'TENANT_BOUND' OR s.tenant_id = ?)");
            params.add(scope.ownerTenantId().toString());
        } else if (scope.requireOwnerTenant()) {
            sql.append(" AND p.visibility != 'TENANT_BOUND'");
        }

        // Source code filter
        if (criteria.sourceCode != null && !criteria.sourceCode.isBlank()) {
            sql.append(" AND s.source_code ILIKE ?");
            params.add(criteria.sourceCode.trim());
        }

        // Category filter
        if (queryCategory != null && !queryCategory.isBlank()) {
            sql.append(" AND (p.category ILIKE ? OR p.product_type ILIKE ?)");
            params.add("%" + queryCategory + "%");
            params.add("%" + queryCategory + "%");
        }

        // Material filter
        if (queryMaterial != null && !queryMaterial.isBlank()) {
            sql.append(" AND p.material ILIKE ?");
            params.add("%" + queryMaterial + "%");
        }

        // Price range
        if (minPrice != null) {
            sql.append(" AND p.price >= ?");
            params.add(minPrice);
        }
        if (maxPrice != null) {
            sql.append(" AND (p.price IS NULL OR p.price <= ?)");
            params.add(maxPrice);
        }

        // Text search on q
        if (criteria.q != null && !criteria.q.isBlank()) {
            sql.append("""
                AND (p.name ILIKE ? OR p.description ILIKE ? OR p.category ILIKE ?
                     OR p.material ILIKE ? OR s.source_code ILIKE ?)
            """);
            String likeQ = "%" + criteria.q.trim() + "%";
            for (int i = 0; i < 5; i++) params.add(likeQ);
        }

        sql.append("""
            AND (SELECT COUNT(*) FROM general_sources s2
                 WHERE s2.id = p.general_source_id AND s2.status = 'ACTIVE') = 1
        """);

        return sql;
    }

    private double calculateScore(Map<String, Object> row, String queryCategory, String queryMaterial,
                                    BigDecimal minPrice, BigDecimal maxPrice, String q, String sourceCode) {
        double score = 0.0;
        // Category match
        String category = str(row, "p_category");
        if (queryCategory != null && category != null && category.toLowerCase(Locale.ROOT).contains(queryCategory.toLowerCase(Locale.ROOT))) {
            score += 10.0;
        }
        // Material match
        String material = str(row, "p_material");
        if (queryMaterial != null && material != null && material.toLowerCase(Locale.ROOT).contains(queryMaterial.toLowerCase(Locale.ROOT))) {
            score += 6.0;
        }
        // Price within range
        BigDecimal price = decimal(row, "p_price");
        if (price != null) {
            if (minPrice != null && price.compareTo(minPrice) >= 0 && maxPrice != null && price.compareTo(maxPrice) <= 0) {
                score += 5.0;
            } else if (maxPrice != null && price.compareTo(maxPrice) <= 0 && minPrice == null) {
                score += 5.0;
            } else if (minPrice != null && price.compareTo(minPrice) >= 0 && maxPrice == null) {
                score += 5.0;
            }
        } else if (minPrice != null || maxPrice != null) {
            score -= 3.0; // price missing but filter requested
        }
        // Name contains keyword
        String name = str(row, "p_name");
        if (q != null && name != null) {
            String[] tokens = q.toLowerCase(Locale.ROOT).split("\\s+");
            long matchCount = 0;
            for (String t : tokens) {
                if (t.length() > 1 && name.toLowerCase(Locale.ROOT).contains(t)) matchCount++;
            }
            score += matchCount * 2.0;
        }
        // Description contains keyword
        String description = str(row, "p_description");
        if (q != null && description != null && description.toLowerCase(Locale.ROOT).contains(q.toLowerCase(Locale.ROOT))) {
            score += 2.0;
        }
        // Source code match
        if (sourceCode != null && sourceCode.equalsIgnoreCase(str(row, "p_source_code"))) {
            score += 2.0;
        }
        // Has image
        if (str(row, "p_image_url") != null) {
            score += 1.0;
        }
        // Category missing penalty
        if (queryCategory != null && category == null) {
            score -= 2.0;
        }
        return score;
    }

    private List<String> buildScoreReasons(Map<String, Object> row, String queryCategory, String queryMaterial,
                                             BigDecimal minPrice, BigDecimal maxPrice, String q, String sourceCode) {
        List<String> reasons = new ArrayList<>();
        String category = str(row, "p_category");
        if (queryCategory != null && category != null && category.toLowerCase(Locale.ROOT).contains(queryCategory.toLowerCase(Locale.ROOT))) {
            reasons.add("category_match");
        }
        String material = str(row, "p_material");
        if (queryMaterial != null && material != null && material.toLowerCase(Locale.ROOT).contains(queryMaterial.toLowerCase(Locale.ROOT))) {
            reasons.add("material_match");
        }
        BigDecimal price = decimal(row, "p_price");
        if (price != null) {
            if (maxPrice != null && price.compareTo(maxPrice) <= 0) {
                reasons.add("price_within_budget");
            } else if (minPrice != null && price.compareTo(minPrice) >= 0) {
                reasons.add("price_above_minimum");
            }
        } else if (minPrice != null || maxPrice != null) {
            reasons.add("price_missing");
        }
        String name = str(row, "p_name");
        if (q != null && name != null && name.toLowerCase(Locale.ROOT).contains(q.toLowerCase(Locale.ROOT).trim())) {
            reasons.add("text_match");
        }
        if (sourceCode != null && sourceCode.equalsIgnoreCase(str(row, "p_source_code"))) {
            reasons.add("source_match");
        }
        return reasons;
    }

    // --- Query understanding ---

    String extractCategory(String q) {
        if (q == null || q.isBlank()) return null;
        String lower = q.toLowerCase(Locale.ROOT).trim();
        // Longest match first
        for (String kw : new String[]{"tủ quần áo", "ghế sofa", "bàn làm việc", "bàn ăn", "bàn trà",
                "kệ tivi", "kệ sách", "đồ trang trí",
                "sofa", "ghế", "tủ áo", "tủ",
                "bàn", "giường", "kệ", "đèn", "rèm", "gương", "thảm", "tranh"}) {
            if (lower.contains(kw)) return CATEGORY_MAP.get(kw);
        }
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
        if (lower.contains("sắt")) return "sắt";
        if (lower.contains("nhựa")) return "nhựa";
        return null;
    }

    BigDecimal extractMaxPrice(String q) {
        if (q == null || q.isBlank()) return null;
        String lower = q.toLowerCase(Locale.ROOT).trim();
        // "dưới X triệu" → X * 1_000_000
        Pattern underPattern = Pattern.compile("dưới\\s*(\\d+(?:[.,]\\d+)?)\\s*(?:triệu|tr)");
        Matcher m = underPattern.matcher(lower);
        if (m.find()) {
            return new BigDecimal(m.group(1).replace(",", ".")).multiply(new BigDecimal("1000000"));
        }
        // "khoảng X triệu"
        Pattern aroundPattern = Pattern.compile("khoảng\\s*(\\d+(?:[.,]\\d+)?)\\s*(?:triệu|tr)");
        m = aroundPattern.matcher(lower);
        if (m.find()) {
            return new BigDecimal(m.group(1).replace(",", ".")).multiply(new BigDecimal("1000000"));
        }
        // "X-Y triệu"
        Pattern rangePattern = Pattern.compile("(\\d+)\\s*(?:-|đến)\\s*(\\d+)\\s*(?:triệu|tr)");
        m = rangePattern.matcher(lower);
        if (m.find()) {
            return new BigDecimal(m.group(2).replace(",", ".")).multiply(new BigDecimal("1000000"));
        }
        // bare "X triệu"
        Pattern barePattern = Pattern.compile("(\\d+(?:[.,]\\d+)?)\\s*(?:triệu|tr)\\b");
        m = barePattern.matcher(lower);
        if (m.find()) {
            return new BigDecimal(m.group(1).replace(",", ".")).multiply(new BigDecimal("1000000"));
        }
        return null;
    }

    BigDecimal extractMinPrice(String q) {
        if (q == null || q.isBlank()) return null;
        String lower = q.toLowerCase(Locale.ROOT).trim();
        // "trên X triệu"
        Pattern abovePattern = Pattern.compile("trên\\s*(\\d+(?:[.,]\\d+)?)\\s*(?:triệu|tr)");
        Matcher m = abovePattern.matcher(lower);
        if (m.find()) {
            return new BigDecimal(m.group(1).replace(",", ".")).multiply(new BigDecimal("1000000"));
        }
        // "từ X triệu"
        Pattern fromPattern = Pattern.compile("từ\\s*(\\d+(?:[.,]\\d+)?)\\s*(?:triệu|tr)");
        m = fromPattern.matcher(lower);
        if (m.find()) {
            return new BigDecimal(m.group(1).replace(",", ".")).multiply(new BigDecimal("1000000"));
        }
        return null;
    }

    private String normalizeMode(String mode) {
        if (mode == null || mode.isBlank()) return "general_compare";
        return switch (mode.trim().toLowerCase()) {
            case "general_compare", "general", "compare", "comparison" -> "general_compare";
            case "market_price", "market", "price" -> "market_price";
            case "tenant_sales", "sales", "tenant" -> "tenant_sales";
            default -> mode.trim().toLowerCase();
        };
    }

    private AppRole parseRole(String role) {
        if (role == null || role.isBlank()) return null;
        try {
            return AppRole.valueOf(role.trim().toUpperCase());
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    // --- Helpers ---

    private String str(Map<String, Object> row, String key) {
        Object v = row.get(key);
        return v != null ? v.toString() : null;
    }

    private UUID uuid(Map<String, Object> row, String key) {
        Object v = row.get(key);
        if (v instanceof UUID) return (UUID) v;
        if (v instanceof String) return UUID.fromString((String) v);
        if (v != null) return UUID.fromString(v.toString());
        return null;
    }

    private BigDecimal decimal(Map<String, Object> row, String key) {
        Object v = row.get(key);
        if (v instanceof BigDecimal) return (BigDecimal) v;
        if (v instanceof Number) return BigDecimal.valueOf(((Number) v).doubleValue());
        if (v instanceof String) {
            try { return new BigDecimal((String) v); } catch (Exception e) { return null; }
        }
        return null;
    }
}
