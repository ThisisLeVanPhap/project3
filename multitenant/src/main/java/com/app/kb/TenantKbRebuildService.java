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
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class TenantKbRebuildService {

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

    public TenantKbRebuildService(
            TenantRepository tenantRepository,
            LlmProperties llmProperties,
            LlmInstanceManager llmInstanceManager,
            TenantKbRebuildStatusService tenantKbRebuildStatusService
    ) {
        this.tenantRepository = tenantRepository;
        this.llmProperties = llmProperties;
        this.llmInstanceManager = llmInstanceManager;
        this.tenantKbRebuildStatusService = tenantKbRebuildStatusService;
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

        Path kbDir = Path.of(kbDirValue).normalize();
        Path rawUrls = kbDir.resolve("raw_urls.txt");
        Path docsJsonl = kbDir.resolve("docs.jsonl");
        Path chunksJsonl = kbDir.resolve("chunks.jsonl");
        Path indexJson = kbDir.resolve("index.json");

        String shop = kbDir.getFileName() == null ? tenant.getCode() : kbDir.getFileName().toString();
        Instant startedAt = Instant.now();
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
            tenantKbRebuildStatusService.markFinished(tenantId, startedAt, finishedAt, "FAILED", message);
            throw ex;
        }
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
