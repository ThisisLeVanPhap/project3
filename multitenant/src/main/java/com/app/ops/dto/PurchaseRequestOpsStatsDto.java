package com.app.ops.dto;

public record PurchaseRequestOpsStatsDto(
        long totalRequests,
        long newCount,
        long contactedCount,
        long completedCount,
        long assignedCount,
        long unassignedCount
) {
    public static PurchaseRequestOpsStatsDto empty() {
        return new PurchaseRequestOpsStatsDto(0, 0, 0, 0, 0, 0);
    }
}
