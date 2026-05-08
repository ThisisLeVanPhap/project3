package com.app.modelserver;

import com.app.bots.ChatbotInstance;
import com.app.tenants.TenantRepository;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.File;
import java.net.ServerSocket;
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

    private final LlmProperties props;
    private final TenantRepository tenantRepo;

    private final Duration idleTtl = Duration.ofMinutes(15);

    public record Running(String baseUrl, long pid, Instant lastUsedAt) {}

    public record Session(String baseUrl, boolean coldStart, boolean warmupWaited) {}

    public record RuntimeStatusSnapshot(
            UUID tenantId,
            String baseUrl,
            long pid,
            Instant lastUsedAt,
            boolean healthy
    ) {}

    private final Map<UUID, Running> runningByTenant = new ConcurrentHashMap<>();
    private final Map<UUID, Process> processByTenant = new ConcurrentHashMap<>();
    private final Map<UUID, ReentrantLock> tenantSpawnLocks = new ConcurrentHashMap<>();
    private final WebClient http = WebClient.builder().build();

    private final ReentrantLock spawnLock = new ReentrantLock();
    private final Set<Integer> reservedPorts = ConcurrentHashMap.newKeySet();

    public String getOrStartBaseUrl(UUID tenantId, ChatbotInstance botCfg) {
        return getOrStartSession(tenantId, botCfg).baseUrl();
    }

    public Session getOrStartSession(UUID tenantId, ChatbotInstance botCfg) {
        Running current = runningByTenant.get(tenantId);
        if (current != null && isHealthy(current.baseUrl())) {
            runningByTenant.put(tenantId, new Running(current.baseUrl(), current.pid(), Instant.now()));
            return new Session(current.baseUrl(), false, false);
        }
        runningByTenant.remove(tenantId);

        ReentrantLock tenantLock = tenantSpawnLocks.computeIfAbsent(tenantId, ignored -> new ReentrantLock());
        boolean warmupWaited = !tenantLock.tryLock();
        if (warmupWaited) {
            log.info("Waiting for in-flight LLM startup tenant={}", tenantId);
            tenantLock.lock();
        }

        try {
            Running existing = runningByTenant.get(tenantId);
            if (existing != null && isHealthy(existing.baseUrl())) {
                runningByTenant.put(tenantId, new Running(existing.baseUrl(), existing.pid(), Instant.now()));
                return new Session(existing.baseUrl(), false, warmupWaited);
            }
            runningByTenant.remove(tenantId);

            log.info("LLM props tenant={} pythonBin={} modelServerDir={}", tenantId, props.getPythonBin(), props.getModelServerDir());

            Running spawned = spawn(tenantId, warmupWaited);
            runningByTenant.put(tenantId, spawned);
            return new Session(spawned.baseUrl(), true, warmupWaited);
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

    private Running spawn(UUID tenantId, boolean warmupWaited) {
        if (props.getPythonBin() == null || props.getPythonBin().isBlank()) {
            throw new IllegalStateException("Missing config: python.llm.python-bin");
        }
        if (props.getModelServerDir() == null || props.getModelServerDir().isBlank()) {
            throw new IllegalStateException("Missing config: python.llm.model-server-dir");
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
                throw new IllegalStateException("Invalid model-server-dir: " + dir.getAbsolutePath());
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

            String kbDir = tenantRepo.findKbDirById(tenantId).orElse(null);
            if (kbDir == null || kbDir.isBlank()) {
                log.warn("Tenant {} has no kb_dir set. RAG will be disabled for this tenant.", tenantId);
            } else {
                pb.environment().put("KB_DIR", kbDir);
                log.info("Tenant {} KB_DIR={}", tenantId, kbDir);
            }

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
            processByTenant.put(tenantId, process);

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
        } catch (Exception e) {
            processByTenant.remove(tenantId);
            throw new RuntimeException(
                    "Failed to start LLM instance for tenant=" + tenantId
                            + " (python=" + props.getPythonBin()
                            + ", modelServerDir=" + props.getModelServerDir()
                            + ", port=" + port + ")",
                    e
            );
        } finally {
            reservedPorts.remove(port);
        }
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
