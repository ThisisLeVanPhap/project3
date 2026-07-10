package com.app.kb;

import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.LlmProperties;
import com.app.ops.dto.KbRebuildHistoryItemDto;
import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

import static java.nio.file.StandardCopyOption.REPLACE_EXISTING;

@Service
public class TenantKbRebuildService {

    private static final DateTimeFormatter VERSION_TAG_FORMATTER = DateTimeFormatter
            .ofPattern("'v'yyyyMMddHHmmss")
            .withZone(ZoneOffset.UTC);

    public record KbStatusSnapshot(
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

    private final TenantRepository tenantRepository;
    private final LlmProperties llmProperties;
    private final LlmInstanceManager llmInstanceManager;
    private final TenantKbRebuildStatusService tenantKbRebuildStatusService;
    private final TenantKbVersionRepository tenantKbVersionRepository;
    private final ProductDatasetRepository productDatasetRepository;
    private final TenantKbSourceService tenantKbSourceService;
    private final ObjectMapper objectMapper;

    public TenantKbRebuildService(
            TenantRepository tenantRepository,
            LlmProperties llmProperties,
            LlmInstanceManager llmInstanceManager,
            TenantKbRebuildStatusService tenantKbRebuildStatusService,
            TenantKbVersionRepository tenantKbVersionRepository,
            ProductDatasetRepository productDatasetRepository,
            TenantKbSourceService tenantKbSourceService,
            ObjectMapper objectMapper
    ) {
        this.tenantRepository = tenantRepository;
        this.llmProperties = llmProperties;
        this.llmInstanceManager = llmInstanceManager;
        this.tenantKbRebuildStatusService = tenantKbRebuildStatusService;
        this.tenantKbVersionRepository = tenantKbVersionRepository;
        this.productDatasetRepository = productDatasetRepository;
        this.tenantKbSourceService = tenantKbSourceService;
        this.objectMapper = objectMapper;
    }

    public RebuildResponse rebuild(UUID tenantId) {
        Tenant tenant = tenantRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Tenant not found"));
        String kbDirValue = tenant.getKbDir() == null ? "" : tenant.getKbDir().trim();
        if (kbDirValue.isBlank()) {
            throw new IllegalArgumentException("Tenant kb_dir is not configured");
        }

        File chatbotDir = new File(llmProperties.getModelServerDir()).getAbsoluteFile();
        if (!chatbotDir.isDirectory()) {
            throw new IllegalStateException("Invalid model-server-dir: " + chatbotDir.getAbsolutePath());
        }

        Path rootKbDir = Path.of(kbDirValue).toAbsolutePath().normalize();
        Path rootRawUrls = rootKbDir.resolve("raw_urls.txt");
        Path sourceManifest = tenantKbSourceService.sourceManifestPath(tenantId);
        Instant startedAt = Instant.now();
        String versionTag = nextVersionTag(tenantId, startedAt);
        Path versionDir = rootKbDir.resolve("versions").resolve(versionTag).normalize();
        Path versionRawUrls = versionDir.resolve("raw_urls.txt");
        Path versionManifest = versionDir.resolve("source_manifest.json");
        Path chunksJsonl = versionDir.resolve("chunks.jsonl");
        Path productsJsonl = versionDir.resolve("products.jsonl");

        prepareVersionDirectory(versionDir, rootRawUrls, versionRawUrls, sourceManifest, versionManifest, tenantId);

        TenantKbVersion kbVersion = createStartedVersion(tenantId, versionTag, versionDir, sourceManifest);
        tenantKbRebuildStatusService.markStarted(tenantId, startedAt, "KB rebuild started");

        try {
            Path kbBase = rootKbDir.getParent();
            if (kbBase == null) {
                throw new IllegalStateException("Tenant kb_dir parent is invalid");
            }
            ScriptResult scriptResult = runRebuildScript(
                    chatbotDir,
                    tenant.getCode(),
                    sourceManifest,
                    kbBase.toAbsolutePath().normalize(),
                    versionTag
            );

            llmInstanceManager.evictTenant(tenantId);
            Instant finishedAt = Instant.now();
            String message = "KB rebuilt successfully. The next tenant chat request will start with the updated KB.";
            markVersionReady(kbVersion, finishedAt, message, chunksJsonl, productsJsonl, scriptResult);
            tenantKbRebuildStatusService.markFinished(tenantId, startedAt, finishedAt, "SUCCESS", message);

            return new RebuildResponse(
                    true,
                    message,
                    finishedAt.toString(),
                    startedAt,
                    finishedAt,
                    "SUCCESS",
                    message
            );
        } catch (RuntimeException ex) {
            Instant finishedAt = Instant.now();
            String message = ex.getMessage() == null ? "KB rebuild failed" : ex.getMessage();
            markVersionFailed(kbVersion, finishedAt, message);
            tenantKbRebuildStatusService.markFinished(tenantId, startedAt, finishedAt, "FAILED", message);
            throw ex;
        }
    }

    private void prepareVersionDirectory(
            Path versionDir,
            Path rootRawUrls,
            Path versionRawUrls,
            Path rootManifest,
            Path versionManifest,
            UUID tenantId
    ) {
        try {
            Files.createDirectories(versionDir);
            if (Files.exists(rootRawUrls)) {
                Files.copy(rootRawUrls, versionRawUrls, REPLACE_EXISTING);
            } else {
                Files.writeString(versionRawUrls, "");
            }
            if (Files.exists(rootManifest)) {
                Files.copy(rootManifest, versionManifest, REPLACE_EXISTING);
            } else {
                TenantKbSourceService.SourceManifest manifest = tenantKbSourceService.readManifest(tenantId);
                objectMapper.writerWithDefaultPrettyPrinter().writeValue(versionManifest.toFile(), manifest);
            }
        } catch (IOException e) {
            throw new IllegalStateException("Unable to prepare KB version directory: " + versionDir);
        }
    }

    private TenantKbVersion createStartedVersion(UUID tenantId, String versionTag, Path versionDir, Path sourceManifest) {
        TenantKbVersion version = new TenantKbVersion();
        version.setTenantId(tenantId);
        version.setVersionTag(versionTag);
        version.setKbDir(versionDir.toAbsolutePath().normalize().toString());
        version.setSourceUrlSnapshot(readSourceSnapshot(sourceManifest));
        version.setSourceType("PRODUCT_DATASET");
        version.setStatus(TenantKbVersionStatus.BUILDING);
        version.setBuildMessage("Rebuild started");
        return tenantKbVersionRepository.save(version);
    }

    private String nextVersionTag(UUID tenantId, Instant startedAt) {
        String baseTag = VERSION_TAG_FORMATTER.format(startedAt);
        String candidate = baseTag;
        int suffix = 2;
        while (tenantKbVersionRepository.findByTenantIdAndVersionTag(tenantId, candidate).isPresent()) {
            candidate = baseTag + "-" + suffix;
            suffix++;
        }
        return candidate;
    }

    private String readSourceSnapshot(Path sourceManifest) {
        if (!Files.exists(sourceManifest)) {
            return "{}";
        }
        try {
            return Files.readString(sourceManifest);
        } catch (IOException ignored) {
            return "{}";
        }
    }

    private ScriptResult runRebuildScript(
            File chatbotDir,
            String tenantCode,
            Path sourceManifest,
            Path kbBase,
            String versionTag
    ) {
        List<String> command = List.of(
                llmProperties.getPythonBin(),
                "tools/rebuild_tenant_product_kb.py",
                "--tenant-code", tenantCode,
                "--source-manifest", sourceManifest.toString(),
                "--kb-base", kbBase.toString(),
                "--version-tag", versionTag,
                "--dataset-id", tenantCode + "-" + versionTag
        );
        return runCommand(chatbotDir, command, "KB rebuild failed");
    }

    private void markVersionReady(
            TenantKbVersion version,
            Instant finishedAt,
            String message,
            Path chunksJsonl,
            Path productsJsonl,
            ScriptResult scriptResult
    ) {
        version.setStatus(TenantKbVersionStatus.READY);
        version.setBuiltAt(finishedAt);
        version.setBuildMessage(message);
        version.setArtifactCount(scriptResult.chunkCount() != null ? scriptResult.chunkCount() : countArtifactLines(chunksJsonl, productsJsonl));
        version.setDatasetId(scriptResult.datasetId());
        version.setSourceType(scriptResult.sourceType() == null ? "PRODUCT_DATASET" : scriptResult.sourceType());
        version.setSourceUrlSnapshot(scriptResult.sourceSnapshot() == null ? version.getSourceUrlSnapshot() : scriptResult.sourceSnapshot());
        tenantKbVersionRepository.save(version);
    }

    private void markVersionFailed(TenantKbVersion version, Instant finishedAt, String message) {
        version.setStatus(TenantKbVersionStatus.FAILED);
        version.setBuiltAt(finishedAt);
        version.setBuildMessage(summarizeMessage(message));
        tenantKbVersionRepository.save(version);
    }

    private Integer countArtifactLines(Path chunksJsonl, Path productsJsonl) {
        Integer chunks = countLines(chunksJsonl);
        if (chunks != null) {
            return chunks;
        }
        return countLines(productsJsonl);
    }

    private Integer countLines(Path path) {
        if (!Files.exists(path)) {
            return null;
        }
        try {
            long count;
            try (var lines = Files.lines(path)) {
                count = lines.filter(line -> !line.isBlank()).count();
            }
            return Math.toIntExact(count);
        } catch (IOException | ArithmeticException ignored) {
            return null;
        }
    }

    private String summarizeMessage(String message) {
        String normalized = message == null ? "KB rebuild failed" : message.trim();
        if (normalized.isBlank()) {
            return "KB rebuild failed";
        }
        int maxLength = 1000;
        return normalized.length() <= maxLength ? normalized : normalized.substring(0, maxLength);
    }

    public KbStatusSnapshot inspectStatus(UUID tenantId) {
        Tenant tenant = tenantRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Tenant not found"));
        TenantKbRebuildStatusService.RebuildTrackingSnapshot tracking = tenantKbRebuildStatusService.getSnapshot(tenantId);

        TenantKbVersion activeVersion = activeKbVersion(tenant);
        if (activeVersion != null) {
            return inspectActiveVersion(activeVersion, tracking);
        }

        String kbDirValue = tenant.getKbDir() == null ? "" : tenant.getKbDir().trim();
        if (kbDirValue.isBlank()) {
            return new KbStatusSnapshot(
                    null,
                    "NOT_CONFIGURED",
                    tracking.lastRebuildFinishedAt(),
                    0,
                    null,
                    null,
                    null,
                    null,
                    tracking.lastRebuildStartedAt(),
                    tracking.lastRebuildFinishedAt(),
                    tracking.lastRebuildStatus(),
                    tracking.lastRebuildMessage(),
                    tracking.history()
            );
        }

        Path kbDir = Path.of(kbDirValue).normalize();
        List<Path> existingArtifacts = existingArtifactPaths(kbDir);
        Instant artifactLastRebuildAt = existingArtifacts.stream()
                .map(this::safeLastModified)
                .filter(fileTime -> fileTime != null)
                .max(Comparator.naturalOrder())
                .map(FileTime::toInstant)
                .orElse(null);

        String status = existingArtifacts.isEmpty() ? "NO_ARTIFACTS" : "READY";
        Instant explicitFinishedAt = tracking.lastRebuildFinishedAt();
        Instant lastRebuildAt = explicitFinishedAt != null ? explicitFinishedAt : artifactLastRebuildAt;
        return new KbStatusSnapshot(
                kbDir.toString(),
                status,
                lastRebuildAt,
                existingArtifacts.size(),
                null,
                null,
                null,
                null,
                tracking.lastRebuildStartedAt(),
                tracking.lastRebuildFinishedAt(),
                tracking.lastRebuildStatus(),
                tracking.lastRebuildMessage(),
                tracking.history()
        );
    }

    private TenantKbVersion activeKbVersion(Tenant tenant) {
        UUID activeKbVersionId = tenant.getActiveKbVersionId();
        if (activeKbVersionId == null) {
            return null;
        }
        return tenantKbVersionRepository.findByTenantIdAndId(tenant.getId(), activeKbVersionId)
                .orElse(null);
    }

    private KbStatusSnapshot inspectActiveVersion(
            TenantKbVersion activeVersion,
            TenantKbRebuildStatusService.RebuildTrackingSnapshot tracking
    ) {
        Path kbDir = Path.of(activeVersion.getKbDir()).normalize();
        List<Path> existingArtifacts = existingArtifactPaths(kbDir);
        Instant artifactLastRebuildAt = existingArtifacts.stream()
                .map(this::safeLastModified)
                .filter(fileTime -> fileTime != null)
                .max(Comparator.naturalOrder())
                .map(FileTime::toInstant)
                .orElse(null);

        Integer versionArtifactCount = activeVersion.getArtifactCount();
        if (versionArtifactCount == null) {
            versionArtifactCount = countArtifactLines(
                    kbDir.resolve("chunks.jsonl"),
                    kbDir.resolve("products.jsonl")
            );
        }
        int artifactCount = versionArtifactCount == null ? existingArtifacts.size() : versionArtifactCount;
        String status = activeVersion.getStatus() == TenantKbVersionStatus.READY
                && (artifactCount > 0 || !existingArtifacts.isEmpty())
                ? "READY"
                : activeVersion.getStatus().name();
        Instant explicitFinishedAt = tracking.lastRebuildFinishedAt();
        Instant lastRebuildAt = explicitFinishedAt != null
                ? explicitFinishedAt
                : firstNonNull(activeVersion.getBuiltAt(), artifactLastRebuildAt);
        ProductDataset dataset = activeVersion.getDatasetId() == null
                ? null
                : productDatasetRepository.findByDatasetId(activeVersion.getDatasetId()).orElse(null);
        return new KbStatusSnapshot(
                kbDir.toString(),
                status,
                lastRebuildAt,
                artifactCount,
                activeVersion.getSourceType(),
                activeVersion.getDatasetId(),
                dataset == null ? null : dataset.getSource(),
                dataset == null ? null : dataset.getSourceUrl(),
                tracking.lastRebuildStartedAt(),
                tracking.lastRebuildFinishedAt(),
                tracking.lastRebuildStatus(),
                tracking.lastRebuildMessage(),
                tracking.history()
        );
    }

    private List<Path> existingArtifactPaths(Path kbDir) {
        return List.of(
                        kbDir.resolve("source_manifest.json"),
                        kbDir.resolve("raw_urls.txt"),
                        kbDir.resolve("products.jsonl"),
                        kbDir.resolve("chunks.jsonl"),
                        kbDir.resolve("index.json")
                ).stream()
                .filter(Files::exists)
                .toList();
    }

    private Instant firstNonNull(Instant first, Instant second) {
        return first == null ? second : first;
    }

    private ScriptResult runCommand(File workingDir, List<String> command, String failurePrefix) {
        ProcessBuilder processBuilder = new ProcessBuilder(command);
        processBuilder.directory(workingDir);
        processBuilder.redirectErrorStream(true);

        try {
            Process process = processBuilder.start();
            List<String> output = new ArrayList<>();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.add(line);
                }
            }

            int exitCode = process.waitFor();
            if (exitCode != 0) {
                throw new IllegalStateException(failurePrefix + ": " + summarizeOutput(output));
            }
            return parseScriptResult(output);
        } catch (IOException e) {
            throw new IllegalStateException(failurePrefix + ": unable to start Python tooling");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(failurePrefix + ": interrupted");
        }
    }

    private ScriptResult parseScriptResult(List<String> output) {
        String jsonLine = output.stream()
                .map(String::trim)
                .filter(line -> line.startsWith("{") && line.endsWith("}"))
                .reduce((first, second) -> second)
                .orElse(null);
        if (jsonLine == null) {
            return new ScriptResult(null, null, null, null);
        }
        try {
            JsonNode root = objectMapper.readTree(jsonLine);
            JsonNode sourceSnapshotNode = root.path("source_url_snapshot");
            String sourceSnapshot = sourceSnapshotNode.isMissingNode() || sourceSnapshotNode.isNull()
                    ? null
                    : objectMapper.writeValueAsString(sourceSnapshotNode);
            return new ScriptResult(
                    text(root, "dataset_id"),
                    intValue(root, "chunk_count"),
                    text(root, "source_type"),
                    sourceSnapshot
            );
        } catch (IOException ignored) {
            return new ScriptResult(null, null, null, null);
        }
    }

    private String text(JsonNode node, String field) {
        JsonNode value = node.path(field);
        if (value.isMissingNode() || value.isNull()) {
            return null;
        }
        String text = value.asText();
        return text == null || text.isBlank() ? null : text;
    }

    private Integer intValue(JsonNode node, String field) {
        JsonNode value = node.path(field);
        return value.isNumber() ? value.asInt() : null;
    }

    private String summarizeOutput(List<String> output) {
        if (output.isEmpty()) {
            return "no output";
        }
        return String.join(" | ", output.stream().limit(20).toList()).trim();
    }

    private FileTime safeLastModified(Path path) {
        try {
            return Files.getLastModifiedTime(path);
        } catch (IOException ignored) {
            return null;
        }
    }

    public record RebuildResponse(
            boolean success,
            String message,
            String rebuiltAt,
            Instant lastRebuildStartedAt,
            Instant lastRebuildFinishedAt,
            String lastRebuildStatus,
            String lastRebuildMessage
    ) {
    }

    private record ScriptResult(
            String datasetId,
            Integer chunkCount,
            String sourceType,
            String sourceSnapshot
    ) {
    }
}
