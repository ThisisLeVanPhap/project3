package com.app.general;

import java.util.UUID;

public record GeneralProductImportResponse(
        UUID importRunId,
        UUID generalSourceId,
        UUID artifactId,
        String datasetId,
        String buildTag,
        int productsSeen,
        int productsImported,
        int productsUpdated,
        int chunksSeen,
        int chunksImported,
        int chunksUpdated,
        String status,
        String message
) {
}
