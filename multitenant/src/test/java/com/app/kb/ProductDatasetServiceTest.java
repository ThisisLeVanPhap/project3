package com.app.kb;

import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.LlmProperties;
import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.web.server.ResponseStatusException;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ProductDatasetServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void registerDatasetReadsManifest() throws Exception {
        Path datasetDir = datasetDir("demo-dataset", true);
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        when(datasetRepository.findByDatasetId("demo-dataset")).thenReturn(Optional.empty());
        when(datasetRepository.save(any(ProductDataset.class))).thenAnswer(invocation -> invocation.getArgument(0));
        ProductDatasetService service = service(datasetRepository, mock(TenantRepository.class), mock(TenantKbVersionRepository.class), modelServerDir());

        ProductDatasetResponse response = service.register(new ProductDatasetRegisterRequest("demo-dataset", datasetDir.toString(), null, null, null));

        assertEquals("demo-dataset", response.datasetId());
        assertEquals("gotrangtri", response.source());
        assertEquals(2, response.productCount());
        assertEquals(2, response.ragChunkCount());
        assertEquals(ProductDatasetStatus.REGISTERED, response.status());
        assertNotNull(response.contentHash());
    }

    @Test
    void registerDatasetMissingManifestFails() {
        ProductDatasetService service = service(mock(ProductDatasetRepository.class), mock(TenantRepository.class), mock(TenantKbVersionRepository.class), modelServerDir());

        assertThrows(ResponseStatusException.class, () ->
                service.register(new ProductDatasetRegisterRequest("missing", tempDir.toString(), null, null, null)));
    }

    @Test
    void registerDatasetRejectsQualityFailure() throws Exception {
        Path datasetDir = datasetDir("bad-dataset", true);
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        when(datasetRepository.findByDatasetId("bad-dataset")).thenReturn(Optional.empty());
        ProductDatasetService service = service(datasetRepository, mock(TenantRepository.class), mock(TenantKbVersionRepository.class), fakeChatbotDir(true));

        assertThrows(ResponseStatusException.class, () ->
                service.register(new ProductDatasetRegisterRequest("bad-dataset", datasetDir.toString(), null, null, null)));
        verify(datasetRepository, never()).save(any(ProductDataset.class));
    }

    @Test
    void listDatasetsNewestFirst() {
        ProductDataset newer = dataset("newer");
        ProductDataset older = dataset("older");
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        when(datasetRepository.findAllByOrderByRegisteredAtDesc()).thenReturn(List.of(newer, older));
        ProductDatasetService service = service(datasetRepository, mock(TenantRepository.class), mock(TenantKbVersionRepository.class), modelServerDir());

        List<ProductDatasetResponse> responses = service.list();

        assertEquals(List.of("newer", "older"), responses.stream().map(ProductDatasetResponse::datasetId).toList());
    }

    @Test
    void deleteDatasetDoesNotDeleteFiles() throws Exception {
        Path datasetDir = datasetDir("delete-me", true);
        ProductDataset dataset = dataset("delete-me");
        dataset.setPath(datasetDir.toString());
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        when(datasetRepository.findById(dataset.getId())).thenReturn(Optional.of(dataset));
        ProductDatasetService service = service(datasetRepository, mock(TenantRepository.class), mock(TenantKbVersionRepository.class), modelServerDir());

        service.delete(dataset.getId());

        verify(datasetRepository).delete(dataset);
        assertTrue(Files.exists(datasetDir.resolve("rag_products.jsonl")));
    }

    @Test
    void assignDatasetCreatesReadyVersionAndPublishesIt() throws Exception {
        Path datasetDir = datasetDir("assign-me", true);
        Path chatbotDir = fakeChatbotDir();
        ProductDataset dataset = dataset("assign-me");
        dataset.setPath(datasetDir.toString());
        dataset.setManifestPath(datasetDir.resolve("manifest.json").toString());
        UUID tenantId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "datn_demo_moho");

        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        TenantRepository tenantRepository = mock(TenantRepository.class);
        TenantKbVersionRepository versionRepository = mock(TenantKbVersionRepository.class);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        when(datasetRepository.findById(dataset.getId())).thenReturn(Optional.of(dataset));
        when(tenantRepository.findByCodeIgnoreCase("datn_demo_moho")).thenReturn(Optional.of(tenant));
        when(versionRepository.findByTenantIdAndVersionTag(any(), any())).thenReturn(Optional.empty());
        when(versionRepository.save(any(TenantKbVersion.class))).thenAnswer(invocation -> {
            TenantKbVersion version = invocation.getArgument(0);
            if (version.getId() == null) {
                version.setId(UUID.randomUUID());
            }
            return version;
        });
        when(datasetRepository.save(any(ProductDataset.class))).thenAnswer(invocation -> invocation.getArgument(0));

        ProductDatasetService service = service(datasetRepository, tenantRepository, versionRepository, chatbotDir, llmInstanceManager);

        ProductDatasetAssignResponse response = service.assignToTenant(dataset.getId(), new ProductDatasetAssignRequest("datn_demo_moho", null));

        assertTrue(response.success());
        assertEquals(2, response.chunkCount());
        assertEquals(response.kbVersionId(), tenant.getActiveKbVersionId());
        assertTrue(response.kbDir().contains("datn_demo_moho"));
        assertEquals(ProductDatasetStatus.ASSIGNED, dataset.getStatus());
        verify(tenantRepository).save(tenant);
        verify(llmInstanceManager).evictTenant(tenantId);
    }

    @Test
    void assignDatasetRejectsQualityFailureBeforePublishing() throws Exception {
        ProductDataset dataset = dataset("assign-bad");
        Path datasetDir = datasetDir("assign-bad", true);
        dataset.setPath(datasetDir.toString());
        dataset.setManifestPath(datasetDir.resolve("manifest.json").toString());
        UUID tenantId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "datn_demo_moho");
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        TenantRepository tenantRepository = mock(TenantRepository.class);
        TenantKbVersionRepository versionRepository = mock(TenantKbVersionRepository.class);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        when(datasetRepository.findById(dataset.getId())).thenReturn(Optional.of(dataset));
        when(tenantRepository.findByCodeIgnoreCase("datn_demo_moho")).thenReturn(Optional.of(tenant));
        ProductDatasetService service = service(datasetRepository, tenantRepository, versionRepository, fakeChatbotDir(true), llmInstanceManager);

        assertThrows(ResponseStatusException.class, () ->
                service.assignToTenant(dataset.getId(), new ProductDatasetAssignRequest("datn_demo_moho", null)));
        assertEquals(ProductDatasetStatus.REGISTERED, dataset.getStatus());
        assertEquals(null, tenant.getActiveKbVersionId());
        verify(tenantRepository, never()).save(tenant);
        verify(llmInstanceManager, never()).evictTenant(tenantId);
    }

    @Test
    void assignDatasetRejectsMissingTenant() throws Exception {
        ProductDataset dataset = dataset("assign-me");
        Path datasetDir = datasetDir("assign-me", true);
        dataset.setPath(datasetDir.toString());
        dataset.setManifestPath(datasetDir.resolve("manifest.json").toString());
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        TenantRepository tenantRepository = mock(TenantRepository.class);
        when(datasetRepository.findById(dataset.getId())).thenReturn(Optional.of(dataset));
        when(tenantRepository.findByCodeIgnoreCase("missing")).thenReturn(Optional.empty());
        ProductDatasetService service = service(datasetRepository, tenantRepository, mock(TenantKbVersionRepository.class), modelServerDir());

        assertThrows(ResponseStatusException.class, () ->
                service.assignToTenant(dataset.getId(), new ProductDatasetAssignRequest("missing", null)));
    }

    @Test
    void buildArtifactDoesNotChangeTenantRuntimeState() throws Exception {
        Path datasetDir = datasetDir("artifact-dataset", true);
        ProductDataset dataset = dataset("artifact-dataset");
        dataset.setPath(datasetDir.toString());
        dataset.setManifestPath(datasetDir.resolve("manifest.json").toString());
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        ProductDatasetArtifactRepository artifactRepository = mock(ProductDatasetArtifactRepository.class);
        TenantRepository tenantRepository = mock(TenantRepository.class);
        TenantKbVersionRepository versionRepository = mock(TenantKbVersionRepository.class);
        TenantKbBindingRepository bindingRepository = mock(TenantKbBindingRepository.class);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        when(datasetRepository.findById(dataset.getId())).thenReturn(Optional.of(dataset));
        when(artifactRepository.findByDatasetIdAndBuildTag(any(), any())).thenReturn(Optional.empty());
        when(artifactRepository.save(any(ProductDatasetArtifact.class))).thenAnswer(invocation -> {
            ProductDatasetArtifact artifact = invocation.getArgument(0);
            if (artifact.getId() == null) {
                artifact.setId(UUID.randomUUID());
            }
            return artifact;
        });
        when(bindingRepository.findAllByDatasetIdAndActiveTrueAndUpdatePolicy("artifact-dataset", TenantKbBindingUpdatePolicy.AUTO_USE_LATEST)).thenReturn(List.of());
        ProductDatasetService service = service(datasetRepository, artifactRepository, tenantRepository, versionRepository, bindingRepository, fakeChatbotDir(), llmInstanceManager);

        ProductDatasetArtifactResponse response = service.buildArtifact(dataset.getId());

        assertEquals(ProductDatasetArtifactStatus.READY, response.status());
        assertEquals(2, response.artifactCount());
        verify(versionRepository, never()).save(any(TenantKbVersion.class));
        verify(tenantRepository, never()).save(any(Tenant.class));
        verify(llmInstanceManager, never()).evictTenant(any());
    }

    @Test
    void bindArtifactCreatesBindingVersionAndEvictsRuntime() throws Exception {
        UUID tenantId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "datn_demo_moho");
        ProductDatasetArtifact artifact = artifact("demo-dataset");
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        ProductDatasetArtifactRepository artifactRepository = mock(ProductDatasetArtifactRepository.class);
        TenantRepository tenantRepository = mock(TenantRepository.class);
        TenantKbVersionRepository versionRepository = mock(TenantKbVersionRepository.class);
        TenantKbBindingRepository bindingRepository = mock(TenantKbBindingRepository.class);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        when(artifactRepository.findById(artifact.getId())).thenReturn(Optional.of(artifact));
        when(tenantRepository.findByCodeIgnoreCase("datn_demo_moho")).thenReturn(Optional.of(tenant));
        when(bindingRepository.findFirstByTenantIdAndActiveTrue(tenantId)).thenReturn(Optional.empty());
        when(versionRepository.findByTenantIdAndVersionTag(any(), any())).thenReturn(Optional.empty());
        when(versionRepository.save(any(TenantKbVersion.class))).thenAnswer(invocation -> {
            TenantKbVersion version = invocation.getArgument(0);
            if (version.getId() == null) {
                version.setId(UUID.randomUUID());
            }
            return version;
        });
        when(bindingRepository.save(any(TenantKbBinding.class))).thenAnswer(invocation -> {
            TenantKbBinding binding = invocation.getArgument(0);
            if (binding.getId() == null) {
                binding.setId(UUID.randomUUID());
            }
            return binding;
        });
        ProductDatasetService service = service(datasetRepository, artifactRepository, tenantRepository, versionRepository, bindingRepository, modelServerDir(), llmInstanceManager);

        TenantKbBindingResponse response = service.bindArtifactToTenant(new TenantKbBindRequest(null, "datn_demo_moho", artifact.getId(), TenantKbBindingUpdatePolicy.AUTO_USE_LATEST));

        assertTrue(response.active());
        assertEquals(artifact.getId(), response.artifactId());
        assertNotNull(response.activeKbVersionId());
        assertEquals(response.activeKbVersionId(), tenant.getActiveKbVersionId());
        assertEquals(null, tenant.getKbDir());
        verify(tenantRepository).save(tenant);
        verify(llmInstanceManager).evictTenant(tenantId);
    }

    @Test
    void unbindClearsActiveVersionAndKeepsFallbackKbDir() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID activeVersionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "datn_demo_moho");
        tenant.setKbDir("/legacy/kb");
        tenant.setActiveKbVersionId(activeVersionId);
        TenantKbBinding binding = new TenantKbBinding();
        binding.setId(UUID.randomUUID());
        binding.setTenantId(tenantId);
        binding.setDatasetId("demo-dataset");
        binding.setActive(true);
        binding.setUpdatePolicy(TenantKbBindingUpdatePolicy.AUTO_USE_LATEST);
        binding.setActiveKbVersionId(activeVersionId);
        ProductDatasetRepository datasetRepository = mock(ProductDatasetRepository.class);
        TenantRepository tenantRepository = mock(TenantRepository.class);
        TenantKbBindingRepository bindingRepository = mock(TenantKbBindingRepository.class);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        when(tenantRepository.findByCodeIgnoreCase("datn_demo_moho")).thenReturn(Optional.of(tenant));
        when(bindingRepository.findFirstByTenantIdAndActiveTrue(tenantId)).thenReturn(Optional.of(binding));
        when(bindingRepository.save(any(TenantKbBinding.class))).thenAnswer(invocation -> invocation.getArgument(0));
        ProductDatasetService service = service(datasetRepository, mock(ProductDatasetArtifactRepository.class), tenantRepository, mock(TenantKbVersionRepository.class), bindingRepository, modelServerDir(), llmInstanceManager);

        TenantKbBindingResponse response = service.unbindTenantKb(new TenantKbUnbindRequest(null, "datn_demo_moho"));

        assertFalse(response.active());
        assertEquals(null, tenant.getActiveKbVersionId());
        assertEquals("/legacy/kb", tenant.getKbDir());
        verify(tenantRepository).save(tenant);
        verify(llmInstanceManager).evictTenant(tenantId);
    }

    private ProductDatasetService service(
            ProductDatasetRepository datasetRepository,
            TenantRepository tenantRepository,
            TenantKbVersionRepository versionRepository,
            Path chatbotDir
    ) {
        return service(datasetRepository, tenantRepository, versionRepository, chatbotDir, mock(LlmInstanceManager.class));
    }

    private ProductDatasetService service(
            ProductDatasetRepository datasetRepository,
            TenantRepository tenantRepository,
            TenantKbVersionRepository versionRepository,
            Path chatbotDir,
            LlmInstanceManager llmInstanceManager
    ) {
        return service(
                datasetRepository,
                mock(ProductDatasetArtifactRepository.class),
                tenantRepository,
                versionRepository,
                mock(TenantKbBindingRepository.class),
                chatbotDir,
                llmInstanceManager
        );
    }

    private ProductDatasetService service(
            ProductDatasetRepository datasetRepository,
            ProductDatasetArtifactRepository artifactRepository,
            TenantRepository tenantRepository,
            TenantKbVersionRepository versionRepository,
            TenantKbBindingRepository bindingRepository,
            Path chatbotDir,
            LlmInstanceManager llmInstanceManager
    ) {
        LlmProperties properties = new LlmProperties();
        properties.setPythonBin("python");
        properties.setModelServerDir(chatbotDir.toString());
        return new ProductDatasetService(
                datasetRepository,
                artifactRepository,
                tenantRepository,
                versionRepository,
                bindingRepository,
                properties,
                llmInstanceManager,
                new ObjectMapper()
        );
    }

    private Path modelServerDir() {
        try {
            return fakeChatbotDir(false);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private Path datasetDir(String datasetId, boolean withRagProducts) throws Exception {
        Path dir = tempDir.resolve(datasetId);
        Files.createDirectories(dir);
        Files.writeString(dir.resolve("catalog.jsonl"), "{\"product_name\":\"A\",\"price\":1,\"material\":\"Gỗ\",\"dimensions\":\"1x1\",\"source_url\":\"https://example.test/a\"}\n{\"product_name\":\"C\",\"price\":2,\"material\":\"Gỗ\",\"dimensions\":\"2x2\",\"source_url\":\"https://example.test/c\"}\n");
        if (withRagProducts) {
            Files.writeString(dir.resolve("rag_products.jsonl"), "{\"title\":\"A\",\"content\":\"B\",\"text\":\"B\",\"url\":\"https://example.test/a\"}\n{\"title\":\"C\",\"content\":\"D\",\"text\":\"D\",\"url\":\"https://example.test/c\"}\n");
        }
        Files.writeString(dir.resolve("manifest.json"), """
                {
                  "dataset_id": "%s",
                  "source": "gotrangtri",
                  "source_url": "https://gotrangtri.vn",
                  "created_at": "2026-06-10T00:00:00Z",
                  "product_count": 2,
                  "rag_chunk_count": 2,
                  "files": {
                    "catalog": "catalog.jsonl",
                    "rag_products": "rag_products.jsonl"
                  },
                  "schema_version": "1.0"
                }
                """.formatted(datasetId));
        return dir;
    }

    private Path fakeChatbotDir() throws Exception {
        return fakeChatbotDir(false);
    }

    private Path fakeChatbotDir(boolean qualityFail) throws Exception {
        Path root = tempDir.resolve("fake-root-" + UUID.randomUUID());
        Path chatbotDir = root.resolve("chatbot");
        Path toolsDir = chatbotDir.resolve("tools");
        Path scriptsDir = root.resolve("data_pipeline").resolve("scripts");
        Files.createDirectories(toolsDir);
        Files.createDirectories(scriptsDir);
        Files.writeString(scriptsDir.resolve("audit_product_dataset.py"), """
                import argparse, json
                p = argparse.ArgumentParser()
                p.add_argument('--dataset-dir')
                p.add_argument('--output')
                args = p.parse_args()
                status = 'fail' if __QUALITY_FAIL__ else 'pass'
                report = {'status': status, 'fail_reasons': ['bad title'] if status == 'fail' else [], 'reasons': ['bad title'] if status == 'fail' else []}
                if args.output:
                    open(args.output, 'w', encoding='utf-8').write(json.dumps(report))
                print(json.dumps(report))
                """.replace("__QUALITY_FAIL__", qualityFail ? "True" : "False"));
        Files.writeString(toolsDir.resolve("import_dataset.py"), """
                import argparse, json
                from pathlib import Path
                p = argparse.ArgumentParser()
                p.add_argument('--dataset-dir')
                p.add_argument('--tenant-code')
                p.add_argument('--kb-base')
                p.add_argument('--version-tag')
                args = p.parse_args()
                kb_dir = Path(args.kb_base) / args.tenant_code / 'versions' / args.version_tag
                kb_dir.mkdir(parents=True, exist_ok=True)
                (kb_dir / 'chunks.jsonl').write_text('{}\\n{}\\n', encoding='utf-8')
                (kb_dir / 'index.json').write_text('{\"N\":2}', encoding='utf-8')
                print(json.dumps({'success': True, 'tenant_code': args.tenant_code, 'dataset_id': Path(args.dataset_dir).name, 'kb_dir': str(kb_dir), 'chunk_count': 2}))
                """);
        Files.writeString(toolsDir.resolve("build_dataset_kb_artifact.py"), """
                import argparse, json
                from pathlib import Path
                p = argparse.ArgumentParser()
                p.add_argument('--dataset-dir')
                p.add_argument('--artifact-dir')
                args = p.parse_args()
                artifact_dir = Path(args.artifact_dir)
                artifact_dir.mkdir(parents=True, exist_ok=True)
                (artifact_dir / 'products.jsonl').write_text('{}\\n{}\\n', encoding='utf-8')
                (artifact_dir / 'chunks.jsonl').write_text('{}\\n{}\\n', encoding='utf-8')
                (artifact_dir / 'index.json').write_text('{\"N\":2}', encoding='utf-8')
                print(json.dumps({'success': True, 'dataset_id': Path(args.dataset_dir).name, 'artifact_path': str(artifact_dir), 'artifact_count': 2, 'quality_status': 'pass'}))
                """);
        return chatbotDir;
    }

    private ProductDataset dataset(String datasetId) {
        ProductDataset dataset = new ProductDataset();
        dataset.setId(UUID.randomUUID());
        dataset.setDatasetId(datasetId);
        dataset.setPath(tempDir.resolve(datasetId).toString());
        dataset.setStatus(ProductDatasetStatus.REGISTERED);
        dataset.setRegisteredAt(Instant.now());
        return dataset;
    }

    private Tenant tenant(UUID tenantId, String code) {
        Tenant tenant = new Tenant();
        tenant.setId(tenantId);
        tenant.setCode(code);
        tenant.setName(code);
        tenant.setApiKey("api-key");
        tenant.setStatus("ACTIVE");
        return tenant;
    }

    private ProductDatasetArtifact artifact(String datasetId) {
        ProductDatasetArtifact artifact = new ProductDatasetArtifact();
        artifact.setId(UUID.randomUUID());
        artifact.setDatasetRecordId(UUID.randomUUID());
        artifact.setDatasetId(datasetId);
        artifact.setBuildTag("build-1");
        artifact.setArtifactPath(tempDir.resolve("kb/datasets/%s/build-1".formatted(datasetId)).toString());
        artifact.setArtifactCount(2);
        artifact.setQualityStatus("pass");
        artifact.setStatus(ProductDatasetArtifactStatus.READY);
        artifact.setBuiltAt(Instant.now());
        return artifact;
    }
}
