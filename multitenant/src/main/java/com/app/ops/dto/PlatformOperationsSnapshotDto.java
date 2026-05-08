package com.app.ops.dto;

import java.time.Instant;
import java.util.List;

public record PlatformOperationsSnapshotDto(
        Instant generatedAt,
        int tenantCount,
        int activeRuntimeSessionCount,
        PurchaseRequestOpsStatsDto purchaseRequests,
        List<TenantOperationsSnapshotDto> tenants
) {
}
