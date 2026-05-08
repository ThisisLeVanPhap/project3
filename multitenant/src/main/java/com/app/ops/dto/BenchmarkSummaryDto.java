package com.app.ops.dto;

import java.util.List;

public record BenchmarkSummaryDto(
        String sourcePath,
        String datasetPath,
        Integer datasetSize,
        Integer topK,
        String summary,
        List<String> interpretation,
        List<BenchmarkModeSummaryDto> modes
) {
}
