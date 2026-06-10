package com.app.kb;

import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class TenantKbDirectoryResolverTest {

    @Test
    void noActiveVersionReturnsLegacyTenantKbDir() {
        UUID tenantId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "chatbot/kb/demo", null);
        TenantKbDirectoryResolver resolver = resolver(tenant, mock(TenantKbVersionRepository.class));

        ResolvedTenantKbDirectory resolved = resolver.resolve(tenantId);

        assertEquals(tenantId, resolved.tenantId());
        assertEquals("chatbot/kb/demo", resolved.kbDir());
        assertEquals(TenantKbDirectorySource.LEGACY_TENANT_KB_DIR, resolved.source());
        assertNull(resolved.versionId());
        assertNull(resolved.versionTag());
        assertNull(resolved.fallbackReason());
    }

    @Test
    void activeReadyVersionReturnsVersionKbDir() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "chatbot/kb/demo", versionId);
        TenantKbVersion version = version(versionId, tenantId, "v20260609120000", "chatbot/kb/demo/versions/v20260609120000", TenantKbVersionStatus.READY);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, versionId, Optional.of(version));
        TenantKbDirectoryResolver resolver = resolver(tenant, versionRepository);

        ResolvedTenantKbDirectory resolved = resolver.resolve(tenantId);

        assertEquals("chatbot/kb/demo/versions/v20260609120000", resolved.kbDir());
        assertEquals(TenantKbDirectorySource.ACTIVE_VERSION, resolved.source());
        assertEquals(versionId, resolved.versionId());
        assertEquals("v20260609120000", resolved.versionTag());
        assertNull(resolved.fallbackReason());
    }

    @Test
    void activeFailedVersionFallsBackToLegacyWithReason() {
        assertInvalidActiveVersionFallsBack(TenantKbVersionStatus.FAILED, "ACTIVE_VERSION_NOT_READY");
    }

    @Test
    void activeArchivedVersionFallsBackToLegacyWithReason() {
        assertInvalidActiveVersionFallsBack(TenantKbVersionStatus.ARCHIVED, "ACTIVE_VERSION_NOT_READY");
    }

    @Test
    void activeBuildingVersionFallsBackToLegacyWithReason() {
        assertInvalidActiveVersionFallsBack(TenantKbVersionStatus.BUILDING, "ACTIVE_VERSION_NOT_READY");
    }

    @Test
    void activeVersionMissingFallsBackToLegacyWithReason() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "chatbot/kb/demo", versionId);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, versionId, Optional.empty());
        TenantKbDirectoryResolver resolver = resolver(tenant, versionRepository);

        ResolvedTenantKbDirectory resolved = resolver.resolve(tenantId);

        assertEquals("chatbot/kb/demo", resolved.kbDir());
        assertEquals(TenantKbDirectorySource.LEGACY_TENANT_KB_DIR, resolved.source());
        assertEquals("ACTIVE_VERSION_NOT_FOUND", resolved.fallbackReason());
    }

    @Test
    void activeReadyVersionWithBlankKbDirFallsBackToLegacyWithReason() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "chatbot/kb/demo", versionId);
        TenantKbVersion version = version(versionId, tenantId, "v1", "  ", TenantKbVersionStatus.READY);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, versionId, Optional.of(version));
        TenantKbDirectoryResolver resolver = resolver(tenant, versionRepository);

        ResolvedTenantKbDirectory resolved = resolver.resolve(tenantId);

        assertEquals("chatbot/kb/demo", resolved.kbDir());
        assertEquals(TenantKbDirectorySource.LEGACY_TENANT_KB_DIR, resolved.source());
        assertEquals("ACTIVE_VERSION_KB_DIR_BLANK", resolved.fallbackReason());
    }

    @Test
    void blankLegacyKbDirAndNoValidActiveVersionThrowsClearError() {
        UUID tenantId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, " ", null);
        TenantKbDirectoryResolver resolver = resolver(tenant, mock(TenantKbVersionRepository.class));

        IllegalStateException ex = assertThrows(IllegalStateException.class, () -> resolver.resolve(tenantId));

        assertEquals("Tenant kb_dir is not configured", ex.getMessage());
    }

    @Test
    void crossTenantActiveVersionCannotBeResolvedAndFallsBack() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "chatbot/kb/demo", versionId);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, versionId, Optional.empty());
        TenantKbDirectoryResolver resolver = resolver(tenant, versionRepository);

        ResolvedTenantKbDirectory resolved = resolver.resolve(tenantId);

        assertEquals(TenantKbDirectorySource.LEGACY_TENANT_KB_DIR, resolved.source());
        assertEquals("ACTIVE_VERSION_NOT_FOUND", resolved.fallbackReason());
    }

    @Test
    void missingTenantThrowsNotFound() {
        UUID tenantId = UUID.randomUUID();
        TenantRepository tenantRepository = mock(TenantRepository.class);
        when(tenantRepository.findById(tenantId)).thenReturn(Optional.empty());
        TenantKbDirectoryResolver resolver = new TenantKbDirectoryResolver(tenantRepository, mock(TenantKbVersionRepository.class));

        assertThrows(ResponseStatusException.class, () -> resolver.resolve(tenantId));
    }

    private void assertInvalidActiveVersionFallsBack(TenantKbVersionStatus status, String fallbackReason) {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Tenant tenant = tenant(tenantId, "chatbot/kb/demo", versionId);
        TenantKbVersion version = version(versionId, tenantId, "v1", "chatbot/kb/demo/versions/v1", status);
        TenantKbVersionRepository versionRepository = versionRepository(tenantId, versionId, Optional.of(version));
        TenantKbDirectoryResolver resolver = resolver(tenant, versionRepository);

        ResolvedTenantKbDirectory resolved = resolver.resolve(tenantId);

        assertEquals("chatbot/kb/demo", resolved.kbDir());
        assertEquals(TenantKbDirectorySource.LEGACY_TENANT_KB_DIR, resolved.source());
        assertEquals(fallbackReason, resolved.fallbackReason());
    }

    private TenantKbDirectoryResolver resolver(Tenant tenant, TenantKbVersionRepository versionRepository) {
        TenantRepository tenantRepository = mock(TenantRepository.class);
        when(tenantRepository.findById(tenant.getId())).thenReturn(Optional.of(tenant));
        return new TenantKbDirectoryResolver(tenantRepository, versionRepository);
    }

    private TenantKbVersionRepository versionRepository(UUID tenantId, UUID versionId, Optional<TenantKbVersion> version) {
        TenantKbVersionRepository versionRepository = mock(TenantKbVersionRepository.class);
        when(versionRepository.findByTenantIdAndId(tenantId, versionId)).thenReturn(version);
        return versionRepository;
    }

    private Tenant tenant(UUID tenantId, String kbDir, UUID activeKbVersionId) {
        Tenant tenant = new Tenant();
        tenant.setId(tenantId);
        tenant.setCode("demo");
        tenant.setName("Demo Tenant");
        tenant.setApiKey("api-" + tenantId);
        tenant.setStatus("ACTIVE");
        tenant.setKbDir(kbDir);
        tenant.setActiveKbVersionId(activeKbVersionId);
        return tenant;
    }

    private TenantKbVersion version(UUID versionId, UUID tenantId, String versionTag, String kbDir, TenantKbVersionStatus status) {
        TenantKbVersion version = new TenantKbVersion();
        version.setId(versionId);
        version.setTenantId(tenantId);
        version.setVersionTag(versionTag);
        version.setKbDir(kbDir);
        version.setStatus(status);
        return version;
    }
}
