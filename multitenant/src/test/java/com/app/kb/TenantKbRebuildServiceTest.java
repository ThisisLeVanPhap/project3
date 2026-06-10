package com.app.kb;

import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.LlmProperties;
import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TenantKbRebuildServiceTest {

    @TempDir
    private Path tempDir;

    @Test
    void rebuildSuccessCreatesBuildingVersionThenMarksReady() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        Path modelDir = createModelServerScripts(false);
        Path kbDir = tempDir.resolve("kb").resolve("demo");
        Files.createDirectories(kbDir);
        Files.writeString(kbDir.resolve("raw_urls.txt"), """
                https://example.com/help
                https://example.com/products
                """);
        Tenant tenant = tenant(tenantId, kbDir);
        List<TenantKbVersion> savedVersions = new ArrayList<>();
        TenantKbVersionRepository versionRepository = versionRepository(savedVersions);
        TenantRepository tenantRepository = tenantRepository(tenant);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);

        TenantKbRebuildService service = newService(tenantRepository, versionRepository, llmInstanceManager, modelDir);

        TenantKbRebuildService.RebuildResponse response = service.rebuild(tenantId);

        assertTrue(response.success());
        assertEquals(2, savedVersions.size());
        TenantKbVersion building = savedVersions.get(0);
        TenantKbVersion ready = savedVersions.get(1);
        Path rootKbDir = kbDir.toAbsolutePath().normalize();
        Path versionDir = Path.of(ready.getKbDir());
        assertEquals(TenantKbVersionStatus.BUILDING, building.getStatus());
        assertEquals(TenantKbVersionStatus.READY, ready.getStatus());
        assertEquals(tenantId, ready.getTenantId());
        assertFalse(rootKbDir.toString().equals(ready.getKbDir()));
        assertEquals(rootKbDir.resolve("versions").resolve(ready.getVersionTag()), versionDir);
        assertTrue(Files.isDirectory(versionDir));
        assertTrue(Files.exists(versionDir.resolve("raw_urls.txt")));
        assertEquals(Files.readString(kbDir.resolve("raw_urls.txt")), Files.readString(versionDir.resolve("raw_urls.txt")));
        assertTrue(ready.getVersionTag().matches("v\\d{14}(-\\d+)?"));
        assertEquals("[\"https://example.com/help\",\"https://example.com/products\"]", ready.getSourceUrlSnapshot());
        assertEquals(3, ready.getArtifactCount());
        assertNotNull(ready.getBuiltAt());
        assertNull(tenant.getActiveKbVersionId());
        List<String> commands = Files.readAllLines(modelDir.resolve("commands.log"));
        assertEquals(2, commands.size());
        assertTrue(commands.get(0).contains(versionDir.resolve("raw_urls.txt").toString().replace("\\", "\\\\")));
        assertTrue(commands.get(0).contains(versionDir.resolve("docs.jsonl").toString().replace("\\", "\\\\")));
        assertTrue(commands.get(1).contains(versionDir.resolve("docs.jsonl").toString().replace("\\", "\\\\")));
        assertTrue(commands.get(1).contains(versionDir.resolve("chunks.jsonl").toString().replace("\\", "\\\\")));
        assertFalse(commands.get(0).contains(rootKbDir.resolve("docs.jsonl").toString().replace("\\", "\\\\")));
        verify(llmInstanceManager).evictTenant(tenantId);
        verify(tenantRepository, never()).save(any(Tenant.class));
    }

    @Test
    void rebuildSuccessSnapshotsEmptyListWhenRawUrlsFileDoesNotExist() throws Exception {
        UUID tenantId = UUID.randomUUID();
        Path modelDir = createModelServerScripts(false);
        Path kbDir = tempDir.resolve("kb").resolve("missing-raw");
        Tenant tenant = tenant(tenantId, kbDir);
        List<TenantKbVersion> savedVersions = new ArrayList<>();
        TenantKbVersionRepository versionRepository = versionRepository(savedVersions);

        TenantKbRebuildService service = newService(tenantRepository(tenant), versionRepository, mock(LlmInstanceManager.class), modelDir);

        service.rebuild(tenantId);

        TenantKbVersion ready = savedVersions.get(1);
        assertEquals("[]", ready.getSourceUrlSnapshot());
        assertEquals(TenantKbVersionStatus.READY, ready.getStatus());
        assertTrue(Files.exists(Path.of(ready.getKbDir()).resolve("raw_urls.txt")));
        assertEquals("", Files.readString(Path.of(ready.getKbDir()).resolve("raw_urls.txt")));
    }

    @Test
    void rebuildSuccessFallsBackToDocsJsonlWhenChunksCannotBeCounted() throws Exception {
        UUID tenantId = UUID.randomUUID();
        Path modelDir = createModelServerScripts(true);
        Path kbDir = tempDir.resolve("kb").resolve("docs-only");
        Files.createDirectories(kbDir);
        Files.writeString(kbDir.resolve("raw_urls.txt"), "https://example.com/help\n");
        Tenant tenant = tenant(tenantId, kbDir);
        List<TenantKbVersion> savedVersions = new ArrayList<>();
        TenantKbVersionRepository versionRepository = versionRepository(savedVersions);

        TenantKbRebuildService service = newService(tenantRepository(tenant), versionRepository, mock(LlmInstanceManager.class), modelDir);

        service.rebuild(tenantId);

        assertEquals(2, savedVersions.get(1).getArtifactCount());
    }

    @Test
    void rebuildFailureMarksVersionFailedAndKeepsExceptionBehavior() throws Exception {
        UUID tenantId = UUID.randomUUID();
        Path modelDir = createFailingModelServerScripts();
        Path kbDir = tempDir.resolve("kb").resolve("fail");
        Files.createDirectories(kbDir);
        Files.writeString(kbDir.resolve("raw_urls.txt"), "https://example.com/help\n");
        Tenant tenant = tenant(tenantId, kbDir);
        List<TenantKbVersion> savedVersions = new ArrayList<>();
        TenantKbVersionRepository versionRepository = versionRepository(savedVersions);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);

        TenantKbRebuildService service = newService(tenantRepository(tenant), versionRepository, llmInstanceManager, modelDir);

        IllegalStateException ex = assertThrows(IllegalStateException.class, () -> service.rebuild(tenantId));

        assertTrue(ex.getMessage().startsWith("KB scrape failed"));
        assertEquals(2, savedVersions.size());
        assertEquals(TenantKbVersionStatus.BUILDING, savedVersions.get(0).getStatus());
        TenantKbVersion failed = savedVersions.get(1);
        assertEquals(TenantKbVersionStatus.FAILED, failed.getStatus());
        assertTrue(Path.of(failed.getKbDir()).startsWith(kbDir.toAbsolutePath().normalize().resolve("versions")));
        assertTrue(Files.exists(Path.of(failed.getKbDir()).resolve("raw_urls.txt")));
        assertNotNull(failed.getBuiltAt());
        assertTrue(failed.getBuildMessage().startsWith("KB scrape failed"));
        assertNull(tenant.getActiveKbVersionId());
        verify(llmInstanceManager, never()).evictTenant(any());
    }

    @Test
    void rebuildWithBlankKbDirFailsBeforeCreatingVersion() {
        UUID tenantId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, null);
        List<TenantKbVersion> savedVersions = new ArrayList<>();
        TenantKbVersionRepository versionRepository = versionRepository(savedVersions);

        TenantKbRebuildService service = newService(tenantRepository(tenant), versionRepository, mock(LlmInstanceManager.class), tempDir);

        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class, () -> service.rebuild(tenantId));

        assertEquals("Tenant kb_dir is not configured", ex.getMessage());
        assertTrue(savedVersions.isEmpty());
    }

    @Test
    void rebuildVersionTagAddsSuffixWhenTimestampCollides() throws Exception {
        UUID tenantId = UUID.randomUUID();
        Path modelDir = createModelServerScripts(false);
        Path kbDir = tempDir.resolve("kb").resolve("collision");
        Tenant tenant = tenant(tenantId, kbDir);
        List<TenantKbVersion> savedVersions = new ArrayList<>();
        TenantKbVersionRepository versionRepository = versionRepository(savedVersions);
        when(versionRepository.findByTenantIdAndVersionTag(eq(tenantId), any(String.class)))
                .thenAnswer(invocation -> {
                    String versionTag = invocation.getArgument(1);
                    return versionTag.endsWith("-2") ? Optional.empty() : Optional.of(new TenantKbVersion());
                });

        TenantKbRebuildService service = newService(tenantRepository(tenant), versionRepository, mock(LlmInstanceManager.class), modelDir);

        service.rebuild(tenantId);

        assertTrue(savedVersions.get(0).getVersionTag().matches("v\\d{14}-2"));
        assertTrue(Path.of(savedVersions.get(0).getKbDir()).endsWith(savedVersions.get(0).getVersionTag()));
    }

    private TenantKbRebuildService newService(
            TenantRepository tenantRepository,
            TenantKbVersionRepository versionRepository,
            LlmInstanceManager llmInstanceManager,
            Path modelDir
    ) {
        LlmProperties llmProperties = new LlmProperties();
        llmProperties.setModelServerDir(modelDir.toString());
        llmProperties.setPythonBin("python");
        TenantKbRebuildStatusService statusService = mock(TenantKbRebuildStatusService.class);
        return new TenantKbRebuildService(tenantRepository, llmProperties, llmInstanceManager, statusService, versionRepository);
    }

    private TenantRepository tenantRepository(Tenant tenant) {
        TenantRepository tenantRepository = mock(TenantRepository.class);
        when(tenantRepository.findById(tenant.getId())).thenReturn(Optional.of(tenant));
        return tenantRepository;
    }

    private TenantKbVersionRepository versionRepository(List<TenantKbVersion> savedVersions) {
        TenantKbVersionRepository versionRepository = mock(TenantKbVersionRepository.class);
        when(versionRepository.findByTenantIdAndVersionTag(any(UUID.class), any(String.class))).thenReturn(Optional.empty());
        when(versionRepository.save(any(TenantKbVersion.class))).thenAnswer(invocation -> {
            TenantKbVersion version = invocation.getArgument(0);
            if (version.getId() == null) {
                version.setId(UUID.randomUUID());
            }
            savedVersions.add(copy(version));
            return version;
        });
        return versionRepository;
    }

    private Tenant tenant(UUID tenantId, Path kbDir) {
        Tenant tenant = new Tenant();
        tenant.setId(tenantId);
        tenant.setCode("demo");
        tenant.setName("Demo Tenant");
        tenant.setApiKey("api-" + tenantId);
        tenant.setStatus("ACTIVE");
        tenant.setKbDir(kbDir == null ? null : kbDir.toString());
        return tenant;
    }

    private TenantKbVersion copy(TenantKbVersion source) {
        TenantKbVersion copy = new TenantKbVersion();
        copy.setId(source.getId());
        copy.setTenantId(source.getTenantId());
        copy.setVersionTag(source.getVersionTag());
        copy.setKbDir(source.getKbDir());
        copy.setSourceUrlSnapshot(source.getSourceUrlSnapshot());
        copy.setArtifactCount(source.getArtifactCount());
        copy.setStatus(source.getStatus());
        copy.setBuildMessage(source.getBuildMessage());
        copy.setBuiltAt(source.getBuiltAt());
        copy.setPublishedAt(source.getPublishedAt());
        copy.setCreatedAt(source.getCreatedAt() == null ? Instant.now() : source.getCreatedAt());
        return copy;
    }

    private Path createModelServerScripts(boolean skipChunks) throws IOException {
        Path modelDir = tempDir.resolve("model-" + UUID.randomUUID());
        Path toolsDir = modelDir.resolve("tools");
        Files.createDirectories(toolsDir);
        Files.writeString(toolsDir.resolve("scrape_site.py"), """
                import json
                import pathlib
                import sys

                command_log = pathlib.Path(__file__).resolve().parents[1] / "commands.log"
                with command_log.open("a", encoding="utf-8") as log:
                    log.write(json.dumps(sys.argv) + "\\n")
                raw_urls = pathlib.Path(sys.argv[2])
                docs_jsonl = pathlib.Path(sys.argv[3])
                raw_urls.parent.mkdir(parents=True, exist_ok=True)
                docs_jsonl.parent.mkdir(parents=True, exist_ok=True)
                if not raw_urls.exists():
                    raw_urls.write_text("https://generated.example/help\\n", encoding="utf-8")
                docs_jsonl.write_text('{"id":"doc-1"}\\n{"id":"doc-2"}\\n', encoding="utf-8")
                """);
        String buildScript = skipChunks
                ? """
                import json
                import pathlib
                import sys

                command_log = pathlib.Path(__file__).resolve().parents[1] / "commands.log"
                with command_log.open("a", encoding="utf-8") as log:
                    log.write(json.dumps(sys.argv) + "\\n")
                index_json = pathlib.Path(sys.argv[3])
                index_json.write_text('{}', encoding="utf-8")
                """
                : """
                import json
                import pathlib
                import sys

                command_log = pathlib.Path(__file__).resolve().parents[1] / "commands.log"
                with command_log.open("a", encoding="utf-8") as log:
                    log.write(json.dumps(sys.argv) + "\\n")
                chunks_jsonl = pathlib.Path(sys.argv[2])
                index_json = pathlib.Path(sys.argv[3])
                chunks_jsonl.write_text('{"id":"chunk-1"}\\n{"id":"chunk-2"}\\n{"id":"chunk-3"}\\n', encoding="utf-8")
                index_json.write_text('{}', encoding="utf-8")
                """;
        Files.writeString(toolsDir.resolve("build_kb.py"), buildScript);
        return modelDir;
    }

    private Path createFailingModelServerScripts() throws IOException {
        Path modelDir = tempDir.resolve("model-fail-" + UUID.randomUUID());
        Path toolsDir = modelDir.resolve("tools");
        Files.createDirectories(toolsDir);
        Files.writeString(toolsDir.resolve("scrape_site.py"), """
                import json
                import pathlib
                import sys

                command_log = pathlib.Path(__file__).resolve().parents[1] / "commands.log"
                with command_log.open("a", encoding="utf-8") as log:
                    log.write(json.dumps(sys.argv) + "\\n")
                print("boom")
                sys.exit(7)
                """);
        Files.writeString(toolsDir.resolve("build_kb.py"), """
                import sys

                sys.exit(0)
                """);
        return modelDir;
    }
}
