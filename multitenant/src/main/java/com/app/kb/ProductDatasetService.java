package com.app.kb;

import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.LlmProperties;
import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Service
public class ProductDatasetService {

    private static final DateTimeFormatter VERSION_TAG_FORMATTER = DateTimeFormatter
            .ofPattern("'dataset-'yyyyMMddHHmmss")
            .withZone(ZoneOffset.UTC);

    private final ProductDatasetRepository productDatasetRepository;
    private final TenantRepository tenantRepository;
    private final TenantKbVersionRepository tenantKbVersionRepository;
    private final LlmProperties llmProperties;
    private final LlmInstanceManager llmInstanceManager;
    private final ObjectMapper objectMapper;

    public ProductDatasetService(
            ProductDatasetRepository productDatasetRepository,
            TenantRepository tenantRepository,
            TenantKbVersionRepository tenantKbVersionRepository,
            LlmProperties llmProperties,
            LlmInstanceManager llmInstanceManager,
            ObjectMapper objectMapper
    ) {
        this.productDatasetRepository = productDatasetRepository;
        this.tenantRepository = tenantRepository;
        this.tenantKbVersionRepository = tenantKbVersionRepository;
        this.llmProperties = llmProperties;
        this.llmInstanceManager = llmInstanceManager;
        this.objectMapper = objectMapper;
    }

    public ProductDatasetResponse register(ProductDatasetRegisterRequest request) {
        String requestedDatasetId = normalizeRequired(request.datasetId(), "dataset_id is required");
        Path datasetDir = resolvePath(normalizeRequired(request.path(), "path is required"));
        if (!Files.isDirectory(datasetDir)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Dataset folder not found: " + datasetDir);
        }
        Path manifestPath = datasetDir.resolve("manifest.json").normalize();
        if (!Files.isRegularFile(manifestPath)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "manifest.json not found: " + manifestPath);
        }
        if (productDatasetRepository.findByDatasetId(requestedDatasetId).isPresent()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Dataset already registered: " + requestedDatasetId);
        }

        JsonNode manifest = readManifest(manifestPath);
        String manifestDatasetId = text(manifest, "dataset_id");
        if (manifestDatasetId != null && !manifestDatasetId.equals(requestedDatasetId)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "dataset_id does not match manifest");
        }

        Path ragProducts = datasetFile(datasetDir, manifest, "rag_products", "rag_products.jsonl");
        ProductDatasetStatus status = Files.isRegularFile(ragProducts)
                ? ProductDatasetStatus.REGISTERED
                : ProductDatasetStatus.MISSING_FILES;

        ProductDataset dataset = new ProductDataset();
        dataset.setDatasetId(requestedDatasetId);
        dataset.setSource(firstNonBlank(request.source(), text(manifest, "source")));
        dataset.setSourceUrl(firstNonBlank(request.sourceUrl(), text(manifest, "source_url")));
        dataset.setVersion(request.version());
        dataset.setPath(datasetDir.toString());
        dataset.setProductCount(intValue(manifest, "product_count"));
        dataset.setRagChunkCount(intValue(manifest, "rag_chunk_count"));
        dataset.setContentHash(firstNonBlank(text(manifest, "content_hash"), computeContentHash(datasetDir, manifest)));
        dataset.setManifestPath(manifestPath.toString());
        dataset.setCreatedAt(parseInstant(text(manifest, "created_at")));
        dataset.setStatus(status);
        return ProductDatasetResponse.from(productDatasetRepository.save(dataset));
    }

    public List<ProductDatasetResponse> list() {
        return productDatasetRepository.findAllByOrderByRegisteredAtDesc().stream()
                .map(ProductDatasetResponse::from)
                .toList();
    }

    public ProductDatasetResponse get(UUID id) {
        return ProductDatasetResponse.from(requireDataset(id));
    }

    public void delete(UUID id) {
        ProductDataset dataset = requireDataset(id);
        productDatasetRepository.delete(dataset);
    }

    public ProductDatasetAssignResponse assignToTenant(UUID datasetRecordId, ProductDatasetAssignRequest request) {
        ProductDataset dataset = requireDataset(datasetRecordId);
        Tenant tenant = requireTenant(request);
        Path datasetDir = resolvePath(dataset.getPath());
        Path manifestPath = dataset.getManifestPath() == null || dataset.getManifestPath().isBlank()
                ? datasetDir.resolve("manifest.json")
                : resolvePath(dataset.getManifestPath());
        JsonNode manifest = readManifest(manifestPath);
        Path ragProducts = datasetFile(datasetDir, manifest, "rag_products", "rag_products.jsonl");
        if (!Files.isRegularFile(ragProducts)) {
            dataset.setStatus(ProductDatasetStatus.MISSING_FILES);
            productDatasetRepository.save(dataset);
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "rag_products.jsonl not found: " + ragProducts);
        }

        Instant startedAt = Instant.now();
        String versionTag = nextVersionTag(tenant.getId(), dataset.getDatasetId(), startedAt);
        File chatbotDir = new File(llmProperties.getModelServerDir()).getAbsoluteFile();
        if (!chatbotDir.isDirectory()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid model-server-dir: " + chatbotDir.getAbsolutePath());
        }
        Path kbBase = chatbotDir.toPath().resolve("kb").toAbsolutePath().normalize();
        Path tenantKbRoot = kbBase.resolve(tenant.getCode()).normalize();
        Path versionDir = tenantKbRoot.resolve("versions").resolve(versionTag).normalize();

        ScriptResult scriptResult;
        try {
            scriptResult = runImportScript(chatbotDir, datasetDir, tenant.getCode(), kbBase, versionTag);
        } catch (RuntimeException ex) {
            dataset.setStatus(ProductDatasetStatus.FAILED);
            productDatasetRepository.save(dataset);
            throw ex;
        }

        Instant assignedAt = Instant.now();
        Integer chunkCount = scriptResult.chunkCount();
        if (chunkCount == null) {
            chunkCount = countLines(versionDir.resolve("chunks.jsonl"));
        }

        TenantKbVersion kbVersion = new TenantKbVersion();
        kbVersion.setTenantId(tenant.getId());
        kbVersion.setVersionTag(versionTag);
        kbVersion.setKbDir(scriptResult.kbDir() == null ? versionDir.toString() : scriptResult.kbDir());
        kbVersion.setSourceUrlSnapshot(manifest.toString());
        kbVersion.setSourceType("PRODUCT_DATASET");
        kbVersion.setDatasetId(dataset.getDatasetId());
        kbVersion.setArtifactCount(chunkCount);
        kbVersion.setStatus(TenantKbVersionStatus.READY);
        kbVersion.setBuildMessage("Imported from product dataset " + dataset.getDatasetId());
        kbVersion.setBuiltAt(assignedAt);
        kbVersion.setPublishedAt(assignedAt);
        kbVersion = tenantKbVersionRepository.save(kbVersion);

        tenant.setKbDir(tenantKbRoot.toString());
        tenant.setActiveKbVersionId(kbVersion.getId());
        tenantRepository.save(tenant);
        llmInstanceManager.evictTenant(tenant.getId());

        dataset.setStatus(ProductDatasetStatus.ASSIGNED);
        dataset.setLastAssignedTenantId(tenant.getId());
        dataset.setLastAssignedAt(assignedAt);
        productDatasetRepository.save(dataset);

        return new ProductDatasetAssignResponse(
                true,
                dataset.getDatasetId(),
                tenant.getId(),
                tenant.getCode(),
                kbVersion.getKbDir(),
                chunkCount,
                kbVersion.getId(),
                versionTag,
                assignedAt,
                "Imported from product dataset " + dataset.getDatasetId()
        );
    }

    private ProductDataset requireDataset(UUID id) {
        return productDatasetRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Product dataset not found"));
    }

    private Tenant requireTenant(ProductDatasetAssignRequest request) {
        if (request.tenantId() != null) {
            return tenantRepository.findById(request.tenantId())
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Tenant not found"));
        }
        String tenantCode = normalizeRequired(request.tenantCode(), "tenant_code or tenantId is required");
        return tenantRepository.findByCodeIgnoreCase(tenantCode)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Tenant not found"));
    }

    private String nextVersionTag(UUID tenantId, String datasetId, Instant startedAt) {
        String safeDataset = datasetId.replaceAll("[^A-Za-z0-9_-]+", "-");
        String base = VERSION_TAG_FORMATTER.format(startedAt) + "-" + safeDataset;
        String candidate = base;
        int suffix = 2;
        while (tenantKbVersionRepository.findByTenantIdAndVersionTag(tenantId, candidate).isPresent()) {
            candidate = base + "-" + suffix;
            suffix++;
        }
        return candidate;
    }

    private ScriptResult runImportScript(File chatbotDir, Path datasetDir, String tenantCode, Path kbBase, String versionTag) {
        List<String> command = List.of(
                llmProperties.getPythonBin(),
                "tools/import_dataset.py",
                "--dataset-dir", datasetDir.toString(),
                "--tenant-code", tenantCode,
                "--kb-base", kbBase.toString(),
                "--version-tag", versionTag
        );
        ProcessBuilder processBuilder = new ProcessBuilder(command);
        processBuilder.directory(chatbotDir);
        processBuilder.redirectErrorStream(true);
        List<String> output = new ArrayList<>();
        try {
            Process process = processBuilder.start();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.add(line);
                }
            }
            int exitCode = process.waitFor();
            if (exitCode != 0) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Dataset import failed: " + summarizeOutput(output));
            }
            return parseScriptResult(output);
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Dataset import failed: unable to start Python tooling");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Dataset import failed: interrupted");
        }
    }

    private ScriptResult parseScriptResult(List<String> output) {
        Optional<String> jsonLine = output.stream()
                .map(String::trim)
                .filter(line -> line.startsWith("{") && line.endsWith("}"))
                .reduce((first, second) -> second);
        if (jsonLine.isEmpty()) {
            return new ScriptResult(null, null);
        }
        try {
            JsonNode root = objectMapper.readTree(jsonLine.get());
            return new ScriptResult(text(root, "kb_dir"), intValue(root, "chunk_count"));
        } catch (IOException ignored) {
            return new ScriptResult(null, null);
        }
    }

    private JsonNode readManifest(Path manifestPath) {
        try {
            return objectMapper.readTree(manifestPath.toFile());
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Unable to read manifest: " + manifestPath);
        }
    }

    private Path datasetFile(Path datasetDir, JsonNode manifest, String manifestKey, String fallback) {
        String fileName = manifest.path("files").path(manifestKey).asText(fallback);
        return datasetDir.resolve(fileName).normalize();
    }

    private String computeContentHash(Path datasetDir, JsonNode manifest) {
        Path primary = datasetFile(datasetDir, manifest, "rag_products", "rag_products.jsonl");
        if (!Files.isRegularFile(primary)) {
            primary = datasetFile(datasetDir, manifest, "catalog", "catalog.jsonl");
        }
        if (!Files.isRegularFile(primary)) {
            return null;
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            digest.update(Files.readAllBytes(primary));
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ignored) {
            return null;
        }
    }

    private Path resolvePath(String value) {
        Path path = Path.of(value);
        if (!path.isAbsolute()) {
            path = Path.of("").toAbsolutePath().resolve(path);
        }
        return path.normalize();
    }

    private String normalizeRequired(String value, String message) {
        String normalized = value == null ? "" : value.trim();
        if (normalized.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, message);
        }
        return normalized;
    }

    private String firstNonBlank(String first, String second) {
        String normalizedFirst = first == null ? "" : first.trim();
        return normalizedFirst.isBlank() ? second : normalizedFirst;
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

    private Instant parseInstant(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return Instant.parse(value);
        } catch (RuntimeException ignored) {
            return null;
        }
    }

    private Integer countLines(Path path) {
        if (!Files.exists(path)) {
            return null;
        }
        try (var lines = Files.lines(path)) {
            long count = lines.filter(line -> !line.isBlank()).count();
            return Math.toIntExact(count);
        } catch (IOException | ArithmeticException ignored) {
            return null;
        }
    }

    private String summarizeOutput(List<String> output) {
        if (output.isEmpty()) {
            return "no output";
        }
        return String.join(" | ", output.stream().limit(20).toList());
    }

    private record ScriptResult(String kbDir, Integer chunkCount) {
    }
}
