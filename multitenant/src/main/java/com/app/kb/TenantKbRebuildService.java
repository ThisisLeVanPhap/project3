package com.app.kb;

import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.LlmProperties;
import com.app.ops.dto.KbRebuildHistoryItemDto;
import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.nio.file.Files;
import java.nio.file.attribute.FileTime;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

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

    public TenantKbRebuildService(
            TenantRepository tenantRepository,
            LlmProperties llmProperties,
            LlmInstanceManager llmInstanceManager,
            TenantKbRebuildStatusService tenantKbRebuildStatusService,
            TenantKbVersionRepository tenantKbVersionRepository
    ) {
        this.tenantRepository = tenantRepository;
        this.llmProperties = llmProperties;
        this.llmInstanceManager = llmInstanceManager;
        this.tenantKbRebuildStatusService = tenantKbRebuildStatusService;
        this.tenantKbVersionRepository = tenantKbVersionRepository;
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
        Instant startedAt = Instant.now();
        String versionTag = nextVersionTag(tenantId, startedAt);
        Path versionDir = rootKbDir.resolve("versions").resolve(versionTag).normalize();
        Path rawUrls = versionDir.resolve("raw_urls.txt");
        Path docsJsonl = versionDir.resolve("docs.jsonl");
        Path chunksJsonl = versionDir.resolve("chunks.jsonl");
        Path indexJson = versionDir.resolve("index.json");

        prepareVersionDirectory(versionDir, rootRawUrls, rawUrls);

        String shop = rootKbDir.getFileName() == null ? tenant.getCode() : rootKbDir.getFileName().toString();
        TenantKbVersion kbVersion = createStartedVersion(tenantId, versionTag, versionDir, rootRawUrls);
        tenantKbRebuildStatusService.markStarted(tenantId, startedAt, "KB rebuild started");

        try {
            runCommand(
                    chatbotDir,
                    List.of(
                            llmProperties.getPythonBin(),
                            "tools/scrape_site.py",
                            shop,
                            rawUrls.toString(),
                            docsJsonl.toString()
                    ),
                    "KB scrape failed"
            );

            runCommand(
                    chatbotDir,
                    List.of(
                            llmProperties.getPythonBin(),
                            "tools/build_kb.py",
                            docsJsonl.toString(),
                            chunksJsonl.toString(),
                            indexJson.toString()
                    ),
                    "KB build failed"
            );

            llmInstanceManager.evictTenant(tenantId);
            Instant finishedAt = Instant.now();
            String message = "KB rebuilt successfully. The next tenant chat request will start with the updated KB.";
            markVersionReady(kbVersion, finishedAt, message, chunksJsonl, docsJsonl);
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

    private void prepareVersionDirectory(Path versionDir, Path rootRawUrls, Path versionRawUrls) {
        try {
            Files.createDirectories(versionDir);
            if (Files.exists(rootRawUrls)) {
                Files.copy(rootRawUrls, versionRawUrls, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            } else {
                Files.writeString(versionRawUrls, "");
            }
        } catch (IOException e) {
            throw new IllegalStateException("Unable to prepare KB version directory: " + versionDir);
        }
    }

    private TenantKbVersion createStartedVersion(UUID tenantId, String versionTag, Path versionDir, Path rootRawUrls) {
        TenantKbVersion version = new TenantKbVersion();
        version.setTenantId(tenantId);
        version.setVersionTag(versionTag);
        version.setKbDir(versionDir.toAbsolutePath().normalize().toString());
        version.setSourceUrlSnapshot(readSourceUrlSnapshot(rootRawUrls));
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

    private String readSourceUrlSnapshot(Path rawUrls) {
        if (!Files.exists(rawUrls)) {
            return "[]";
        }
        try {
            List<String> urls = Files.readAllLines(rawUrls).stream()
                    .map(String::trim)
                    .filter(line -> !line.isBlank())
                    .toList();
            return toJsonArray(urls);
        } catch (IOException ignored) {
            return "[]";
        }
    }

    private String toJsonArray(List<String> values) {
        return values.stream()
                .map(value -> "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"")
                .reduce((left, right) -> left + "," + right)
                .map(json -> "[" + json + "]")
                .orElse("[]");
    }

    private void markVersionReady(TenantKbVersion version, Instant finishedAt, String message, Path chunksJsonl, Path docsJsonl) {
        version.setStatus(TenantKbVersionStatus.READY);
        version.setBuiltAt(finishedAt);
        version.setBuildMessage(message);
        version.setArtifactCount(countArtifactLines(chunksJsonl, docsJsonl));
        tenantKbVersionRepository.save(version);
    }

    private void markVersionFailed(TenantKbVersion version, Instant finishedAt, String message) {
        version.setStatus(TenantKbVersionStatus.FAILED);
        version.setBuiltAt(finishedAt);
        version.setBuildMessage(summarizeMessage(message));
        tenantKbVersionRepository.save(version);
    }

    private Integer countArtifactLines(Path chunksJsonl, Path docsJsonl) {
        Integer chunks = countLines(chunksJsonl);
        if (chunks != null) {
            return chunks;
        }
        return countLines(docsJsonl);
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
        String kbDirValue = tenant.getKbDir() == null ? "" : tenant.getKbDir().trim();
        TenantKbRebuildStatusService.RebuildTrackingSnapshot tracking = tenantKbRebuildStatusService.getSnapshot(tenantId);
        if (kbDirValue.isBlank()) {
            return new KbStatusSnapshot(
                    null,
                    "NOT_CONFIGURED",
                    tracking.lastRebuildFinishedAt(),
                    0,
                    tracking.lastRebuildStartedAt(),
                    tracking.lastRebuildFinishedAt(),
                    tracking.lastRebuildStatus(),
                    tracking.lastRebuildMessage(),
                    tracking.history()
            );
        }

        Path kbDir = Path.of(kbDirValue).normalize();
        List<Path> artifactPaths = List.of(
                kbDir.resolve("raw_urls.txt"),
                kbDir.resolve("docs.jsonl"),
                kbDir.resolve("chunks.jsonl"),
                kbDir.resolve("index.json")
        );

        List<Path> existingArtifacts = artifactPaths.stream()
                .filter(Files::exists)
                .toList();

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
                tracking.lastRebuildStartedAt(),
                tracking.lastRebuildFinishedAt(),
                tracking.lastRebuildStatus(),
                tracking.lastRebuildMessage(),
                tracking.history()
        );
    }

    private void runCommand(File workingDir, List<String> command, String failurePrefix) {
        ProcessBuilder processBuilder = new ProcessBuilder(command);
        processBuilder.directory(workingDir);
        processBuilder.redirectErrorStream(true);

        try {
            Process process = processBuilder.start();
            List<String> output = new ArrayList<>();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (output.size() < 20) {
                        output.add(line);
                    }
                }
            }

            int exitCode = process.waitFor();
            if (exitCode != 0) {
                throw new IllegalStateException(failurePrefix + ": " + summarizeOutput(output));
            }
        } catch (IOException e) {
            throw new IllegalStateException(failurePrefix + ": unable to start Python tooling");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(failurePrefix + ": interrupted");
        }
    }

    private String summarizeOutput(List<String> output) {
        if (output.isEmpty()) {
            return "no output";
        }
        return String.join(" | ", output).trim();
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
}
