package com.app.ops.dto;

import java.time.Instant;

public record RuntimeOperationsDto(
        boolean active,
        String status,
        String baseUrl,
        long pid,
        Instant lastActivityAt
) {
}
