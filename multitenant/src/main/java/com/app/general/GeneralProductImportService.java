package com.app.general;

import com.app.kb.ProductDataset;
import com.app.kb.ProductDatasetArtifact;
import com.app.kb.ProductDatasetArtifactRepository;
import com.app.kb.ProductDatasetArtifactStatus;
import com.app.kb.ProductDatasetRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
public class GeneralProductImportService {

    private final ProductDatasetArtifactRepository artifactRepository;
    private final ProductDatasetRepository datasetRepository;
    private final GeneralSourceRepository generalSourceRepository;
    private final GeneralProductRepository generalProductRepository;
    private final GeneralProductChunkRepository generalProductChunkRepository;
    private final GeneralImportRunRepository generalImportRunRepository;
    private final ObjectMapper objectMapper;

    public GeneralProductImportService(
            ProductDatasetArtifactRepository artifactRepository,
            ProductDatasetRepository datasetRepository,
            GeneralSourceRepository generalSourceRepository,
            GeneralProductRepository generalProductRepository,
            GeneralProductChunkRepository generalProductChunkRepository,
            GeneralImportRunRepository generalImportRunRepository,
            ObjectMapper objectMapper
    ) {
        this.artifactRepository = artifactRepository;
        this.datasetRepository = datasetRepository;
        this.generalSourceRepository = generalSourceRepository;
        this.generalProductRepository = generalProductRepository;
        this.generalProductChunkRepository = generalProductChunkRepository;
        this.generalImportRunRepository = generalImportRunRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public GeneralProductImportResponse importArtifact(UUID artifactId) {
        ProductDatasetArtifact artifact = artifactRepository.findById(artifactId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Dataset artifact not found"));
        if (artifact.getStatus() != ProductDatasetArtifactStatus.READY) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Only READY artifacts can be imported into general products");
        }

        ProductDataset dataset = datasetRepository.findById(artifact.getDatasetRecordId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Dataset not found for artifact"));

        // Resolve source code from dataset metadata
        String sourceCode = resolveSourceCode(dataset, artifact);
        String sourceDomain = firstNonBlank(dataset.getSourceUrl(), dataset.getSource());

        // Resolve file paths
        Path artifactDir = Path.of(artifact.getArtifactPath()).normalize();
        Path productsPath = resolveFile(artifactDir, "rag_products.jsonl");
        if (productsPath == null) {
            productsPath = resolveFile(artifactDir, "products.jsonl");
        }
        if (productsPath == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "rag_products.jsonl or products.jsonl not found for artifact: " + artifactDir);
        }
        Path chunksPath = resolveFile(artifactDir, "chunks.jsonl");

        // Create or update GeneralSource: upsert by artifact_id for DATASET_ARTIFACT
        GeneralSource source = generalSourceRepository.findByArtifactId(artifact.getId())
                .orElseGet(GeneralSource::new);
        source.setSourceCode(sourceCode);
        source.setSourceName(firstNonBlank(dataset.getSource(), sourceCode));
        if (sourceDomain != null) {
            source.setSourceDomain(sourceDomain);
        }
        source.setSourceType("DATASET_ARTIFACT");
        source.setDatasetId(artifact.getDatasetId());
        source.setArtifactId(artifact.getId());
        source.setVisibility("GLOBAL_PUBLIC");
        source.setStatus("ACTIVE");
        generalSourceRepository.save(source);
        UUID generalSourceId = source.getId();

        // Create import run
        GeneralImportRun run = new GeneralImportRun();
        run.setSourceType("DATASET_ARTIFACT");
        run.setSourceRef(artifact.getId().toString());
        run.setGeneralSourceId(generalSourceId);
        run.setStatus("RUNNING");
        run.setMessage("Importing artifact " + artifact.getBuildTag());
        generalImportRunRepository.save(run);
        UUID runId = run.getId();

        int productsSeen = 0;
        int productsImported = 0;
        int productsUpdated = 0;
        int chunksSeen = 0;
        int chunksImported = 0;
        int chunksUpdated = 0;
        String errorMessage = null;

        // Load chunks.jsonl once into a map: product_id -> list of lines
        Map<String, List<JsonNode>> chunkLinesByProduct = new HashMap<>();
        if (chunksPath != null && Files.isRegularFile(chunksPath)) {
            try (var lines = Files.lines(chunksPath, StandardCharsets.UTF_8)) {
                Iterator<String> it = lines.iterator();
                while (it.hasNext()) {
                    String line = it.next().trim();
                    if (line.isBlank()) continue;
                    chunksSeen++;
                    try {
                        JsonNode chunkRaw = objectMapper.readTree(line);
                        if (!chunkRaw.isObject()) continue;
                        String chunkProductId = text(chunkRaw, "product_id", "sku", "code", "id");
                        if (chunkProductId == null || chunkProductId.isBlank()) continue;
                        chunkLinesByProduct
                                .computeIfAbsent(chunkProductId, k -> new ArrayList<>())
                                .add(chunkRaw);
                    } catch (Exception ignored) {
                    }
                }
            } catch (Exception ignored) {
            }
        }

        try {
            if (productsPath != null && Files.isRegularFile(productsPath)) {
                try (var lines = Files.lines(productsPath, StandardCharsets.UTF_8)) {
                    Iterator<String> iterator = lines.iterator();
                    while (iterator.hasNext()) {
                        String line = iterator.next().trim();
                        if (line.isBlank()) continue;
                        productsSeen++;
                        JsonNode raw;
                        try {
                            raw = objectMapper.readTree(line);
                        } catch (Exception ex) {
                            continue;
                        }
                        if (!raw.isObject()) continue;
                        String contentHash = sha256(line);
                        String externalProductId = text(raw, "product_id", "sku", "code", "id");
                        if (externalProductId != null) {
                            externalProductId = externalProductId.trim();
                        }

                        Optional<GeneralProduct> existing = externalProductId != null && !externalProductId.isEmpty()
                                ? generalProductRepository.findByGeneralSourceIdAndExternalProductId(generalSourceId, externalProductId)
                                : generalProductRepository.findByGeneralSourceIdAndContentHash(generalSourceId, contentHash);
                        GeneralProduct product = existing.orElseGet(GeneralProduct::new);
                        mapProduct(product, dataset, artifact, raw, generalSourceId, sourceCode, sourceDomain, externalProductId, contentHash);
                        generalProductRepository.save(product);

                        if (existing.isPresent()) {
                            productsUpdated++;
                        } else {
                            productsImported++;
                        }

                        // Upsert chunks using pre-loaded map or generate fallback
                        UUID productId = product.getId();
                        List<JsonNode> productChunks = externalProductId != null
                                ? chunkLinesByProduct.get(externalProductId)
                                : null;
                        if (productChunks != null && !productChunks.isEmpty()) {
                            for (JsonNode chunkRaw : productChunks) {
                                String chunkHash = sha256(chunkRaw.toString());
                                String chunkText = text(chunkRaw, "text", "content", "chunk_text");
                                if (chunkText == null) continue;
                                Optional<GeneralProductChunk> existingChunk = generalProductChunkRepository
                                        .findByGeneralProductIdAndContentHash(productId, chunkHash);
                                GeneralProductChunk chunk = existingChunk.orElseGet(GeneralProductChunk::new);
                                chunk.setGeneralProductId(productId);
                                chunk.setGeneralSourceId(generalSourceId);
                                chunk.setText(chunkText);
                                chunk.setChunkType(firstNonBlank(text(chunkRaw, "chunk_type", "type"), "PRODUCT"));
                                chunk.setContentHash(chunkHash);
                                if (chunkRaw.has("metadata") && chunkRaw.get("metadata").isObject()) {
                                    chunk.setMetadata(chunkRaw.get("metadata"));
                                }
                                generalProductChunkRepository.save(chunk);
                                if (existingChunk.isPresent()) {
                                    chunksUpdated++;
                                } else {
                                    chunksImported++;
                                }
                            }
                        } else {
                            // Generate fallback chunk
                            String genText = generateFallbackChunkText(raw);
                            if (genText != null) {
                                String genHash = sha256(genText);
                                Optional<GeneralProductChunk> existingChunk = generalProductChunkRepository
                                        .findByGeneralProductIdAndContentHash(productId, genHash);
                                GeneralProductChunk chunk = existingChunk.orElseGet(GeneralProductChunk::new);
                                chunk.setGeneralProductId(productId);
                                chunk.setGeneralSourceId(generalSourceId);
                                chunk.setText(genText);
                                chunk.setChunkType("PRODUCT_GENERATED");
                                chunk.setContentHash(genHash);
                                generalProductChunkRepository.save(chunk);
                                if (!existingChunk.isPresent()) {
                                    chunksImported++;
                                } else {
                                    chunksUpdated++;
                                }
                            }
                        }
                    }
                }
            }

            run.setStatus("SUCCESS");
            run.setMessage("Import complete for artifact " + artifact.getBuildTag());
        } catch (Exception ex) {
            errorMessage = ex.getMessage();
            run.setStatus("FAILED");
            run.setMessage("Import failed: " + (errorMessage != null ? errorMessage : ex.getClass().getSimpleName()));
        }

        run.setProductsSeen(productsSeen);
        run.setProductsImported(productsImported);
        run.setProductsUpdated(productsUpdated);
        run.setChunksSeen(chunksSeen);
        run.setChunksImported(chunksImported);
        run.setChunksUpdated(chunksUpdated);
        run.setFinishedAt(Instant.now());
        generalImportRunRepository.save(run);

        long totalForSource = generalProductRepository.countByGeneralSourceId(generalSourceId);
        long chunkCount = generalProductChunkRepository.countByGeneralSourceId(generalSourceId);

        return new GeneralProductImportResponse(
                runId,
                generalSourceId,
                artifact.getId(),
                artifact.getDatasetId(),
                artifact.getBuildTag(),
                productsSeen,
                productsImported,
                productsUpdated,
                chunksSeen,
                (int) chunkCount,
                chunksUpdated,
                run.getStatus(),
                run.getMessage()
        );
    }

    private String generateFallbackChunkText(JsonNode raw) {
        String name = text(raw, "name", "title", "product_name");
        String description = text(raw, "description", "notes", "content");
        String material = text(raw, "material");
        String dimensions = text(raw, "dimensions", "size");
        String price = raw.has("price") ? raw.get("price").asText() : null;

        StringBuilder sb = new StringBuilder();
        if (name != null) sb.append("Tên: ").append(name).append(".\n");
        if (description != null) sb.append("Mô tả: ").append(description).append(".\n");
        if (price != null) sb.append("Giá: ").append(price).append(".\n");
        if (material != null) sb.append("Chất liệu: ").append(material).append(".\n");
        if (dimensions != null) sb.append("Kích thước: ").append(dimensions).append(".\n");

        return sb.isEmpty() ? null : sb.toString().trim();
    }

    private String resolveSourceCode(ProductDataset dataset, ProductDatasetArtifact artifact) {
        String fromDataset = firstNonBlank(dataset.getSource(), dataset.getDatasetId());
        if (fromDataset != null) return fromDataset.replaceAll("[^a-zA-Z0-9_-]", "_").toLowerCase(Locale.ROOT);
        return artifact.getDatasetId().replaceAll("[^a-zA-Z0-9_-]", "_").toLowerCase(Locale.ROOT);
    }

    private Path resolveFile(Path artifactDir, String fileName) {
        Path file = artifactDir.resolve(fileName).normalize();
        if (Files.isRegularFile(file)) return file;
        return null;
    }

    private void mapProduct(
            GeneralProduct product,
            ProductDataset dataset,
            ProductDatasetArtifact artifact,
            JsonNode raw,
            UUID generalSourceId,
            String sourceCode,
            String sourceDomain,
            String externalProductId,
            String contentHash
    ) {
        product.setGeneralSourceId(generalSourceId);
        product.setDatasetRecordId(dataset.getId());
        product.setArtifactId(artifact.getId());
        product.setDatasetId(artifact.getDatasetId());
        product.setArtifactBuildTag(artifact.getBuildTag());
        product.setSource(sourceCode);
        product.setSourceCode(sourceCode);
        product.setSourceDomain(sourceDomain);
        String productUrl = text(raw, "source_url", "url", "link");
        product.setSourceUrl(firstNonBlank(productUrl, dataset.getSourceUrl()));
        product.setProductId(externalProductId);
        product.setExternalProductId(externalProductId);
        product.setSku(text(raw, "sku", "code"));
        String name = text(raw, "name", "title", "product_name");
        product.setName(name);
        if (name != null) {
            product.setNormalizedName(name.toLowerCase(Locale.ROOT).trim());
        }
        String category = text(raw, "category", "type", "product_type");
        product.setCategory(category);
        product.setProductType(category);
        product.setBrand(text(raw, "brand"));
        product.setMaterial(text(raw, "material"));
        String dims = text(raw, "dimensions", "size");
        product.setDimensions(dims);
        product.setDimensionsText(dims);
        BigDecimal price = decimal(raw, "price", "price_vnd", "amount");
        product.setPrice(price);
        product.setOriginalPrice(decimal(raw, "original_price", "original_price_vnd", "list_price"));
        product.setCurrency(firstNonBlank(text(raw, "currency"), price == null ? null : "VND"));
        product.setProductUrl(text(raw, "product_url", "url", "link", "source"));
        product.setImageUrl(text(raw, "image_url", "image", "thumbnail"));
        product.setDescription(text(raw, "description", "notes", "content"));
        product.setVisibility("GLOBAL_PUBLIC");
        product.setStatus("ACTIVE");
        product.setContentHash(contentHash);
        product.setRaw(raw);
    }

    private String text(JsonNode node, String... names) {
        if (node == null) return null;
        for (String name : names) {
            JsonNode value = node.get(name);
            if (value != null && !value.isNull()) {
                String text = value.asText(null);
                if (text != null && !text.isBlank()) {
                    return text.trim();
                }
            }
        }
        return null;
    }

    private BigDecimal decimal(JsonNode node, String... names) {
        String text = text(node, names);
        if (text == null) return null;
        String normalized = text.replaceAll("[^0-9.,]", "").replace(",", "");
        if (normalized.isBlank()) return null;
        try {
            return new BigDecimal(normalized);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private String firstNonBlank(String first, String second) {
        if (first != null && !first.isBlank()) return first;
        return second != null && !second.isBlank() ? second : null;
    }

    private String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 not available", ex);
        }
    }
}
