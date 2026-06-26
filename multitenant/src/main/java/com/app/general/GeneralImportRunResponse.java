package com.app.general;

import java.time.Instant;
import java.util.UUID;

public record GeneralImportRunResponse(
        UUID id,
        String sourceType,
        String sourceRef,
        UUID generalSourceId,
        String status,
        int productsSeen,
        int productsImported,
        int productsUpdated,
        int chunksSeen,
        int chunksImported,
        int chunksUpdated,
        String message,
        Instant startedAt,
        Instant finishedAt
) {
    public static GeneralImportRunResponse from(GeneralImportRun run) {
        return new GeneralImportRunResponse(
                run.getId(),
                run.getSourceType(),
                run.getSourceRef(),
                run.getGeneralSourceId(),
                run.getStatus(),
                run.getProductsSeen(),
                run.getProductsImported(),
                run.getProductsUpdated(),
                run.getChunksSeen(),
                run.getChunksImported(),
                run.getChunksUpdated(),
                run.getMessage(),
                run.getStartedAt(),
                run.getFinishedAt()
        );
    }
}
