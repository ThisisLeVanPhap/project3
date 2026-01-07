package com.app.modelserver;

import com.app.bots.ChatbotInstance;
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

@Slf4j
@Service
@RequiredArgsConstructor
public class LlmInstanceManager {

    private final LlmProperties props;

    private final Duration idleTtl = Duration.ofMinutes(15);

    public record Running(String baseUrl, long pid, Instant lastUsedAt) {}

    private final Map<UUID, Running> runningByTenant = new ConcurrentHashMap<>();
    private final WebClient http = WebClient.builder().build();

    public String getOrStartBaseUrl(UUID tenantId, ChatbotInstance botCfg) {
        Running r = runningByTenant.get(tenantId);
        if (r != null && isHealthy(r.baseUrl())) {
            runningByTenant.put(tenantId, new Running(r.baseUrl(), r.pid(), Instant.now()));
            return r.baseUrl();
        }
        runningByTenant.remove(tenantId);

        log.info("LLM props pythonBin={}, modelServerDir={}", props.getPythonBin(), props.getModelServerDir());

        Running spawned = spawn(tenantId, botCfg);
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

    private Running spawn(UUID tenantId, ChatbotInstance botCfg) {
        // validate config rõ ràng (để không bị null mà không biết)
        if (props.getPythonBin() == null || props.getPythonBin().isBlank()) {
            throw new IllegalStateException("Missing config: python.llm.python-bin");
        }
        if (props.getModelServerDir() == null || props.getModelServerDir().isBlank()) {
            throw new IllegalStateException("Missing config: python.llm.model-server-dir");
        }

        int port = pickPort();
        String baseUrl = "http://" + props.getHost() + ":" + port;

        try {
            File dir = new File(props.getModelServerDir());
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

            log.info("Spawning LLM instance tenant={} -> {} (python={}, dir={})",
                    tenantId, baseUrl, props.getPythonBin(), dir.getAbsolutePath());

            Process p = pb.start();
            long pid = p.pid();

            // ✅ DRAIN LOG của uvicorn để thấy lỗi thật (import fail / thiếu uvicorn / v.v.)
            new Thread(() -> {
                try (var br = new java.io.BufferedReader(
                        new java.io.InputStreamReader(p.getInputStream()))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        log.info("[llm:{} pid={}] {}", tenantId, pid, line);
                    }
                } catch (Exception ex) {
                    log.warn("[llm:{} pid={}] log stream closed: {}", tenantId, pid, ex.toString());
                }
            }, "llm-log-" + tenantId).start();

            long deadline = System.currentTimeMillis() + 120_000;
            long lastLog = 0;
            while (System.currentTimeMillis() < deadline) {
                if (isHealthy(baseUrl)) {
                    log.info("LLM READY tenant={} -> {} (pid={})", tenantId, baseUrl, pid);
                    return new Running(baseUrl, pid, Instant.now());
                }
                // nếu process chết sớm thì báo ngay, khỏi chờ đủ 30s
                if (!p.isAlive()) {
                    throw new IllegalStateException("LLM process exited early (pid=" + pid + ")");
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
                            + ", modelServerDir=" + props.getModelServerDir() + ")",
                    e
            );
        }
    }

    private int pickPort() {
        for (int port = props.getPortRangeStart(); port <= props.getPortRangeEnd(); port++) {
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
}
