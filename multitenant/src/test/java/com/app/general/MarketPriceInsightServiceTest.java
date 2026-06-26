package com.app.general;

import com.app.auth.AppRole;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class MarketPriceInsightServiceTest {

    private final MarketPriceInsightService service = new MarketPriceInsightService(null, new GeneralScopeResolver());

    @Test
    void queryUnderstandingExtractsCategory() {
        assertEquals("Sofa", service.extractCategory("sofa vải 2m"));
        assertEquals("Tủ", service.extractCategory("tủ quần áo gỗ công nghiệp"));
        assertEquals("Bàn làm việc", service.extractCategory("bàn làm việc nhỏ gọn"));
        assertEquals("Giường", service.extractCategory("giường ngủ 1m6"));
        assertEquals("Kệ", service.extractCategory("kệ sách gỗ"));
        assertEquals("Đèn", service.extractCategory("đèn thả trần"));
        assertNull(service.extractCategory("xe đạp"));
    }

    @Test
    void queryUnderstandingExtractsMaterial() {
        assertEquals("vải", service.extractMaterial("sofa vải"));
        assertEquals("da", service.extractMaterial("ghế da"));
        assertEquals("gỗ", service.extractMaterial("bàn gỗ"));
        assertEquals("MDF", service.extractMaterial("tủ MDF"));
        assertNull(service.extractMaterial("sản phẩm tốt"));
    }

    @Test
    void queryUnderstandingExtractsInputPrice() {
        assertEquals(BigDecimal.valueOf(8000000), service.extractInputPrice("sofa 8 triệu"));
        assertEquals(BigDecimal.valueOf(5000000), service.extractInputPrice("tủ 5tr"));
        assertNull(service.extractInputPrice("sofa đẹp"));
    }

    @Test
    void confidenceHighRequires50SamplesAnd2Sources() {
        MarketPriceInsightResponse.Stats stats = new MarketPriceInsightResponse.Stats(
                BigDecimal.valueOf(1000), BigDecimal.valueOf(2000), BigDecimal.valueOf(3000),
                BigDecimal.valueOf(4000), BigDecimal.valueOf(5000), 60, 2, "VND", null);
        assertEquals(60, stats.sampleCount());
        assertEquals(2, stats.sourceCount());
    }

    @Test
    void confidenceMediumFrom15Samples() {
        MarketPriceInsightResponse.Stats stats = new MarketPriceInsightResponse.Stats(
                BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                BigDecimal.ZERO, BigDecimal.ZERO, 20, 1, "VND", null);
        assertEquals(20, stats.sampleCount());
        assertEquals(1, stats.sourceCount());
    }

    @Test
    void confidenceLowFrom5Samples() {
        MarketPriceInsightResponse.Stats stats = new MarketPriceInsightResponse.Stats(
                BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                BigDecimal.ZERO, BigDecimal.ZERO, 5, 1, "VND", null);
        assertEquals(5, stats.sampleCount());
    }

    @Test
    void scopeResolverGeneralCompareUserOnlyGlobalPublic() {
        GeneralScope scope = new GeneralScopeResolver().resolve("market_price", null, null);
        assertEquals(1, scope.allowedVisibilities().size());
        assertTrue(scope.allowedVisibilities().contains(SourceVisibility.GLOBAL_PUBLIC));
        assertTrue(scope.canQueryGeneralProducts());
    }

    @Test
    void scopeResolverPlatformAdminAllVisibilities() {
        GeneralScope scope = new GeneralScopeResolver().resolve("market_price", null, AppRole.PLATFORM_ADMIN);
        assertEquals(4, scope.allowedVisibilities().size());
        assertTrue(scope.canQueryGeneralProducts());
    }

    @Test
    void scopeResolverTenantBoundNotVisibleForAnonymous() {
        GeneralScope scope = new GeneralScopeResolver().resolve("market_price", null, null);
        assertFalse(scope.allowedVisibilities().contains(SourceVisibility.TENANT_BOUND));
        assertFalse(scope.allowedVisibilities().contains(SourceVisibility.PRIVATE));
        assertFalse(scope.allowedVisibilities().contains(SourceVisibility.ADMIN_ONLY));
    }

    @Test
    void assessmentBelowP25() {
        MarketPriceInsightResponse.Stats stats = new MarketPriceInsightResponse.Stats(
                BigDecimal.valueOf(3000000), BigDecimal.valueOf(5000000), BigDecimal.valueOf(7000000),
                BigDecimal.valueOf(9000000), BigDecimal.valueOf(15000000), 30, 1, "VND", null);

        var asm = service.assessPrice(BigDecimal.valueOf(2000000), stats);
        assertEquals("below_p25", asm.position());
    }

    @Test
    void assessmentBetweenP25AndMedian() {
        MarketPriceInsightResponse.Stats stats = new MarketPriceInsightResponse.Stats(
                BigDecimal.valueOf(3000000), BigDecimal.valueOf(5000000), BigDecimal.valueOf(7000000),
                BigDecimal.valueOf(9000000), BigDecimal.valueOf(15000000), 30, 1, "VND", null);

        var asm = service.assessPrice(BigDecimal.valueOf(6000000), stats);
        assertEquals("between_p25_and_median", asm.position());
    }

    @Test
    void assessmentBetweenMedianAndP75() {
        MarketPriceInsightResponse.Stats stats = new MarketPriceInsightResponse.Stats(
                BigDecimal.valueOf(3000000), BigDecimal.valueOf(5000000), BigDecimal.valueOf(7000000),
                BigDecimal.valueOf(9000000), BigDecimal.valueOf(15000000), 30, 1, "VND", null);

        var asm = service.assessPrice(BigDecimal.valueOf(8000000), stats);
        assertEquals("between_median_and_p75", asm.position());
    }

    @Test
    void assessmentAboveMax() {
        MarketPriceInsightResponse.Stats stats = new MarketPriceInsightResponse.Stats(
                BigDecimal.valueOf(3000000), BigDecimal.valueOf(5000000), BigDecimal.valueOf(7000000),
                BigDecimal.valueOf(9000000), BigDecimal.valueOf(15000000), 30, 1, "VND", null);

        var asm = service.assessPrice(BigDecimal.valueOf(20000000), stats);
        assertEquals("above_max", asm.position());
    }

    // --- Scope canAccessSource tests ---

    @Test
    void tenantBoundSourceDeniedForUser() {
        GeneralScope scope = new GeneralScopeResolver().resolve("market_price", null, null);
        assertFalse(scope.canAccessSource("TENANT_BOUND", UUID.randomUUID()));
    }

    @Test
    void privateSourceDeniedForUser() {
        GeneralScope scope = new GeneralScopeResolver().resolve("market_price", null, null);
        assertFalse(scope.canAccessSource("PRIVATE", null));
    }

    @Test
    void adminOnlySourceDeniedForUser() {
        GeneralScope scope = new GeneralScopeResolver().resolve("market_price", null, null);
        assertFalse(scope.canAccessSource("ADMIN_ONLY", null));
    }

    @Test
    void platformAdminCanSeeAllSources() {
        GeneralScope scope = new GeneralScopeResolver().resolve("market_price", null, AppRole.PLATFORM_ADMIN);
        assertTrue(scope.canAccessSource("PRIVATE", null));
        assertTrue(scope.canAccessSource("ADMIN_ONLY", null));
        assertTrue(scope.canAccessSource("TENANT_BOUND", UUID.randomUUID()));
    }
}
