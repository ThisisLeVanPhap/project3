package com.app.general;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;
import java.util.Map;

public record CrawlAndMaterializeResponse(
        boolean success,
        String datasetId,
        String datasetDir,
        String manifestPath,
        String qualityAuditPath,
        int productCount,
        int ragChunkCount,
        String qualityStatus,
        List<String> qualityReasons,
        String sourceCode,
        String sourceUrl,
        String provider,
        Map<String, Object> crawl,
        Map<String, Object> taxonomy,
        Boolean registerDataset,
        String registerError,
        JsonNode rawScriptOutput
) {
}
