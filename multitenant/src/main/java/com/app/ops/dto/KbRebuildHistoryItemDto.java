package com.app.ops.dto;

import java.time.Instant;

public record KbRebuildHistoryItemDto(
        Instant startedAt,
        Instant finishedAt,
        String status,
        String message
) {
}
