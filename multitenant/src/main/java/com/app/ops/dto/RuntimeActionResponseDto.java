package com.app.ops.dto;

import java.time.Instant;
import java.util.UUID;

public record RuntimeActionResponseDto(
        boolean success,
        String action,
        UUID tenantId,
        String message,
        Instant occurredAt
) {
}
