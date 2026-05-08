package com.app.ops.dto;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record TenantOperationsSnapshotDto(
        UUID tenantId,
        String tenantCode,
        String tenantName,
        Instant generatedAt,
        RuntimeOperationsDto runtime,
        KbOperationsDto knowledgeBase,
        List<BotOperationsDto> bots,
        PurchaseRequestOpsStatsDto purchaseRequests
) {
}
