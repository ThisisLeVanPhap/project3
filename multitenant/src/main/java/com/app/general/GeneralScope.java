package com.app.general;

import com.app.auth.AppRole;
import java.util.Set;
import java.util.UUID;

public record GeneralScope(
        String mode,
        UUID callerTenantId,
        AppRole callerRole,
        Set<SourceVisibility> allowedVisibilities,
        boolean requireOwnerTenant,
        UUID ownerTenantId,
        boolean allowAdminOnly,
        boolean canQueryGeneralProducts,
        String reason
) {
    public boolean canAccessSource(String sourceVisibility, UUID sourceOwnerTenantId) {
        SourceVisibility vis = SourceVisibility.fromString(sourceVisibility);
        if (!allowedVisibilities.contains(vis)) return false;
        if (vis == SourceVisibility.TENANT_BOUND && requireOwnerTenant) {
            return ownerTenantId != null && ownerTenantId.equals(sourceOwnerTenantId);
        }
        return true;
    }
}
