package com.app.tenant;

import java.util.UUID;

public final class TenantGuards {
    private TenantGuards() {}
    public static UUID requireTenant() {
        String tid = TenantContext.get();
        if (tid == null) throw new IllegalStateException("Missing tenant (X-API-Key or X-Tenant-Id)");
        return UUID.fromString(tid);
    }
}
