package com.app.ops;

import com.app.ops.dto.BenchmarkModeSummaryDto;
import com.app.ops.dto.BenchmarkSummaryDto;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class BenchmarkSummaryService {

    private static final List<String> PREFERRED_MODE_ORDER = List.of("keyword", "vector", "hybrid", "hybrid_rerank");

    private final ObjectMapper objectMapper;
    private final String benchmarkResultsPath;

    public BenchmarkSummaryService(
            ObjectMapper objectMapper,
            @Value("${app.ops.benchmark-results-path:chatbot/eval/results.json}") String benchmarkResultsPath
    ) {
        this.objectMapper = objectMapper;
        this.benchmarkResultsPath = benchmarkResultsPath;
    }

    public BenchmarkSummaryDto getBenchmarkSummary() {
        Path artifactPath = resolveArtifactPath();
        JsonNode root = readArtifact(artifactPath);
        JsonNode dataset = root.path("dataset");
        List<BenchmarkModeSummaryDto> modes = readModes(root.path("results"));
        List<String> interpretation = readInterpretation(root.path("interpretation"));

        return new BenchmarkSummaryDto(
                artifactPath.toAbsolutePath().normalize().toString(),
                textOrNull(dataset.path("path")),
                intOrNull(dataset.path("size")),
                intOrNull(root.path("top_k")),
                buildSummary(interpretation, modes),
                interpretation,
                modes
        );
    }

    Path resolveArtifactPath() {
        Path configured = Path.of(benchmarkResultsPath).normalize();
        List<Path> candidates = configured.isAbsolute()
                ? List.of(configured)
                : List.of(
                configured.toAbsolutePath().normalize(),
                Path.of("").toAbsolutePath().normalize().resolve(configured).normalize(),
                Path.of("").toAbsolutePath().normalize().resolve("..").resolve(configured).normalize()
        );

        return candidates.stream()
                .filter(Files::exists)
                .findFirst()
                .orElseThrow(() -> new IllegalStateException("Benchmark results artifact not found. Checked: " + candidates));
    }

    private JsonNode readArtifact(Path artifactPath) {
        try {
            return objectMapper.readTree(artifactPath.toFile());
        } catch (IOException e) {
            throw new IllegalStateException("Failed to read benchmark results artifact: " + artifactPath, e);
        }
    }

    private List<BenchmarkModeSummaryDto> readModes(JsonNode node) {
        if (!node.isArray()) {
            return List.of();
        }

        Map<String, BenchmarkModeSummaryDto> byMode = new LinkedHashMap<>();
        node.forEach(item -> {
            String mode = textOrNull(item.path("mode"));
            if (mode == null) {
                return;
            }
            byMode.put(mode, new BenchmarkModeSummaryDto(
                    mode,
                    doubleOrNull(item.path("recall_at_k")),
                    doubleOrNull(item.path("mrr")),
                    intOrNull(item.path("total_questions"))
            ));
        });

        return byMode.values().stream()
                .sorted(Comparator.comparingInt(dto -> modeOrder(dto.mode())))
                .toList();
    }

    private List<String> readInterpretation(JsonNode node) {
        if (!node.isArray()) {
            return List.of();
        }
        List<String> lines = new ArrayList<>();
        node.forEach(item -> {
            String text = textOrNull(item);
            if (text != null) {
                lines.add(text);
            }
        });
        return List.copyOf(lines);
    }

    private String buildSummary(List<String> interpretation, List<BenchmarkModeSummaryDto> modes) {
        if (!interpretation.isEmpty()) {
            return interpretation.get(0);
        }

        return modes.stream()
                .filter(mode -> mode.recallAt5() != null && mode.mrr() != null)
                .max(Comparator.comparing(BenchmarkModeSummaryDto::recallAt5).thenComparing(BenchmarkModeSummaryDto::mrr))
                .map(mode -> mode.mode() + " leads on Recall@5 and MRR in the current artifact.")
                .orElse("Benchmark summary is available from the current evaluation artifact.");
    }

    private int modeOrder(String mode) {
        int index = PREFERRED_MODE_ORDER.indexOf(mode);
        return index >= 0 ? index : PREFERRED_MODE_ORDER.size();
    }

    private String textOrNull(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        String value = node.asText();
        return value == null || value.isBlank() ? null : value;
    }

    private Integer intOrNull(JsonNode node) {
        return node != null && node.canConvertToInt() ? node.intValue() : null;
    }

    private Double doubleOrNull(JsonNode node) {
        return node != null && node.isNumber() ? node.doubleValue() : null;
    }
}
