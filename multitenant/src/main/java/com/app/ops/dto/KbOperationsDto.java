package com.app.ops.dto;

import java.time.Instant;
import java.util.List;

public record KbOperationsDto(
        String kbDir,
        String status,
        Instant lastRebuildAt,
        int artifactCount,
        Instant lastRebuildStartedAt,
        Instant lastRebuildFinishedAt,
        String lastRebuildStatus,
        String lastRebuildMessage,
        List<KbRebuildHistoryItemDto> rebuildHistory
) {
}
