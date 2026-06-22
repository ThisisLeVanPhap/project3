package com.app.modelserver;

import com.app.bots.ChatbotInstance;
import com.app.kb.ResolvedTenantKbDirectory;
import com.app.kb.TenantKbDirectoryResolver;
import com.app.kb.TenantKbDirectorySource;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.File;
import java.net.ServerSocket;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;

@Slf4j
@Service
@RequiredArgsConstructor
public class LlmInstanceManager {

    public static final String RUNTIME_EXTERNAL_HTTP = "external_http";
    public static final String RUNTIME_SPAWNED_PROCESS = "spawned_process";
    public static final String OBSERVABILITY_EXTERNAL_BASE_URL = "EXTERNAL_BASE_URL";
    public static final String OBSERVABILITY_JAVA_SPAWNED = "JAVA_SPAWNED";

    private static final Duration EXTERNAL_HEALTH_TIMEOUT = Duration.ofSeconds(2);
    private static final String NOTE_EXTERNAL_UNAVAILABLE = "Java does not own external Python process";
    private static final String NOTE_EXTERNAL_HEALTH_FAILED = "Java could not read external runtime /healthz";
    private static final String HEALTH_SOURCE_EXTERNAL = "EXTERNAL_HEALTHZ";
    private static final String VERSION_SEGMENT = "versions";
    private static final String PATH_SEPARATOR_REGEX = "[\\\\/]";

    private final LlmProperties props;
    private final TenantKbDirectoryResolver tenantKbDirectoryResolver;

    private final Duration idleTtl = Duration.ofMinutes(15);

    public record Running(String baseUrl, long pid, Instant lastUsedAt) {}

    public record Session(String baseUrl, boolean coldStart, boolean warmupWaited, String runtimeMode) {
        public Session(String baseUrl, boolean coldStart, boolean warmupWaited) {
            this(baseUrl, coldStart, warmupWaited, "unknown");
        }
    }

    public record RuntimeStatusSnapshot(
            UUID tenantId,
            String baseUrl,
            long pid,
            Instant lastUsedAt,
            boolean healthy
    ) {}

    public record RuntimeKbDesiredSnapshot(
            @JsonProperty("kb_dir")
            String kbDir,
            String source,
            @JsonProperty("version_id")
            UUID versionId,
            @JsonProperty("version_tag")
            String versionTag,
            @JsonProperty("fallback_reason")
            String fallbackReason
    ) {}

    public record RuntimeKbRunningSnapshot(
            String mode,
            @JsonProperty("kb_dir")
            String kbDir,
            String source,
            @JsonProperty("version_id")
            UUID versionId,
            @JsonProperty("version_tag")
            String versionTag,
            @JsonProperty("started_at")
            @JsonFormat(shape = JsonFormat.Shape.STRING)
            Instant startedAt,
            @JsonProperty("last_used_at")
            @JsonFormat(shape = JsonFormat.Shape.STRING)
            Instant lastUsedAt,
            @JsonProperty("process_alive")
            Boolean processAlive,
            Long pid,
            String note,
            Boolean ready,
            @JsonProperty("kb_loaded")
            Boolean kbLoaded,
            @JsonProperty("retrieval_mode")
            String retrievalMode
    ) {}

    public record RuntimeKbStatusSnapshot(
            @JsonProperty("tenant_id")
            UUID tenantId,
            RuntimeKbDesiredSnapshot desired,
            RuntimeKbRunningSnapshot running,
            @JsonProperty("in_sync")
            Boolean inSync
    ) {}

    private record RuntimeKbMetadata(
            String kbDir,
            String source,
            UUID versionId,
            String versionTag,
            Instant startedAt,
            long pid
    ) {}

    private record ExternalHealthSnapshot(
            String kbDir,
            String versionTag,
            Boolean ready,
            Boolean kbLoaded,
            String retrievalMode,
            String note
    ) {}

    private record HealthzResponse(
            Boolean ready,
            @JsonProperty("kb_dir")
            String kbDir,
            @JsonProperty("kb_loaded")
            Boolean kbLoaded,
            @JsonProperty("retrieval_mode")
            String retrievalMode
    ) {}

    private final Map<UUID, Running> runningByTenant = new ConcurrentHashMap<>();
    private final Map<UUID, Process> processByTenant = new ConcurrentHashMap<>();
    private final Map<UUID, RuntimeKbMetadata> runtimeKbByTenant = new ConcurrentHashMap<>();
    private final Map<UUID, ReentrantLock> tenantSpawnLocks = new ConcurrentHashMap<>();
    private final WebClient http = WebClient.builder().build();

    private final ReentrantLock spawnLock = new ReentrantLock();
    private final Set<Integer> reservedPorts = ConcurrentHashMap.newKeySet();

    public String getOrStartBaseUrl(UUID tenantId, ChatbotInstance botCfg) {
        return getOrStartSession(tenantId, botCfg).baseUrl();
    }

    public Session getOrStartSession(UUID tenantId, ChatbotInstance botCfg) {
        ResolvedTenantKbDirectory resolvedKbDirectory = resolveKbDirectoryForTenant(tenantId);
        String externalBaseUrl = normalizedExternalBaseUrl();
        if (shouldUseExternalRuntime(resolvedKbDirectory, externalBaseUrl)) {
            log.info(
                    "LLM runtime selected mode={} tenant={} baseUrl={} healthPath={}",
                    RUNTIME_EXTERNAL_HTTP,
                    tenantId,
                    externalBaseUrl,
                    props.getHealthPath()
            );
            if (isHealthy(externalBaseUrl)) {
                return new Session(externalBaseUrl, false, false, RUNTIME_EXTERNAL_HTTP);
            }
            throw new ChatbotUpstreamException(
                    UpstreamFailureCategory.UNAVAILABLE,
                    tenantId.toString(),
                    externalBaseUrl,
                    null,
                    false,
                    false,
                    "Configured PYTHON_LLM_BASE_URL is not healthy at " + externalBaseUrl + props.getHealthPath()
                            + ". Start chatbot-api, check the health endpoint, or unset PYTHON_LLM_BASE_URL for local spawn fallback.",
                    null
            );
        }

        Running current = runningByTenant.get(tenantId);
        RuntimeKbMetadata currentRuntime = runtimeKbByTenant.get(tenantId);
        if (current != null && currentRuntime != null && matchesResolvedKb(currentRuntime, resolvedKbDirectory) && isHealthy(current.baseUrl())) {
            runningByTenant.put(tenantId, new Running(current.baseUrl(), current.pid(), Instant.now()));
            log.info(
                    "LLM runtime selected mode={} tenant={} baseUrl={} pid={} reused=true",
                    RUNTIME_SPAWNED_PROCESS,
                    tenantId,
                    current.baseUrl(),
                    current.pid()
            );
            return new Session(current.baseUrl(), false, false, RUNTIME_SPAWNED_PROCESS);
        }
        runningByTenant.remove(tenantId);
        runtimeKbByTenant.remove(tenantId);

        ReentrantLock tenantLock = tenantSpawnLocks.computeIfAbsent(tenantId, ignored -> new ReentrantLock());
        boolean warmupWaited = !tenantLock.tryLock();
        if (warmupWaited) {
            log.info("Waiting for in-flight LLM startup tenant={}", tenantId);
            tenantLock.lock();
        }

        try {
            Running existing = runningByTenant.get(tenantId);
            RuntimeKbMetadata existingRuntime = runtimeKbByTenant.get(tenantId);
            if (existing != null && existingRuntime != null && matchesResolvedKb(existingRuntime, resolvedKbDirectory) && isHealthy(existing.baseUrl())) {
                runningByTenant.put(tenantId, new Running(existing.baseUrl(), existing.pid(), Instant.now()));
                log.info(
                        "LLM runtime selected mode={} tenant={} baseUrl={} pid={} reused=true warmupWaited={}",
                        RUNTIME_SPAWNED_PROCESS,
                        tenantId,
                        existing.baseUrl(),
                        existing.pid(),
                        warmupWaited
                );
                return new Session(existing.baseUrl(), false, warmupWaited, RUNTIME_SPAWNED_PROCESS);
            }
            runningByTenant.remove(tenantId);
            runtimeKbByTenant.remove(tenantId);

            log.info(
                    "LLM runtime selected mode={} tenant={} pythonBin={} modelServerDir={} kbDir={} source={} versionTag={}",
                    RUNTIME_SPAWNED_PROCESS,
                    tenantId,
                    props.getPythonBin(),
                    props.getModelServerDir(),
                    resolvedKbDirectory.kbDir(),
                    resolvedKbDirectory.source(),
                    resolvedKbDirectory.versionTag()
            );

            Running spawned = spawn(tenantId, warmupWaited, resolvedKbDirectory);
            runningByTenant.put(tenantId, spawned);
            return new Session(spawned.baseUrl(), true, warmupWaited, RUNTIME_SPAWNED_PROCESS);
        } finally {
            tenantLock.unlock();
        }
    }

    public void cleanupIdle() {
        Instant now = Instant.now();
        for (var e : runningByTenant.entrySet()) {
            Running r = e.getValue();
            if (Duration.between(r.lastUsedAt(), now).compareTo(idleTtl) > 0) {
                runningByTenant.remove(e.getKey());
                runtimeKbByTenant.remove(e.getKey());
            }
        }
    }

    private boolean isHealthy(String baseUrl) {
        try {
            Boolean ready = http.get()
                    .uri(baseUrl + props.getHealthPath())
                    .retrieve()
                    .bodyToMono(Map.class)
                    .map(m -> {
                        Object v = m.get("ready");
                        if (v instanceof Boolean b) return b;
                        if (v instanceof String s) return Boolean.parseBoolean(s);
                        return false;
                    })
                    .onErrorReturn(false)
                    .block(Duration.ofSeconds(1));

            return ready != null && ready;
        } catch (Exception ignored) {
            return false;
        }
    }

    private Running spawn(UUID tenantId, boolean warmupWaited, ResolvedTenantKbDirectory resolvedKbDirectory) {
        if (props.getPythonBin() == null || props.getPythonBin().isBlank()) {
            throw spawnConfigException(
                    tenantId,
                    "Missing PYTHON_BIN for local spawned Python mode. Set PYTHON_LLM_BASE_URL to use an external chatbot-api service, or set PYTHON_BIN for local fallback."
            );
        }
        if (props.getModelServerDir() == null || props.getModelServerDir().isBlank()) {
            throw spawnConfigException(
                    tenantId,
                    "Missing MODEL_SERVER_DIR for local spawned Python mode. Set PYTHON_LLM_BASE_URL to use an external chatbot-api service, or set MODEL_SERVER_DIR for local fallback."
            );
        }

        int port;
        String baseUrl;

        spawnLock.lock();
        try {
            port = pickPortReserved();
            reservedPorts.add(port);
            baseUrl = "http://" + props.getHost() + ":" + port;
        } finally {
            spawnLock.unlock();
        }

        Process process = null;
        long pid = -1;

        try {
            File dir = new File(props.getModelServerDir()).getAbsoluteFile();
            log.info("Resolved model-server-dir={}", dir.getAbsolutePath());
            if (!dir.isDirectory()) {
                throw spawnConfigException(
                        tenantId,
                        "Invalid MODEL_SERVER_DIR for local spawned Python mode: " + dir.getAbsolutePath()
                                + ". Set PYTHON_LLM_BASE_URL to use an external chatbot-api service, or fix MODEL_SERVER_DIR."
                );
            }

            ProcessBuilder pb = new ProcessBuilder(
                    props.getPythonBin(),
                    "-m", "uvicorn",
                    props.getUvicornModule(),
                    "--host", props.getHost(),
                    "--port", String.valueOf(port)
            );

            pb.directory(dir);
            pb.redirectErrorStream(true);
            pb.environment().put("KB_DIR", resolvedKbDirectory.kbDir());
            log.info(
                    "Tenant {} KB_DIR={} source={} versionTag={}",
                    tenantId,
                    resolvedKbDirectory.kbDir(),
                    resolvedKbDirectory.source(),
                    resolvedKbDirectory.versionTag()
            );

            log.info(
                    "Spawning LLM instance tenant={} baseUrl={} warmupWaited={} python={} dir={}",
                    tenantId,
                    baseUrl,
                    warmupWaited,
                    props.getPythonBin(),
                    dir.getAbsolutePath()
            );

            process = pb.start();
            pid = process.pid();
            recordSpawnedRuntimeKb(tenantId, resolvedKbDirectory, pid, Instant.now(), process);

            Process finalProcess = process;
            long finalPid = pid;
            new Thread(() -> {
                try (var br = new java.io.BufferedReader(new java.io.InputStreamReader(finalProcess.getInputStream()))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        log.info("[llm:{} pid={}] {}", tenantId, finalPid, line);
                    }
                } catch (Exception ex) {
                    log.warn("[llm:{} pid={}] log stream closed: {}", tenantId, finalPid, ex.toString());
                }
            }, "llm-log-" + tenantId).start();

            long deadline = System.currentTimeMillis() + props.getStartupTimeoutMs();
            long lastLog = 0;

            while (System.currentTimeMillis() < deadline) {
                if (!process.isAlive()) {
                    throw new ChatbotUpstreamException(
                            UpstreamFailureCategory.UNAVAILABLE,
                            tenantId.toString(),
                            baseUrl,
                            null,
                            true,
                            warmupWaited,
                            "LLM process exited before becoming healthy",
                            null
                    );
                }

                if (isHealthy(baseUrl)) {
                    log.info("LLM READY tenant={} baseUrl={} pid={} coldStart=true warmupWaited={}", tenantId, baseUrl, pid, warmupWaited);
                    return new Running(baseUrl, pid, Instant.now());
                }

                long now = System.currentTimeMillis();
                if (now - lastLog > 5000) {
                    log.info("Waiting LLM healthy tenant={} baseUrl={} coldStart=true warmupWaited={}", tenantId, baseUrl, warmupWaited);
                    lastLog = now;
                }

                Thread.sleep(300);
            }

            process.destroyForcibly();
            throw new ChatbotUpstreamException(
                    UpstreamFailureCategory.TIMEOUT,
                    tenantId.toString(),
                    baseUrl,
                    null,
                    true,
                    warmupWaited,
                    "Timed out waiting for chatbot warmup",
                    null
            );
        } catch (ChatbotUpstreamException e) {
            processByTenant.remove(tenantId);
            runtimeKbByTenant.remove(tenantId);
            log.warn(
                    "LLM startup failure tenant={} baseUrl={} category={} coldStart={} warmupWaited={} message={}",
                    e.getTenantId(),
                    e.getBaseUrl(),
                    e.getCategory(),
                    e.isColdStart(),
                    e.isWarmupWaited(),
                    e.getMessage(),
                    e
            );
            throw e;
        } catch (IllegalStateException e) {
            throw spawnConfigException(tenantId, e.getMessage());
        } catch (Exception e) {
            processByTenant.remove(tenantId);
            runtimeKbByTenant.remove(tenantId);
            throw new ChatbotUpstreamException(
                    UpstreamFailureCategory.UNAVAILABLE,
                    tenantId.toString(),
                    baseUrl,
                    null,
                    true,
                    warmupWaited,
                    "Failed to start local Python chatbot process. Prefer PYTHON_LLM_BASE_URL for deploy/runtime; otherwise verify PYTHON_BIN="
                            + props.getPythonBin() + ", MODEL_SERVER_DIR=" + props.getModelServerDir() + ", port=" + port,
                    e
            );
        } finally {
            reservedPorts.remove(port);
        }
    }

    ResolvedTenantKbDirectory resolveKbDirectoryForTenant(UUID tenantId) {
        return tenantKbDirectoryResolver.resolve(tenantId);
    }

    void recordSpawnedRuntimeKb(UUID tenantId, ResolvedTenantKbDirectory resolvedKbDirectory, long pid, Instant startedAt, Process process) {
        if (process != null) {
            processByTenant.put(tenantId, process);
        }
        runtimeKbByTenant.put(
                tenantId,
                new RuntimeKbMetadata(
                        resolvedKbDirectory.kbDir(),
                        resolvedKbDirectory.source().name(),
                        resolvedKbDirectory.versionId(),
                        resolvedKbDirectory.versionTag(),
                        startedAt,
                        pid
                )
        );
    }

    public RuntimeKbStatusSnapshot getRuntimeKbStatus(UUID tenantId) {
        ResolvedTenantKbDirectory resolved = tenantKbDirectoryResolver.resolve(tenantId);
        RuntimeKbDesiredSnapshot desired = new RuntimeKbDesiredSnapshot(
                resolved.kbDir(),
                resolved.source().name(),
                resolved.versionId(),
                resolved.versionTag(),
                resolved.fallbackReason()
        );

        RuntimeKbMetadata running = runtimeKbByTenant.get(tenantId);
        if (running != null) {
            Process process = processByTenant.get(tenantId);
            boolean processAlive = process != null && process.isAlive();
            Running runningRecord = runningByTenant.get(tenantId);
            Instant lastUsedAt = runningRecord != null ? runningRecord.lastUsedAt() : null;
            RuntimeKbRunningSnapshot runningSnapshot = new RuntimeKbRunningSnapshot(
                    OBSERVABILITY_JAVA_SPAWNED,
                    running.kbDir(),
                    running.source(),
                    running.versionId(),
                    running.versionTag(),
                    running.startedAt(),
                    lastUsedAt,
                    processAlive,
                    running.pid(),
                    null,
                    null,
                    null,
                    null
            );
            return new RuntimeKbStatusSnapshot(
                    tenantId,
                    desired,
                    runningSnapshot,
                    isRuntimeKbInSync(desired, runningSnapshot)
            );
        }

        String externalBaseUrl = normalizedExternalBaseUrl();
        if (shouldUseExternalRuntime(resolved, externalBaseUrl)) {
            ExternalHealthSnapshot external = fetchExternalHealth(externalBaseUrl);
            RuntimeKbRunningSnapshot runningSnapshot = new RuntimeKbRunningSnapshot(
                    OBSERVABILITY_EXTERNAL_BASE_URL,
                    external.kbDir(),
                    HEALTH_SOURCE_EXTERNAL,
                    null,
                    external.versionTag(),
                    null,
                    null,
                    null,
                    null,
                    external.note(),
                    external.ready(),
                    external.kbLoaded(),
                    external.retrievalMode()
            );
            return new RuntimeKbStatusSnapshot(
                    tenantId,
                    desired,
                    runningSnapshot,
                    external.kbDir() == null ? null : isRuntimeKbInSync(desired, runningSnapshot)
            );
        }

        return new RuntimeKbStatusSnapshot(tenantId, desired, null, false);
    }

    private boolean shouldUseExternalRuntime(ResolvedTenantKbDirectory resolvedKbDirectory, String externalBaseUrl) {
        if (externalBaseUrl == null || externalBaseUrl.isBlank()) {
            return false;
        }
        return !isTenantSpecificKb(resolvedKbDirectory);
    }

    private boolean isTenantSpecificKb(ResolvedTenantKbDirectory resolvedKbDirectory) {
        if (resolvedKbDirectory == null) {
            return false;
        }
        if (resolvedKbDirectory.kbDir() == null || resolvedKbDirectory.kbDir().isBlank()) {
            return false;
        }
        return resolvedKbDirectory.versionId() != null
                || resolvedKbDirectory.versionTag() != null
                || resolvedKbDirectory.source() == TenantKbDirectorySource.ACTIVE_VERSION;
    }

    private boolean matchesResolvedKb(RuntimeKbMetadata runtime, ResolvedTenantKbDirectory resolvedKbDirectory) {
        return java.util.Objects.equals(runtime.kbDir(), resolvedKbDirectory.kbDir())
                && java.util.Objects.equals(runtime.source(), resolvedKbDirectory.source().name())
                && java.util.Objects.equals(runtime.versionId(), resolvedKbDirectory.versionId())
                && java.util.Objects.equals(runtime.versionTag(), resolvedKbDirectory.versionTag());
    }

    private ExternalHealthSnapshot fetchExternalHealth(String baseUrl) {
        try {
            HealthzResponse response = http.get()
                    .uri(baseUrl + props.getHealthPath())
                    .retrieve()
                    .bodyToMono(HealthzResponse.class)
                    .block(EXTERNAL_HEALTH_TIMEOUT);
            if (response == null) {
                return new ExternalHealthSnapshot(null, null, null, null, null, NOTE_EXTERNAL_HEALTH_FAILED);
            }
            return new ExternalHealthSnapshot(
                    response.kbDir(),
                    inferVersionTagFromKbDir(response.kbDir()),
                    response.ready(),
                    response.kbLoaded(),
                    response.retrievalMode(),
                    NOTE_EXTERNAL_UNAVAILABLE
            );
        } catch (Exception ignored) {
            return new ExternalHealthSnapshot(null, null, null, null, null, NOTE_EXTERNAL_HEALTH_FAILED);
        }
    }

    String inferVersionTagFromKbDir(String kbDir) {
        if (kbDir == null || kbDir.isBlank()) {
            return null;
        }
        try {
            Path path = Path.of(kbDir);
            int count = path.getNameCount();
            for (int i = 0; i < count - 1; i++) {
                if (VERSION_SEGMENT.equals(path.getName(i).toString())) {
                    String candidate = path.getName(i + 1).toString();
                    return candidate.isBlank() ? null : candidate;
                }
            }
        } catch (Exception ignored) {
        }

        String[] parts = kbDir.split(PATH_SEPARATOR_REGEX);
        for (int i = 0; i < parts.length - 1; i++) {
            if (VERSION_SEGMENT.equals(parts[i])) {
                String candidate = parts[i + 1];
                return candidate.isBlank() ? null : candidate;
            }
        }
        return null;
    }

    private boolean isRuntimeKbInSync(RuntimeKbDesiredSnapshot desired, RuntimeKbRunningSnapshot running) {
        return java.util.Objects.equals(desired.kbDir(), running.kbDir())
                && java.util.Objects.equals(desired.source(), running.source())
                && java.util.Objects.equals(desired.versionId(), running.versionId())
                && java.util.Objects.equals(desired.versionTag(), running.versionTag());
    }

    private ChatbotUpstreamException spawnConfigException(UUID tenantId, String message) {
        return new ChatbotUpstreamException(
                UpstreamFailureCategory.UNAVAILABLE,
                tenantId.toString(),
                null,
                null,
                true,
                false,
                message,
                null
        );
    }

    private int pickPortReserved() {
        for (int port = props.getPortRangeStart(); port <= props.getPortRangeEnd(); port++) {
            if (reservedPorts.contains(port)) {
                continue;
            }
            if (isPortFree(port)) {
                return port;
            }
        }
        throw new IllegalStateException("No free port in range " +
                props.getPortRangeStart() + "-" + props.getPortRangeEnd());
    }

    private String normalizedExternalBaseUrl() {
        String baseUrl = props.getBaseUrl();
        if (baseUrl == null || baseUrl.isBlank()) {
            return "";
        }
        String normalized = baseUrl.trim();
        while (normalized.endsWith("/")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        return normalized;
    }

    private boolean isPortFree(int port) {
        try (ServerSocket s = new ServerSocket(port)) {
            s.setReuseAddress(true);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    @PreDestroy
    public void shutdownAll() {
        for (UUID tenantId : processByTenant.keySet()) {
            evictTenant(tenantId);
        }
        runningByTenant.clear();
        runtimeKbByTenant.clear();
    }

    public Map<UUID, Running> dumpRunning() {
        return Map.copyOf(runningByTenant);
    }

    public Map<UUID, RuntimeStatusSnapshot> dumpRuntimeStatuses() {
        Map<UUID, RuntimeStatusSnapshot> snapshots = new ConcurrentHashMap<>();
        for (var entry : runningByTenant.entrySet()) {
            Running running = entry.getValue();
            snapshots.put(
                    entry.getKey(),
                    new RuntimeStatusSnapshot(
                            entry.getKey(),
                            running.baseUrl(),
                            running.pid(),
                            running.lastUsedAt(),
                            isHealthy(running.baseUrl())
                    )
            );
        }
        return Map.copyOf(snapshots);
    }

    public void evictTenant(UUID tenantId) {
        runningByTenant.remove(tenantId);
        runtimeKbByTenant.remove(tenantId);
        Process process = processByTenant.remove(tenantId);
        if (process == null) {
            return;
        }

        try {
            if (process.isAlive()) {
                process.destroy();
                process.waitFor(2, java.util.concurrent.TimeUnit.SECONDS);
                if (process.isAlive()) {
                    process.destroyForcibly();
                }
            }
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            if (process.isAlive()) {
                process.destroyForcibly();
            }
        }
    }
}
