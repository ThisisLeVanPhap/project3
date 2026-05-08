package com.app.ops.dto;

public record BenchmarkModeSummaryDto(
        String mode,
        Double recallAt5,
        Double mrr,
        Integer totalQuestions
) {
}
