package com.app.general;

import com.app.auth.AppRole;
import org.junit.jupiter.api.Test;

import java.util.EnumSet;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class GeneralScopeResolverTest {

    private final GeneralScopeResolver resolver = new GeneralScopeResolver();
    private final UUID tenantA = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private final UUID tenantB = UUID.fromString("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");

    // === Data isolation: GENERAL_COMPARE ===

    @Test
    void generalCompareAnonymousOnlyGlobalPublic() {
        GeneralScope scope = resolver.resolve("general_compare", null, null);
        assertEquals(Set.of(SourceVisibility.GLOBAL_PUBLIC), scope.allowedVisibilities());
        assertTrue(scope.canQueryGeneralProducts());
    }

    @Test
    void generalCompareTenantAdminOnlyGlobalPublic() {
        GeneralScope scope = resolver.resolve("general_compare", tenantA, AppRole.TENANT_ADMIN);
        assertEquals(Set.of(SourceVisibility.GLOBAL_PUBLIC), scope.allowedVisibilities());
        assertFalse(scope.canAccessSource("TENANT_BOUND", tenantA));
        assertFalse(scope.canAccessSource("PRIVATE", null));
        assertFalse(scope.canAccessSource("ADMIN_ONLY", null));
    }

    @Test
    void generalComparePlatformAdminSeesAll() {
        GeneralScope scope = resolver.resolve("general_compare", null, AppRole.PLATFORM_ADMIN);
        assertEquals(EnumSet.allOf(SourceVisibility.class), scope.allowedVisibilities());
        assertTrue(scope.canAccessSource("PRIVATE", null));
        assertTrue(scope.canAccessSource("ADMIN_ONLY", null));
        assertTrue(scope.canAccessSource("TENANT_BOUND", tenantA));
    }

    @Test
    void generalCompareTenantAdminCannotSeeTenantBSource() {
        // TenantA admin asking in GENERAL_COMPARE — can only see GLOBAL_PUBLIC
        GeneralScope scope = resolver.resolve("general_compare", tenantA, AppRole.TENANT_ADMIN);
        assertFalse(scope.canAccessSource("TENANT_BOUND", tenantB));
        // Even own TENANT_BOUND is not visible in GENERAL_COMPARE
        assertFalse(scope.canAccessSource("TENANT_BOUND", tenantA));
    }

    // === Data isolation: MARKET_PRICE ===

    @Test
    void marketPriceAnonymousOnlyGlobalPublic() {
        GeneralScope scope = resolver.resolve("market_price", null, null);
        assertEquals(Set.of(SourceVisibility.GLOBAL_PUBLIC), scope.allowedVisibilities());
    }

    @Test
    void marketPriceTenantAdminOnlyGlobalPublic() {
        GeneralScope scope = resolver.resolve("market_price", tenantA, AppRole.TENANT_ADMIN);
        assertEquals(Set.of(SourceVisibility.GLOBAL_PUBLIC), scope.allowedVisibilities());
        assertFalse(scope.canAccessSource("TENANT_BOUND", tenantA));
        assertFalse(scope.canAccessSource("PRIVATE", null));
    }

    @Test
    void marketPricePlatformAdminSeesAll() {
        GeneralScope scope = resolver.resolve("market_price", null, AppRole.PLATFORM_ADMIN);
        assertEquals(EnumSet.allOf(SourceVisibility.class), scope.allowedVisibilities());
    }

    // === Data isolation: TENANT_SALES ===

    @Test
    void tenantSalesAnonymousDenied() {
        GeneralScope scope = resolver.resolve("tenant_sales", null, null);
        assertFalse(scope.canQueryGeneralProducts());
        assertTrue(scope.allowedVisibilities().isEmpty());
    }

    @Test
    void tenantSalesTenantMemberSeesOwnBoundOnly() {
        GeneralScope scope = resolver.resolve("tenant_sales", tenantA, AppRole.TENANT_MEMBER);
        assertTrue(scope.canQueryGeneralProducts());
        assertEquals(Set.of(SourceVisibility.TENANT_BOUND), scope.allowedVisibilities());
        assertTrue(scope.requireOwnerTenant());
        assertEquals(tenantA, scope.ownerTenantId());
        assertTrue(scope.canAccessSource("TENANT_BOUND", tenantA));
        assertFalse(scope.canAccessSource("TENANT_BOUND", tenantB));
        assertFalse(scope.canAccessSource("PRIVATE", null));
        assertFalse(scope.canAccessSource("ADMIN_ONLY", null));
    }

    @Test
    void tenantSalesTenantAdminCannotSeeTenantB() {
        GeneralScope scope = resolver.resolve("tenant_sales", tenantA, AppRole.TENANT_ADMIN);
        assertTrue(scope.canQueryGeneralProducts());
        assertTrue(scope.canAccessSource("TENANT_BOUND", tenantA));
        assertFalse(scope.canAccessSource("TENANT_BOUND", tenantB));
    }

    @Test
    void tenantSalesWithoutTenantContextDenied() {
        GeneralScope scope = resolver.resolve("tenant_sales", null, AppRole.TENANT_MEMBER);
        assertFalse(scope.canQueryGeneralProducts());
    }

    // === PRIVATE / ADMIN_ONLY ===

    @Test
    void privateSourceDeniedForAnyNonAdmin() {
        for (AppRole role : new AppRole[]{AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER}) {
            GeneralScope scope = resolver.resolve("general_compare", tenantA, role);
            assertFalse(scope.canAccessSource("PRIVATE", null), "Role " + role + " should not see PRIVATE");
            assertFalse(scope.canAccessSource("ADMIN_ONLY", null), "Role " + role + " should not see ADMIN_ONLY");
        }
    }

    @Test
    void privateSourceAllowedForPlatformAdmin() {
        GeneralScope scope = resolver.resolve("general_compare", null, AppRole.PLATFORM_ADMIN);
        assertTrue(scope.canAccessSource("PRIVATE", null));
        assertTrue(scope.canAccessSource("ADMIN_ONLY", null));
    }

    // === TENANT_BOUND cross-tenant isolation ===

    @Test
    void tenantBoundIsolatedBetweenTenants() {
        // Tenant A cannot access Tenant B's TENANT_BOUND data
        GeneralScope scope = resolver.resolve("tenant_sales", tenantA, AppRole.TENANT_ADMIN);
        assertTrue(scope.canAccessSource("TENANT_BOUND", tenantA));
        assertFalse(scope.canAccessSource("TENANT_BOUND", tenantB));
    }

    // === Mode normalization ===

    @Test
    void modeAliasesMapCorrectly() {
        assertEquals("general_compare", resolver.resolve("comparison", null, null).mode());
        assertEquals("market_price", resolver.resolve("price", null, null).mode());
        assertEquals("tenant_sales", resolver.resolve("shop", tenantA, AppRole.TENANT_MEMBER).mode());
    }

    @Test
    void invalidModeReturnsRestrictedScope() {
        GeneralScope scope = resolver.resolve("invalid", null, null);
        assertFalse(scope.canQueryGeneralProducts());
        assertTrue(scope.reason().contains("Unknown mode"));
    }

    // === Edge cases ===

    @Test
    void nullRoleDefaultsToAnonymous() {
        GeneralScope scope = resolver.resolve("general_compare", null, null);
        assertTrue(scope.canQueryGeneralProducts());
        assertEquals(Set.of(SourceVisibility.GLOBAL_PUBLIC), scope.allowedVisibilities());
    }

    @Test
    void canAccessSourceWithNullOwnerTenant() {
        GeneralScope scope = resolver.resolve("general_compare", null, AppRole.PLATFORM_ADMIN);
        assertTrue(scope.canAccessSource("GLOBAL_PUBLIC", null));
        assertTrue(scope.canAccessSource("PRIVATE", null));
        assertTrue(scope.canAccessSource("ADMIN_ONLY", null));
    }
}
