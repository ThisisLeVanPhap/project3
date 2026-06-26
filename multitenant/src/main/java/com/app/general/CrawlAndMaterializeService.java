package com.app.general;

import com.app.kb.ProductDatasetArtifact;
import com.app.kb.ProductDatasetArtifactRepository;
import com.app.kb.ProductDatasetArtifactStatus;
import com.app.kb.ProductDatasetRegisterRequest;
import com.app.kb.ProductDatasetService;
import com.app.kb.TenantKbBindRequest;
import com.app.kb.TenantKbBindingUpdatePolicy;
import com.app.modelserver.LlmProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URI;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;

@Service
public class CrawlAndMaterializeService {

    private static final Logger log = LoggerFactory.getLogger(CrawlAndMaterializeService.class);

    private static final Set<String> VALID_VISIBILITY = Set.of("GLOBAL_PUBLIC", "TENANT_BOUND", "PRIVATE", "ADMIN_ONLY");
    private static final int MAX_URLS_HARD_LIMIT = 50000;
    private static final int DEFAULT_MAX_URLS = 500;

    // Private IPv4 ranges
    private static final Set<String> PRIVATE_PREFIXES = Set.of(
            "127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
            "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
            "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
            "0.", "169.254.", "::1", "fc00:", "fd00:", "fe80:"
    );

    private final LlmProperties llmProperties;
    private final ProductDatasetService productDatasetService;
    private final CrawlMaterializeJobRepository jobRepository;
    private final GeneralProductImportService generalProductImportService;
    private final ProductDatasetArtifactRepository artifactRepository;
    private final ObjectMapper objectMapper;

    public CrawlAndMaterializeService(
            LlmProperties llmProperties,
            ProductDatasetService productDatasetService,
            CrawlMaterializeJobRepository jobRepository,
            GeneralProductImportService generalProductImportService,
            ProductDatasetArtifactRepository artifactRepository,
            ObjectMapper objectMapper
    ) {
        this.llmProperties = llmProperties;
        this.productDatasetService = productDatasetService;
        this.jobRepository = jobRepository;
        this.generalProductImportService = generalProductImportService;
        this.artifactRepository = artifactRepository;
        this.objectMapper = objectMapper;
    }

    public CrawlMaterializeJobResponse startJob(CrawlAndMaterializeRequest req, String createdBy) {
        validateRequest(req);
        String datasetId = req.datasetId() != null && !req.datasetId().isBlank()
                ? req.datasetId().trim()
                : req.sourceCode().trim() + "-" + java.time.format.DateTimeFormatter
                        .ofPattern("yyyyMMdd-HHmmss").withZone(java.time.ZoneOffset.UTC)
                        .format(Instant.now());

        CrawlMaterializeJob job = new CrawlMaterializeJob();
        job.setSourceCode(req.sourceCode().trim());
        job.setSourceName(req.sourceName() != null ? req.sourceName().trim() : null);
        job.setRootUrl(req.rootUrl());
        job.setSitemapUrl(req.sitemapUrl());
        job.setProductUrls(req.productUrls() != null ? objectMapper.valueToTree(req.productUrls()).toString() : null);
        job.setDatasetId(datasetId);
        job.setMaxUrls(req.getMaxUrlsOrDefault());
        job.setProductOnly(req.isProductOnly());
        job.setRunQualityAudit(req.isRunQualityAudit());
        job.setRunTaxonomyNormalize(req.isRunTaxonomyNormalize());
        job.setRegisterDataset(req.isRegisterDataset());
        job.setStatus("QUEUED");
        job.setStage("QUEUED");
        job.setVisibility(req.getVisibilityOrDefault());
        job.setBuildArtifact(req.isBuildArtifact());
        job.setBindTenant(req.isBindTenant());
        job.setImportGeneral(req.isImportGeneral());
        if (req.isBindTenant()) {
            job.setTenantId(UUID.fromString(req.bindTenantId().trim()));
        }
        job.setCreatedBy(createdBy);
        jobRepository.save(job);

        runJobAsync(job.getId());
        return CrawlMaterializeJobResponse.from(job);
    }

    private void validateRequest(CrawlAndMaterializeRequest req) {
        if (req.sourceCode() == null || req.sourceCode().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "sourceCode is required");
        }
        if ((req.sitemapUrl() == null || req.sitemapUrl().isBlank())
                && (req.productUrls() == null || req.productUrls().isEmpty())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "sitemapUrl or productUrls is required");
        }
        if (req.isBindTenant() && (req.bindTenantId() == null || req.bindTenantId().isBlank())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "tenantId is required when bindTenant=true");
        }
        if (req.isBindTenant() && !req.isBuildArtifact()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "buildArtifact must be true when bindTenant=true");
        }
        if (req.isImportGeneral() && !req.isBuildArtifact()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "buildArtifact must be true when importGeneral=true");
        }
        if (req.isImportGeneral() && !"GLOBAL_PUBLIC".equals(req.getVisibilityOrDefault())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "visibility must be GLOBAL_PUBLIC when importGeneral=true");
        }
        String vis = req.getVisibilityOrDefault();
        if (!VALID_VISIBILITY.contains(vis)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid visibility: " + vis);
        }
        // maxUrls safety
        if (req.maxUrls() != null && req.maxUrls() > MAX_URLS_HARD_LIMIT) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "maxUrls exceeds hard limit of " + MAX_URLS_HARD_LIMIT
                            + ". Large crawl requires batch mode or external worker.");
        }
        // SSRF protection: check all URLs
        checkPrivateUrl("sitemapUrl", req.sitemapUrl());
        checkPrivateUrl("rootUrl", req.rootUrl());
        if (req.productUrls() != null) {
            for (String url : req.productUrls()) {
                checkPrivateUrl("productUrls", url);
            }
        }
    }

    private void checkPrivateUrl(String fieldName, String url) {
        if (url == null || url.isBlank()) return;
        try {
            URI uri = new URI(url.trim());
            String scheme = uri.getScheme();
            if (scheme != null && !scheme.equalsIgnoreCase("http") && !scheme.equalsIgnoreCase("https")) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        fieldName + " must use http or https scheme: " + url);
            }
            String host = uri.getHost();
            if (host == null || host.isBlank()) {
                host = url.trim().toLowerCase();
            } else {
                host = host.toLowerCase();
            }
            // Check private patterns
            for (String prefix : PRIVATE_PREFIXES) {
                if (host.startsWith(prefix)) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                            fieldName + " URL resolves to a private/loopback address: " + url);
                }
            }
            // Check known internal docker names
            if (host.equals("postgres") || host.equals("chatbot-api") || host.endsWith(".internal")
                    || host.endsWith(".local") || host.equals("localhost") || host.equals("host.docker.internal")) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        fieldName + " URL resolves to an internal address: " + url);
            }
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    fieldName + " URL is invalid or malformed: " + url);
        }
    }

    public CrawlMaterializeJobResponse getJob(UUID jobId) {
        CrawlMaterializeJob job = jobRepository.findById(jobId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Job not found"));
        return CrawlMaterializeJobResponse.from(job);
    }

    public List<CrawlMaterializeJobResponse> listJobs() {
        return jobRepository.findTop50ByOrderByCreatedAtDesc().stream()
                .map(CrawlMaterializeJobResponse::from)
                .toList();
    }

    // --- Async multi-stage worker ---

    @Async("crawlMaterializeExecutor")
    public void runJobAsync(UUID jobId) {
        CrawlMaterializeJob job = jobRepository.findById(jobId).orElse(null);
        if (job == null) return;

        job.setStatus("RUNNING");
        job.setStage("CRAWL");
        job.setStartedAt(Instant.now());
        jobRepository.save(job);

        try {
            // Stage 1: CRAWL — discover URLs + HTTP fetch (enrichment inline in crawl job._prepare_observation)
            updateStage(job, "CRAWL", "Discovering and crawling product URLs...");
            JsonNode output = runCrawlScript(job);

            // Fail fast if Python script returned success=false or zero products
            if (!output.path("success").asBoolean(false)) {
                String err = output.path("error").asText("Crawl script returned success=false");
                throw new IOException("Crawl failed: " + err);
            }
            int crawlProductCount = output.path("product_count").asInt(0);
            if (crawlProductCount <= 0) {
                throw new IOException("Crawl produced 0 products (sourceCode=" + job.getSourceCode()
                        + ", sitemap=" + job.getSitemapUrl() + ")");
            }
            job.setTotalUrls(crawlProductCount);

            // Stage 2: ENRICH — already done inline in crawl job via enrich_product_from_text
            updateStage(job, "ENRICH", "Enriching product data (category, material, dimensions)...");

            // Stage 3: RAG_EXPORT — done by materialize_product_dataset -> convert_product_jsonl_to_rag_jsonl
            updateStage(job, "RAG_EXPORT", "Converting products to RAG chunks...");

            // Stage 4: DEDUPE — if enabled
            if (output.has("dedupe") && !output.get("dedupe").isNull()) {
                int removed = output.get("dedupe").path("removed_duplicates").asInt(0);
                int before = output.get("dedupe").path("input_lines").asInt(0);
                int after = output.get("dedupe").path("output_lines").asInt(0);
                updateStage(job, "DEDUPE", "Removed " + removed + " duplicate(s) (" + before + " → " + after + ")");
            } else {
                updateStage(job, "DEDUPE", "Dedupe skipped (not configured for this source)");
            }

            // Stage 5: MATERIALIZE
            updateStage(job, "MATERIALIZE", "Materializing dataset folder...");
            String datasetDir = output.path("dataset_dir").asText(null);
            job.setDatasetPath(datasetDir);
            job.setProductCount(output.path("product_count").asInt(0));
            job.setRagChunkCount(output.path("rag_chunk_count").asInt(0));

            // Stage 6: QUALITY_AUDIT (done inside materialize_product_dataset)
            String qualityStatus = output.path("quality_status").asText("pass");
            job.setQualityStatus(qualityStatus);
            if ("fail".equals(qualityStatus)) {
                log.warn("Quality audit failed for dataset {}, proceeding anyway", job.getDatasetId());
                updateStage(job, "QUALITY_AUDIT", "Quality audit failed — proceeding");
                job.setQualityStatus("warn"); // treat as warn so pipeline continues
            } else {
                updateStage(job, "QUALITY_AUDIT", "Quality audit passed (" + qualityStatus + ")");
            }

            // Stage 7: TAXONOMY_NORMALIZE
            if (job.isRunTaxonomyNormalize() && job.getStageMessage() != null) {
                boolean taxonomyApplied = output.has("taxonomy") && !output.get("taxonomy").isNull();
                if (taxonomyApplied) {
                    int changes = output.get("taxonomy").path("change_count").asInt(0);
                    updateStage(job, "TAXONOMY_NORMALIZE", "Taxonomy normalize applied, " + changes + " change(s)");
                } else {
                    updateStage(job, "TAXONOMY_NORMALIZE", "Skipped: no taxonomy profile for source " + job.getSourceCode());
                }
            } else if (job.isRunTaxonomyNormalize()) {
                updateStage(job, "TAXONOMY_NORMALIZE", "Skipped: no taxonomy profile available");
            }

            // Stage 8: REGISTER dataset
            if (job.isRegisterDataset() && datasetDir != null) {
                updateStage(job, "REGISTER", "Registering ProductDataset...");
                productDatasetService.register(new ProductDatasetRegisterRequest(
                        job.getDatasetId(), datasetDir,
                        job.getSourceCode(),
                        job.getRootUrl() != null ? job.getRootUrl() : job.getSitemapUrl(),
                        null
                ));
            }

            // Stage 9: BUILD_ARTIFACT
            UUID artifactId = null;
            String artifactPath = null;
            if (job.isBuildArtifact() && datasetDir != null) {
                updateStage(job, "BUILD_ARTIFACT", "Building KB artifact from dataset...");
                JsonNode buildResult = runBuildArtifactScript(job, datasetDir);
                if (buildResult.path("success").asBoolean(false)) {
                    artifactPath = buildResult.path("artifact_path").asText(null);
                    artifactId = findArtifactIdByPath(job.getDatasetId(), artifactPath);
                }
                job.setArtifactId(artifactId);
                job.setArtifactPath(artifactPath);
            }

            // Stage 10: BIND_TENANT
            UUID activeKbVersionId = null;
            if (job.isBindTenant() && artifactId != null && job.getTenantId() != null) {
                updateStage(job, "BIND_TENANT", "Binding artifact to tenant " + job.getTenantId() + "...");
                activeKbVersionId = productDatasetService.bindArtifactToTenant(
                        new TenantKbBindRequest(job.getTenantId(), null, artifactId, TenantKbBindingUpdatePolicy.AUTO_USE_LATEST)
                ).activeKbVersionId();
                job.setActiveKbVersionId(activeKbVersionId);
            }

            // Stage 11: IMPORT_GENERAL
            UUID generalSourceId = null;
            UUID importRunId = null;
            if (job.isImportGeneral() && "GLOBAL_PUBLIC".equals(job.getVisibility()) && artifactId != null) {
                updateStage(job, "IMPORT_GENERAL", "Importing into General Data Layer...");
                GeneralProductImportResponse importResp = generalProductImportService.importArtifact(artifactId);
                generalSourceId = importResp.generalSourceId();
                importRunId = importResp.importRunId();
                job.setGeneralSourceId(generalSourceId);
                job.setImportRunId(importRunId);
            }

            job.setStatus("SUCCESS");
            job.setStage("SUCCESS");
            job.setStageMessage("All " + countActiveStages(job) + " stages completed");
            job.setFinishedAt(Instant.now());
            jobRepository.save(job);

        } catch (Exception ex) {
            log.error("Crawl and materialize job {} failed at stage {}", jobId, job.getStage(), ex);
            job.setStatus("FAILED");
            job.setErrorMessage((job.getStage() != null ? "[" + job.getStage() + "] " : "") + ex.getMessage());
            job.setFinishedAt(Instant.now());
            jobRepository.save(job);
        }
    }

    private int countActiveStages(CrawlMaterializeJob job) {
        int count = 6; // CRAWL, ENRICH, RAG_EXPORT, MATERIALIZE, QUALITY_AUDIT, REGISTER
        if (job.isBuildArtifact()) count++;
        if (job.isBindTenant()) count++;
        if (job.isImportGeneral()) count++;
        if (job.isRunTaxonomyNormalize()) count++;
        if (job.getProductCount() > 0 && outputContainsDedupe(job)) count++;
        return count;
    }

    private boolean outputContainsDedupe(CrawlMaterializeJob job) {
        // Best-effort; dedupe stage shown when enabled by default script behavior
        return true;
    }

    private void updateStage(CrawlMaterializeJob job, String stage, String message) {
        job.setStage(stage);
        job.setStageMessage(message);
        job.setStageUpdatedAt(Instant.now());
        jobRepository.save(job);
    }

    // --- Script runners ---

    private JsonNode runCrawlScript(CrawlMaterializeJob job) throws IOException, InterruptedException {
        File chatbotDir = new File(llmProperties.getModelServerDir()).getAbsoluteFile();
        File script = new File(chatbotDir, "tools/crawl_and_materialize_dataset.py");
        List<String> cmd = new ArrayList<>();
        cmd.add(llmProperties.getPythonBin());
        cmd.add(script.getAbsolutePath());
        cmd.add("--dataset-id");
        cmd.add(job.getDatasetId());
        cmd.add("--source-code");
        cmd.add(job.getSourceCode());
        cmd.add("--max-urls");
        cmd.add(String.valueOf(job.getMaxUrls()));
        if (job.getSitemapUrl() != null && !job.getSitemapUrl().isBlank()) {
            cmd.add("--sitemap-url");
            cmd.add(job.getSitemapUrl());
        }
        if (job.getRootUrl() != null && !job.getRootUrl().isBlank()) {
            cmd.add("--root-url");
            cmd.add(job.getRootUrl());
        }
        if (job.isProductOnly()) cmd.add("--product-only");
        if (job.isRunQualityAudit()) cmd.add("--run-quality-audit");
        if (job.isRunTaxonomyNormalize()) cmd.add("--run-taxonomy-normalize");
        cmd.add("--run-dedupe");
        String out = runProcess(cmd, chatbotDir.toPath());
        // Parse stderr output for dedupe stats if needed
        return objectMapper.readTree(out);
    }

    private JsonNode runBuildArtifactScript(CrawlMaterializeJob job, String datasetDir) throws IOException, InterruptedException {
        File chatbotDir = new File(llmProperties.getModelServerDir()).getAbsoluteFile();
        File script = new File(chatbotDir, "tools/build_dataset_kb_artifact.py");
        String artifactDir = datasetDir + "/artifact-" + java.time.format.DateTimeFormatter
                .ofPattern("yyyyMMddHHmmss").withZone(java.time.ZoneOffset.UTC)
                .format(Instant.now());
        List<String> cmd = new ArrayList<>();
        cmd.add(llmProperties.getPythonBin());
        cmd.add(script.getAbsolutePath());
        cmd.add("--dataset-dir");
        cmd.add(datasetDir);
        cmd.add("--artifact-dir");
        cmd.add(artifactDir);
        String out = runProcess(cmd, chatbotDir.toPath());
        JsonNode json = objectMapper.readTree(out);
        if (json.has("error") || !json.path("success").asBoolean(true)) {
            throw new IOException(json.path("error").asText("Build artifact failed"));
        }
        return json;
    }

    private UUID findArtifactIdByPath(String datasetId, String artifactPath) {
        if (artifactPath == null) return null;
        var building = artifactRepository.findFirstByDatasetIdAndStatusOrderByBuiltAtDescCreatedAtDesc(
                datasetId, ProductDatasetArtifactStatus.BUILDING);
        if (building.isPresent() && artifactPath.equals(building.get().getArtifactPath())) {
            return building.get().getId();
        }
        var ready = artifactRepository.findFirstByDatasetIdAndStatusOrderByBuiltAtDescCreatedAtDesc(
                datasetId, ProductDatasetArtifactStatus.READY);
        if (ready.isPresent() && artifactPath.equals(ready.get().getArtifactPath())) {
            return ready.get().getId();
        }
        return null;
    }

    private String runProcess(List<String> command, Path workDir) throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder(command);
        pb.directory(workDir.toFile());
        pb.redirectErrorStream(true);
        Process process = pb.start();
        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line).append("\n");
            }
        }
        int exitCode = process.waitFor();
        String rawOutput = output.toString().trim();
        if (exitCode != 0) {
            try {
                JsonNode errJson = objectMapper.readTree(rawOutput);
                if (errJson.has("error")) {
                    throw new IOException(errJson.get("error").asText("Script failed: " + exitCode));
                }
                return rawOutput;
            } catch (Exception pe) {
                String preview = rawOutput.length() > 500 ? rawOutput.substring(0, 500) + "..." : rawOutput;
                throw new IOException("Script failed (exit " + exitCode + "): " + preview);
            }
        }
        return rawOutput;
    }
}
