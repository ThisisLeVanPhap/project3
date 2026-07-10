package com.app.ops.dto;

import java.time.Instant;
import java.util.List;

public record KbOperationsDto(
        String kbDir,
        String status,
        Instant lastRebuildAt,
        int artifactCount,
        String sourceType,
        String datasetId,
        String source,
        String sourceUrl,
        Instant lastRebuildStartedAt,
        Instant lastRebuildFinishedAt,
        String lastRebuildStatus,
        String lastRebuildMessage,
        List<KbRebuildHistoryItemDto> rebuildHistory
) {
}
