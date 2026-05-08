package com.app.ops;

import com.app.ops.dto.BenchmarkSummaryDto;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class BenchmarkSummaryServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void readsBenchmarkSummaryFromArtifact() throws Exception {
        Path artifact = tempDir.resolve("results.json");
        Files.writeString(artifact, """
                {
                  "dataset": {
                    "path": "chatbot/eval/dataset.jsonl",
                    "size": 48
                  },
                  "top_k": 5,
                  "results": [
                    { "mode": "vector", "recall_at_k": 0.66, "mrr": 0.46, "total_questions": 48 },
                    { "mode": "keyword", "recall_at_k": 0.79, "mrr": 0.73, "total_questions": 48 },
                    { "mode": "hybrid", "recall_at_k": 0.79, "mrr": 0.67, "total_questions": 48 },
                    { "mode": "hybrid_rerank", "recall_at_k": 0.77, "mrr": 0.62, "total_questions": 48 }
                  ],
                  "interpretation": [
                    "Keyword is strongest on the current dataset."
                  ]
                }
                """);

        BenchmarkSummaryService service = new BenchmarkSummaryService(new ObjectMapper(), artifact.toString());

        BenchmarkSummaryDto summary = service.getBenchmarkSummary();

        assertThat(summary.datasetPath()).isEqualTo("chatbot/eval/dataset.jsonl");
        assertThat(summary.datasetSize()).isEqualTo(48);
        assertThat(summary.topK()).isEqualTo(5);
        assertThat(summary.summary()).isEqualTo("Keyword is strongest on the current dataset.");
        assertThat(summary.modes()).extracting(mode -> mode.mode())
                .containsExactly("keyword", "vector", "hybrid", "hybrid_rerank");
        assertThat(summary.modes().get(0).recallAt5()).isEqualTo(0.79);
    }

    @Test
    void failsCleanlyWhenArtifactIsMissing() {
        BenchmarkSummaryService service = new BenchmarkSummaryService(new ObjectMapper(), tempDir.resolve("missing.json").toString());

        assertThatThrownBy(service::getBenchmarkSummary)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Benchmark results artifact not found");
    }
}
