package com.app.modelserver;

import com.app.bots.ChatbotInstance;
import com.app.tenants.TenantRepository;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.File;
import java.net.ServerSocket;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Set;
import java.util.concurrent.locks.ReentrantLock;

@Slf4j
@Service
@RequiredArgsConstructor
public class LlmInstanceManager {

    private final LlmProperties props;
    private final TenantRepository tenantRepo;

    private final Duration idleTtl = Duration.ofMinutes(15);

    public record Running(String baseUrl, long pid, Instant lastUsedAt) {}

    private final Map<UUID, Running> runningByTenant = new ConcurrentHashMap<>();
    private final WebClient http = WebClient.builder().build();

    private final ReentrantLock spawnLock = new ReentrantLock();
    private final Set<Integer> reservedPorts = ConcurrentHashMap.newKeySet();

    public String getOrStartBaseUrl(UUID tenantId, ChatbotInstance botCfg) {
        Running r = runningByTenant.get(tenantId);
        if (r != null && isHealthy(r.baseUrl())) {
            runningByTenant.put(tenantId, new Running(r.baseUrl(), r.pid(), Instant.now()));
            return r.baseUrl();
        }
        runningByTenant.remove(tenantId);

        log.info("LLM props pythonBin={}, modelServerDir={}", props.getPythonBin(), props.getModelServerDir());

        Running spawned = spawn(tenantId);
        runningByTenant.put(tenantId, spawned);
        return spawned.baseUrl();
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
            HttpStatusCode code = http.get()
                    .uri(baseUrl + props.getHealthPath())
                    .retrieve()
                    .toBodilessEntity()
                    .map(resp -> resp.getStatusCode())
                    .onErrorReturn(HttpStatusCode.valueOf(503))
                    .block(Duration.ofSeconds(1));
            return code != null && code.is2xxSuccessful();
        } catch (Exception ignored) {
            return false;
        }
    }

    private Running spawn(UUID tenantId) {
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

        Process p = null;
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

            // ✅ set KB_DIR theo tenant
            String kbDir = tenantRepo.findKbDirById(tenantId).orElse(null);
            if (kbDir == null || kbDir.isBlank()) {
                log.warn("Tenant {} has no kb_dir set. RAG will be disabled for this tenant.", tenantId);
            } else {
                pb.environment().put("KB_DIR", kbDir);
                log.info("Tenant {} KB_DIR={}", tenantId, kbDir);
            }

            log.info("Spawning LLM instance tenant={} -> {} (python={}, dir={})",
                    tenantId, baseUrl, props.getPythonBin(), dir.getAbsolutePath());

            p = pb.start();
            pid = p.pid();

            Process finalP = p;
            long finalPid = pid;
            new Thread(() -> {
                try (var br = new java.io.BufferedReader(new java.io.InputStreamReader(finalP.getInputStream()))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        log.info("[llm:{} pid={}] {}", tenantId, finalPid, line);
                    }
                } catch (Exception ex) {
                    log.warn("[llm:{} pid={}] log stream closed: {}", tenantId, finalPid, ex.toString());
                }
            }, "llm-log-" + tenantId).start();

            long deadline = System.currentTimeMillis() + 120_000;
            long lastLog = 0;

            while (System.currentTimeMillis() < deadline) {
                if (!p.isAlive()) {
                    throw new IllegalStateException("LLM process exited early (pid=" + pid + ", port=" + port + ")");
                }

                if (isHealthy(baseUrl)) {
                    log.info("LLM READY tenant={} -> {} (pid={})", tenantId, baseUrl, pid);
                    return new Running(baseUrl, pid, Instant.now());
                }

                long now = System.currentTimeMillis();
                if (now - lastLog > 5000) {
                    log.info("Waiting LLM healthy tenant={} at {}", tenantId, baseUrl);
                    lastLog = now;
                }

                Thread.sleep(300);
            }

            p.destroyForcibly();
            throw new IllegalStateException("LLM server not healthy for tenant=" + tenantId + " at " + baseUrl);

        } catch (Exception e) {
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
            if (reservedPorts.contains(port)) continue;
            if (isPortFree(port)) return port;
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
        runningByTenant.clear();
    }

    public Map<UUID, Running> dumpRunning() {
        return Map.copyOf(runningByTenant);
    }
}
