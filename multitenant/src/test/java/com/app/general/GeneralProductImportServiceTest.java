package com.app.general;

import com.app.kb.ProductDataset;
import com.app.kb.ProductDatasetArtifact;
import com.app.kb.ProductDatasetArtifactRepository;
import com.app.kb.ProductDatasetArtifactStatus;
import com.app.kb.ProductDatasetRepository;
import com.app.kb.ProductDatasetStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.web.server.ResponseStatusException;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GeneralProductImportServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void importCreatesSourceProductsChunksAndImportRun() throws Exception {
        Path artifactDir = tempDir.resolve("artifact");
        Files.createDirectories(artifactDir);
        Files.writeString(artifactDir.resolve("rag_products.jsonl"), """
                {"product_id":"SFG041","title":"Sofa gỗ sồi","type":"sofa","price_vnd":12000000,"material":"gỗ sồi","url":"https://example.test/sofa"}
                {"sku":"BAN-01","name":"Bàn ăn","category":"bàn ăn","amount":"8500000 VND","dimensions":"1m4 x 0m8"}
                """);

        InMemoryStores stores = new InMemoryStores();
        ProductDataset dataset = dataset("gotrangtri");
        ProductDatasetArtifact artifact = artifact(dataset, artifactDir, ProductDatasetArtifactStatus.READY);

        mockArtifact(stores, artifact);
        mockDataset(stores, dataset);
        GeneralProductImportService service = buildService(stores);

        GeneralProductImportResponse resp = service.importArtifact(artifact.getId());

        assertEquals(2, resp.productsSeen());
        assertEquals(2, resp.productsImported());
        assertEquals(0, resp.productsUpdated());
        assertEquals("SUCCESS", resp.status());
        assertNotNull(resp.generalSourceId());
        assertNotNull(resp.importRunId());

        // Verify source created
        GeneralSource source = stores.sourceById.get(resp.generalSourceId());
        assertNotNull(source);
        assertEquals("gotrangtri", source.getSourceCode());
        assertEquals("DATASET_ARTIFACT", source.getSourceType());
        assertEquals("GLOBAL_PUBLIC", source.getVisibility());

        // Verify products linked to source
        GeneralProduct sofa = stores.productByExternalId.get("SFG041");
        assertNotNull(sofa);
        assertEquals(resp.generalSourceId(), sofa.getGeneralSourceId());
        assertEquals("GLOBAL_PUBLIC", sofa.getVisibility());
        assertEquals("sofa", sofa.getCategory());
        assertEquals("sofa", sofa.getProductType());
        assertEquals("12000000", sofa.getPrice().toPlainString());
        assertEquals("Sofa gỗ sồi", sofa.getName());
        assertEquals("sofa gỗ sồi", sofa.getNormalizedName());

        // Verify chunks generated
        assertTrue(stores.chunkCountBySource.getOrDefault(resp.generalSourceId(), 0L) >= 1);

        // Verify import run
        GeneralImportRun run = stores.runById.get(resp.importRunId());
        assertNotNull(run);
        assertEquals("SUCCESS", run.getStatus());
        assertEquals(2, run.getProductsSeen());
        assertEquals(2, run.getProductsImported());
        assertEquals(resp.generalSourceId(), run.getGeneralSourceId());
        assertNotNull(run.getFinishedAt());
    }

    @Test
    void importAgainDoesNotDuplicateSourceProductsOrChunks() throws Exception {
        Path artifactDir = tempDir.resolve("artifact2");
        Files.createDirectories(artifactDir);
        Files.writeString(artifactDir.resolve("rag_products.jsonl"), """
                {"product_id":"SFG041","title":"Sofa gỗ sồi","type":"sofa","price_vnd":12000000,"material":"gỗ sồi","url":"https://example.test/sofa"}
                """);

        InMemoryStores stores = new InMemoryStores();
        ProductDataset dataset = dataset("gotrangtri");
        ProductDatasetArtifact artifact = artifact(dataset, artifactDir, ProductDatasetArtifactStatus.READY);

        mockArtifact(stores, artifact);
        mockDataset(stores, dataset);
        GeneralProductImportService service = buildService(stores);

        GeneralProductImportResponse first = service.importArtifact(artifact.getId());
        GeneralProductImportResponse second = service.importArtifact(artifact.getId());

        assertEquals(1, first.productsImported());
        assertEquals(0, second.productsImported());
        assertEquals(1, second.productsUpdated());

        // Source count should be 1 (not duplicated)
        assertEquals(1L, stores.sourceByCode.size());

        // Two import runs created
        assertNotNull(first.importRunId());
        assertNotNull(second.importRunId());

        // Verify tenant artifact unchanged
        assertEquals(ProductDatasetArtifactStatus.READY, artifact.getStatus());
    }

    @Test
    void importRejectsArtifactThatIsNotReady() {
        ProductDataset dataset = dataset("gotrangtri");
        ProductDatasetArtifact artifact = artifact(dataset, tempDir.resolve("artifact"), ProductDatasetArtifactStatus.BUILDING);
        ProductDatasetArtifactRepository artifactRepository = mock(ProductDatasetArtifactRepository.class);
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        GeneralProductImportService service = new GeneralProductImportService(
                artifactRepository,
                datasetRepository,
                mock(GeneralSourceRepository.class),
                mock(GeneralProductRepository.class),
                mock(GeneralProductChunkRepository.class),
                mock(GeneralImportRunRepository.class),
                new ObjectMapper()
        );
        when(artifactRepository.findById(artifact.getId())).thenReturn(Optional.of(artifact));

        assertThrows(ResponseStatusException.class, () -> service.importArtifact(artifact.getId()));
        verify(datasetRepository, never()).findById(any());
    }

    @Test
    void importRejectsArtifactWithMissingProductsFile() throws Exception {
        Path artifactDir = tempDir.resolve("artifact-missing");
        Files.createDirectories(artifactDir);
        // No rag_products.jsonl -> BAD_REQUEST

        InMemoryStores stores = new InMemoryStores();
        ProductDataset dataset = dataset("gotrangtri");
        ProductDatasetArtifact artifact = artifact(dataset, artifactDir, ProductDatasetArtifactStatus.READY);

        mockArtifact(stores, artifact);
        mockDataset(stores, dataset);
        GeneralProductImportService service = buildService(stores);

        assertThrows(ResponseStatusException.class, () -> service.importArtifact(artifact.getId()));
    }

    private void assertTrue(boolean condition) {
        org.junit.jupiter.api.Assertions.assertTrue(condition);
    }

    private void mockArtifact(InMemoryStores stores, ProductDatasetArtifact artifact) {
        when(stores.artifactRepository.findById(artifact.getId())).thenReturn(Optional.of(artifact));
    }

    private void mockDataset(InMemoryStores stores, ProductDataset dataset) {
        when(stores.datasetRepository.findById(dataset.getId())).thenReturn(Optional.of(dataset));
    }

    private GeneralProductImportService buildService(InMemoryStores stores) {
        return new GeneralProductImportService(
                stores.artifactRepository,
                stores.datasetRepository,
                stores.sourceRepository,
                stores.productRepository,
                stores.chunkRepository,
                stores.runRepository,
                new ObjectMapper()
        );
    }

    private ProductDataset dataset(String datasetId) {
        ProductDataset dataset = new ProductDataset();
        dataset.setId(UUID.randomUUID());
        dataset.setDatasetId(datasetId);
        dataset.setSource("gotrangtri");
        dataset.setSourceUrl("https://gotrangtri.example");
        dataset.setPath(tempDir.resolve(datasetId).toString());
        dataset.setStatus(ProductDatasetStatus.REGISTERED);
        dataset.setRegisteredAt(Instant.now());
        return dataset;
    }

    private ProductDatasetArtifact artifact(ProductDataset dataset, Path artifactDir, ProductDatasetArtifactStatus status) {
        ProductDatasetArtifact artifact = new ProductDatasetArtifact();
        artifact.setId(UUID.randomUUID());
        artifact.setDatasetRecordId(dataset.getId());
        artifact.setDatasetId(dataset.getDatasetId());
        artifact.setBuildTag("build-1");
        artifact.setArtifactPath(artifactDir.toString());
        artifact.setArtifactCount(2);
        artifact.setQualityStatus("pass");
        artifact.setStatus(status);
        artifact.setBuiltAt(Instant.now());
        return artifact;
    }

    static class InMemoryStores {
        final ProductDatasetArtifactRepository artifactRepository = mock(ProductDatasetArtifactRepository.class);
        final ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        final GeneralSourceRepository sourceRepository = mock(GeneralSourceRepository.class);
        final GeneralProductRepository productRepository = mock(GeneralProductRepository.class);
        final GeneralProductChunkRepository chunkRepository = mock(GeneralProductChunkRepository.class);
        final GeneralImportRunRepository runRepository = mock(GeneralImportRunRepository.class);

        final Map<String, GeneralSource> sourceByCode = new HashMap<>();
        final Map<UUID, GeneralSource> sourceById = new HashMap<>();
        final Map<String, GeneralProduct> productByExternalId = new HashMap<>();
        final Map<String, GeneralProduct> productByHash = new HashMap<>();
        final Map<UUID, GeneralProduct> productById = new HashMap<>();
        final Map<String, GeneralProductChunk> chunkByProductHash = new HashMap<>();
        final Map<UUID, GeneralProductChunk> chunkById = new HashMap<>();
        final Map<UUID, GeneralImportRun> runById = new HashMap<>();
        final Map<UUID, Long> chunkCountBySource = new HashMap<>();

        InMemoryStores() {
            wireSourceRepository();
            wireProductRepository();
            wireChunkRepository();
            wireRunRepository();
        }

        private void wireSourceRepository() {
            when(sourceRepository.findByArtifactId(any())).thenAnswer(inv -> {
                UUID artifactId = inv.getArgument(0, UUID.class);
                return sourceById.values().stream()
                        .filter(s -> artifactId.equals(s.getArtifactId()))
                        .findFirst();
            });
            when(sourceRepository.save(any(GeneralSource.class))).thenAnswer(inv -> {
                GeneralSource s = inv.getArgument(0);
                if (s.getId() == null) s.setId(UUID.randomUUID());
                sourceByCode.put(s.getSourceCode(), s);
                sourceById.put(s.getId(), s);
                return s;
            });
        }

        private void wireProductRepository() {
            when(productRepository.findByGeneralSourceIdAndExternalProductId(any(), any())).thenAnswer(inv ->
                    Optional.ofNullable(productByExternalId.get(inv.getArgument(1, String.class))));
            when(productRepository.findByGeneralSourceIdAndContentHash(any(), any())).thenAnswer(inv ->
                    Optional.ofNullable(productByHash.get(inv.getArgument(1, String.class))));
            when(productRepository.save(any(GeneralProduct.class))).thenAnswer(inv -> {
                GeneralProduct p = inv.getArgument(0);
                if (p.getId() == null) p.setId(UUID.randomUUID());
                productById.put(p.getId(), p);
                if (p.getExternalProductId() != null) productByExternalId.put(p.getExternalProductId(), p);
                if (p.getContentHash() != null) productByHash.put(p.getContentHash(), p);
                return p;
            });
            when(productRepository.countByGeneralSourceId(any())).thenAnswer(inv ->
                    productById.values().stream().filter(p -> inv.getArgument(0).equals(p.getGeneralSourceId())).count());
        }

        private void wireChunkRepository() {
            when(chunkRepository.findByGeneralProductIdAndContentHash(any(), any())).thenAnswer(inv -> {
                String key = inv.getArgument(0) + ":" + inv.getArgument(1);
                return Optional.ofNullable(chunkByProductHash.get(key));
            });
            when(chunkRepository.save(any(GeneralProductChunk.class))).thenAnswer(inv -> {
                GeneralProductChunk c = inv.getArgument(0);
                if (c.getId() == null) c.setId(UUID.randomUUID());
                chunkById.put(c.getId(), c);
                chunkByProductHash.put(c.getGeneralProductId() + ":" + c.getContentHash(), c);
                chunkCountBySource.merge(c.getGeneralSourceId(), 1L, Long::sum);
                return c;
            });
            when(chunkRepository.countByGeneralSourceId(any())).thenAnswer(inv ->
                    chunkCountBySource.getOrDefault(inv.getArgument(0, UUID.class), 0L));
        }

        private void wireRunRepository() {
            when(runRepository.save(any(GeneralImportRun.class))).thenAnswer(inv -> {
                GeneralImportRun r = inv.getArgument(0);
                if (r.getId() == null) r.setId(UUID.randomUUID());
                runById.put(r.getId(), r);
                return r;
            });
        }
    }
}
