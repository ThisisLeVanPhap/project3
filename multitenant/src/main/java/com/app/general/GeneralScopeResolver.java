package com.app.general;

import com.app.auth.AppRole;
import org.springframework.stereotype.Service;

import java.util.EnumSet;
import java.util.Set;
import java.util.UUID;

@Service
public class GeneralScopeResolver {

    public GeneralScope resolve(String mode, UUID callerTenantId, AppRole callerRole) {
        return resolve(mode, callerTenantId, callerRole, null);
    }

    public GeneralScope resolve(String mode, UUID callerTenantId, AppRole callerRole, UUID requestedOwnerTenantId) {
        String normalizedMode = normalizeMode(mode);

        return switch (normalizedMode) {
            case "general_compare" -> resolveGeneralCompare(callerTenantId, callerRole, requestedOwnerTenantId);
            case "market_price" -> resolveMarketPrice(callerTenantId, callerRole, requestedOwnerTenantId);
            case "tenant_sales" -> resolveTenantSales(callerTenantId, callerRole);
            default -> new GeneralScope(
                    normalizedMode, callerTenantId, callerRole,
                    Set.of(), false, null, false, false,
                    "Unknown mode: " + normalizedMode
            );
        };
    }

    private GeneralScope resolveGeneralCompare(UUID callerTenantId, AppRole callerRole, UUID requestedOwnerTenantId) {
        if (callerRole == null) {
            return new GeneralScope(
                    "general_compare", callerTenantId, null,
                    Set.of(SourceVisibility.GLOBAL_PUBLIC),
                    false, null, false, true,
                    "User/anonymous: GLOBAL_PUBLIC only"
            );
        }
        return switch (callerRole) {
            case PLATFORM_ADMIN -> new GeneralScope(
                    "general_compare", callerTenantId, callerRole,
                    EnumSet.allOf(SourceVisibility.class),
                    false, null, true, true,
                    "Platform admin: all visibilities"
            );
            case TENANT_ADMIN, TENANT_MEMBER -> new GeneralScope(
                    "general_compare", callerTenantId, callerRole,
                    Set.of(SourceVisibility.GLOBAL_PUBLIC),
                    false, null, false, true,
                    "Tenant role: GLOBAL_PUBLIC only"
            );
            default -> new GeneralScope(
                    "general_compare", callerTenantId, callerRole,
                    Set.of(SourceVisibility.GLOBAL_PUBLIC),
                    false, null, false, true,
                    "User/anonymous: GLOBAL_PUBLIC only"
            );
        };
    }

    private GeneralScope resolveMarketPrice(UUID callerTenantId, AppRole callerRole, UUID requestedOwnerTenantId) {
        if (callerRole == null) {
            return new GeneralScope(
                    "market_price", callerTenantId, null,
                    Set.of(SourceVisibility.GLOBAL_PUBLIC),
                    false, null, false, true,
                    "User/anonymous: GLOBAL_PUBLIC only"
            );
        }
        return switch (callerRole) {
            case PLATFORM_ADMIN -> new GeneralScope(
                    "market_price", callerTenantId, callerRole,
                    EnumSet.allOf(SourceVisibility.class),
                    false, null, true, true,
                    "Platform admin: all visibilities"
            );
            case TENANT_ADMIN, TENANT_MEMBER -> new GeneralScope(
                    "market_price", callerTenantId, callerRole,
                    Set.of(SourceVisibility.GLOBAL_PUBLIC),
                    false, null, false, true,
                    "Tenant role: GLOBAL_PUBLIC only"
            );
            default -> new GeneralScope(
                    "market_price", callerTenantId, callerRole,
                    Set.of(SourceVisibility.GLOBAL_PUBLIC),
                    false, null, false, true,
                    "User/anonymous: GLOBAL_PUBLIC only"
            );
        };
    }

    private GeneralScope resolveTenantSales(UUID callerTenantId, AppRole callerRole) {
        if (callerRole == null) {
            return new GeneralScope(
                    "tenant_sales", callerTenantId, null,
                    Set.of(), false, null, false, false,
                    "Tenant sales not available for anonymous users"
            );
        }
        return switch (callerRole) {
            case PLATFORM_ADMIN -> new GeneralScope(
                    "tenant_sales", callerTenantId, callerRole,
                    EnumSet.allOf(SourceVisibility.class),
                    true, callerTenantId, true, true,
                    "Platform admin: all visibilities with ownership"
            );
            case TENANT_ADMIN, TENANT_MEMBER -> {
                if (callerTenantId == null) {
                    yield new GeneralScope(
                            "tenant_sales", null, callerRole,
                            Set.of(), false, null, false, false,
                            "Tenant sales requires tenant context"
                    );
                }
                yield new GeneralScope(
                        "tenant_sales", callerTenantId, callerRole,
                        Set.of(SourceVisibility.TENANT_BOUND),
                        true, callerTenantId, false, true,
                        "Tenant sales: TENANT_BOUND for own tenant"
                );
            }
            default -> new GeneralScope(
                    "tenant_sales", callerTenantId, callerRole,
                    Set.of(), false, null, false, false,
                    "Tenant sales not available for anonymous users"
            );
        };
    }

    private String normalizeMode(String mode) {
        if (mode == null || mode.isBlank()) return "general_compare";
        return switch (mode.trim().toLowerCase()) {
            case "general_compare", "general", "general_consumer", "compare", "comparison" -> "general_compare";
            case "market_price", "market", "price", "market_reference" -> "market_price";
            case "tenant_sales", "sales", "tenant", "shop" -> "tenant_sales";
            default -> mode.trim().toLowerCase();
        };
    }
}
