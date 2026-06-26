package com.app.general;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class GeneralProductSearchServiceTest {

    // Testing query understanding only (rule-based extractors)
    // JdbcTemplate-based search with scope+ranking needs integration test

    private final GeneralProductSearchService service =
            new GeneralProductSearchService(null, new GeneralScopeResolver());

    @Test
    void searchLimitClampsToMax20() {
        var criteria = new SearchCriteria("test", "general_compare", null, null,
                null, null, null, null, null, 100, 0);
        assertEquals(20, criteria.limit);
    }

    @Test
    void queryUnderstandingExtractsCategory() {
        assertEquals("Sofa", service.extractCategory("mua sofa vải"));
        assertEquals("Tủ", service.extractCategory("tủ quần áo cánh lùa"));
        assertEquals("Bàn làm việc", service.extractCategory("bàn làm việc nhỏ gọn"));
        assertEquals("Kệ", service.extractCategory("kệ sách gỗ"));
        assertEquals("Đèn", service.extractCategory("đèn thả trần"));
        assertEquals("Giường", service.extractCategory("giường ngủ 1m6"));
        assertNull(service.extractCategory("sản phẩm chất lượng"));
    }

    @Test
    void queryUnderstandingExtractsMaterial() {
        assertEquals("vải", service.extractMaterial("sofa vải"));
        assertEquals("da", service.extractMaterial("ghế da cao cấp"));
        assertEquals("gỗ", service.extractMaterial("bàn gỗ đẹp"));
        assertNull(service.extractMaterial("sản phẩm tốt"));
    }

    @Test
    void queryUnderstandingExtractsMaxPrice() {
        assertEquals(BigDecimal.valueOf(7000000), service.extractMaxPrice("dưới 7 triệu"));
        assertEquals(BigDecimal.valueOf(5000000), service.extractMaxPrice("khoảng 5 triệu"));
        assertNull(service.extractMaxPrice("sofa đẹp"));
    }

    @Test
    void scopeResolverIntegration() {
        // Test that scope resolver correctly restricts access
        GeneralScopeResolver resolver = new GeneralScopeResolver();

        // GENERAL_COMPARE normal user -> only GLOBAL_PUBLIC
        GeneralScope scope = resolver.resolve("general_compare", null, null);
        assertEquals(1, scope.allowedVisibilities().size());
        assertEquals(SourceVisibility.GLOBAL_PUBLIC, scope.allowedVisibilities().iterator().next());

        // TENANT_SALES tenant admin with tenant context -> TENANT_BOUND
        scope = resolver.resolve("tenant_sales", java.util.UUID.randomUUID(), com.app.auth.AppRole.TENANT_ADMIN);
        assertEquals(1, scope.allowedVisibilities().size());
        assertEquals(SourceVisibility.TENANT_BOUND, scope.allowedVisibilities().iterator().next());
        assertTrue(scope.canQueryGeneralProducts());

        // GENERAL_COMPARE platform admin -> all visibilities
        scope = resolver.resolve("general_compare", null, com.app.auth.AppRole.PLATFORM_ADMIN);
        assertEquals(4, scope.allowedVisibilities().size());
    }
}
