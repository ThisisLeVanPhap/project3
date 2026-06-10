package com.app.kb;

import com.app.modelserver.LlmInstanceManager;
import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TenantKbVersionServiceTest {

    @Test
    void listVersionsOnlyReturnsTenantVersionsAndMarksActive() {
        UUID tenantId = UUID.randomUUID();
        UUID activeVersionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, activeVersionId);
        TenantKbVersion activeVersion = version(activeVersionId, tenantId, "v2", TenantKbVersionStatus.READY);
        TenantKbVersion otherTenantVersion = version(UUID.randomUUID(), UUID.randomUUID(), "v1", TenantKbVersionStatus.READY);
        TenantKbVersionRepository versionRepository = mock(TenantKbVersionRepository.class);
        TenantRepository tenantRepository = tenantRepository(tenant);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        when(versionRepository.findAllByTenantIdOrderByBuiltAtDescCreatedAtDesc(tenantId))
                .thenReturn(List.of(activeVersion));

        TenantKbVersionService service = new TenantKbVersionService(versionRepository, tenantRepository, llmInstanceManager);

        List<TenantKbVersionResponse> responses = service.listVersionsForTenant(tenantId);

        assertEquals(1, responses.size());
        assertEquals(activeVersionId, responses.get(0).id());
        assertTrue(responses.get(0).active());
        verify(versionRepository, never()).save(otherTenantVersion);
    }

    @Test
    void publishReadyVersionSetsActivePointerAndPublishedAt() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, null);
        TenantKbVersion version = version(versionId, tenantId, "v1", TenantKbVersionStatus.READY);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, version);
        TenantRepository tenantRepository = tenantRepository(tenant);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        TenantKbVersionService service = new TenantKbVersionService(versionRepository, tenantRepository, llmInstanceManager);

        TenantKbVersionResponse response = service.publishVersion(tenantId, versionId);

        assertEquals(versionId, tenant.getActiveKbVersionId());
        assertEquals(versionId, response.id());
        assertTrue(response.active());
        assertNotNull(version.getPublishedAt());
        verify(tenantRepository).save(tenant);
        verify(versionRepository).save(version);
        verify(llmInstanceManager).evictTenant(tenantId);
    }

    @Test
    void publishFailedBuildingOrArchivedVersionIsRejected() {
        assertPublishRejected(TenantKbVersionStatus.FAILED);
        assertPublishRejected(TenantKbVersionStatus.BUILDING);
        assertPublishRejected(TenantKbVersionStatus.ARCHIVED);
    }

    @Test
    void publishOtherTenantVersionIsBlocked() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, null);
        TenantKbVersionRepository versionRepository = mock(TenantKbVersionRepository.class);
        TenantRepository tenantRepository = tenantRepository(tenant);
        when(versionRepository.findByTenantIdAndId(tenantId, versionId)).thenReturn(Optional.empty());
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        TenantKbVersionService service = new TenantKbVersionService(versionRepository, tenantRepository, llmInstanceManager);

        assertThrows(ResponseStatusException.class, () -> service.publishVersion(tenantId, versionId));

        verify(tenantRepository, never()).save(any(Tenant.class));
        verify(llmInstanceManager, never()).evictTenant(any());
    }

    @Test
    void archiveReadyNonActiveVersionMarksArchived() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, UUID.randomUUID());
        TenantKbVersion version = version(versionId, tenantId, "v1", TenantKbVersionStatus.READY);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, version);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        TenantKbVersionService service = new TenantKbVersionService(versionRepository, tenantRepository(tenant), llmInstanceManager);

        TenantKbVersionResponse response = service.archiveVersion(tenantId, versionId);

        assertEquals(TenantKbVersionStatus.ARCHIVED, version.getStatus());
        assertEquals(TenantKbVersionStatus.ARCHIVED, response.status());
        verify(versionRepository).save(version);
        verify(llmInstanceManager, never()).evictTenant(any());
    }

    @Test
    void archiveActiveVersionIsRejected() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, versionId);
        TenantKbVersion version = version(versionId, tenantId, "v1", TenantKbVersionStatus.READY);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, version);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        TenantKbVersionService service = new TenantKbVersionService(versionRepository, tenantRepository(tenant), llmInstanceManager);

        assertThrows(IllegalStateException.class, () -> service.archiveVersion(tenantId, versionId));

        verify(versionRepository, never()).save(version);
    }

    @Test
    void archiveBuildingVersionIsRejected() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, null);
        TenantKbVersion version = version(versionId, tenantId, "v1", TenantKbVersionStatus.BUILDING);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, version);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        TenantKbVersionService service = new TenantKbVersionService(versionRepository, tenantRepository(tenant), llmInstanceManager);

        assertThrows(IllegalStateException.class, () -> service.archiveVersion(tenantId, versionId));

        verify(versionRepository, never()).save(version);
    }

    private void assertPublishRejected(TenantKbVersionStatus status) {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, null);
        TenantKbVersion version = version(versionId, tenantId, "v1", status);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, version);
        TenantRepository tenantRepository = tenantRepository(tenant);
        LlmInstanceManager llmInstanceManager = mock(LlmInstanceManager.class);
        TenantKbVersionService service = new TenantKbVersionService(versionRepository, tenantRepository, llmInstanceManager);

        assertThrows(IllegalStateException.class, () -> service.publishVersion(tenantId, versionId));

        verify(tenantRepository, never()).save(any(Tenant.class));
        verify(versionRepository, never()).save(version);
        verify(llmInstanceManager, never()).evictTenant(any());
    }

    private TenantRepository tenantRepository(Tenant tenant) {
        TenantRepository tenantRepository = mock(TenantRepository.class);
        when(tenantRepository.findById(tenant.getId())).thenReturn(Optional.of(tenant));
        return tenantRepository;
    }

    private TenantKbVersionRepository versionRepository(UUID tenantId, TenantKbVersion version) {
        TenantKbVersionRepository versionRepository = mock(TenantKbVersionRepository.class);
        when(versionRepository.findByTenantIdAndId(tenantId, version.getId())).thenReturn(Optional.of(version));
        return versionRepository;
    }

    private Tenant tenant(UUID tenantId, UUID activeKbVersionId) {
        Tenant tenant = new Tenant();
        tenant.setId(tenantId);
        tenant.setCode("demo");
        tenant.setName("Demo Tenant");
        tenant.setApiKey("api-" + tenantId);
        tenant.setStatus("ACTIVE");
        tenant.setKbDir("chatbot/kb/demo");
        tenant.setActiveKbVersionId(activeKbVersionId);
        return tenant;
    }

    private TenantKbVersion version(UUID id, UUID tenantId, String versionTag, TenantKbVersionStatus status) {
        TenantKbVersion version = new TenantKbVersion();
        version.setId(id);
        version.setTenantId(tenantId);
        version.setVersionTag(versionTag);
        version.setKbDir("chatbot/kb/demo");
        version.setStatus(status);
        version.setArtifactCount(3);
        version.setBuildMessage("done");
        version.setBuiltAt(Instant.parse("2026-06-09T10:00:00Z"));
        version.setCreatedAt(Instant.parse("2026-06-09T09:55:00Z"));
        return version;
    }
}
