package com.app.general;

import java.util.UUID;

public record GeneralSourceResponse(
        UUID id,
        String sourceCode,
        String sourceName,
        String sourceDomain,
        String sourceType,
        String datasetId,
        UUID artifactId,
        String visibility,
        String status
) {
    public static GeneralSourceResponse from(GeneralSource source) {
        return new GeneralSourceResponse(
                source.getId(),
                source.getSourceCode(),
                source.getSourceName(),
                source.getSourceDomain(),
                source.getSourceType(),
                source.getDatasetId(),
                source.getArtifactId(),
                source.getVisibility(),
                source.getStatus()
        );
    }
}
