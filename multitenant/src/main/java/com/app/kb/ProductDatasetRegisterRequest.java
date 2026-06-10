package com.app.kb;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ProductDatasetRegisterRequest(
        @JsonProperty("dataset_id")
        String datasetId,
        String path,
        String source,
        @JsonProperty("source_url")
        String sourceUrl,
        String version
) {
}
