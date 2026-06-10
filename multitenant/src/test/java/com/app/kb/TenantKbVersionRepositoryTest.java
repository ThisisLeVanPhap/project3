package com.app.kb;

import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

@DataJpaTest(properties = {
        "spring.flyway.enabled=false",
        "spring.jpa.hibernate.ddl-auto=create-drop"
})
@EntityScan(basePackageClasses = {TenantKbVersion.class, Tenant.class})
@EnableJpaRepositories(basePackageClasses = {TenantKbVersionRepository.class, TenantRepository.class})
class TenantKbVersionRepositoryTest {

    @Autowired
    private TenantKbVersionRepository tenantKbVersionRepository;

    @Autowired
    private TenantRepository tenantRepository;

    @Autowired
    private EntityManager entityManager;

    @Test
    void savesReadyTenantKbVersion() {
        UUID tenantId = UUID.randomUUID();

        TenantKbVersion version = saveVersion(tenantId, "v1", "chatbot/kb/demo/v1", TenantKbVersionStatus.READY, Instant.parse("2026-06-01T00:00:00Z"));

        Optional<TenantKbVersion> loaded = tenantKbVersionRepository.findById(version.getId());
        assertTrue(loaded.isPresent());
        assertEquals(tenantId, loaded.get().getTenantId());
        assertEquals("v1", loaded.get().getVersionTag());
        assertEquals("chatbot/kb/demo/v1", loaded.get().getKbDir());
        assertEquals(TenantKbVersionStatus.READY, loaded.get().getStatus());
        assertNotNull(loaded.get().getCreatedAt());
    }

    @Test
    void enforcesUniqueVersionTagPerTenant() {
        UUID tenantId = UUID.randomUUID();
        saveVersion(tenantId, "v1", "chatbot/kb/demo/v1", TenantKbVersionStatus.READY, Instant.parse("2026-06-01T00:00:00Z"));

        TenantKbVersion duplicate = newVersion(tenantId, "v1", "chatbot/kb/demo/v1-copy", TenantKbVersionStatus.READY, Instant.parse("2026-06-02T00:00:00Z"));

        assertThrows(DataIntegrityViolationException.class, () -> {
            tenantKbVersionRepository.saveAndFlush(duplicate);
        });
    }

    @Test
    void allowsSameVersionTagForDifferentTenants() {
        saveVersion(UUID.randomUUID(), "v1", "chatbot/kb/demo-a/v1", TenantKbVersionStatus.READY, Instant.parse("2026-06-01T00:00:00Z"));
        saveVersion(UUID.randomUUID(), "v1", "chatbot/kb/demo-b/v1", TenantKbVersionStatus.READY, Instant.parse("2026-06-01T00:00:00Z"));

        assertEquals(2, tenantKbVersionRepository.findAll().size());
    }

    @Test
    void findsVersionByTenantIdAndVersionTag() {
        UUID tenantId = UUID.randomUUID();
        saveVersion(tenantId, "v1", "chatbot/kb/demo/v1", TenantKbVersionStatus.READY, Instant.parse("2026-06-01T00:00:00Z"));
        saveVersion(UUID.randomUUID(), "v1", "chatbot/kb/other/v1", TenantKbVersionStatus.READY, Instant.parse("2026-06-01T00:00:00Z"));

        Optional<TenantKbVersion> loaded = tenantKbVersionRepository.findByTenantIdAndVersionTag(tenantId, "v1");

        assertTrue(loaded.isPresent());
        assertEquals(tenantId, loaded.get().getTenantId());
        assertEquals("chatbot/kb/demo/v1", loaded.get().getKbDir());
    }

    @Test
    void ordersTenantVersionsByBuiltAtDescendingAndFindsLatestBuiltVersion() {
        UUID tenantId = UUID.randomUUID();
        saveVersion(tenantId, "v1", "chatbot/kb/demo/v1", TenantKbVersionStatus.READY, Instant.parse("2026-06-01T00:00:00Z"));
        saveVersion(tenantId, "v2", "chatbot/kb/demo/v2", TenantKbVersionStatus.READY, Instant.parse("2026-06-03T00:00:00Z"));
        saveVersion(tenantId, "v3", "chatbot/kb/demo/v3", TenantKbVersionStatus.BUILDING, null);

        List<TenantKbVersion> versions = tenantKbVersionRepository.findAllByTenantIdOrderByBuiltAtDesc(tenantId);
        Optional<TenantKbVersion> latest = tenantKbVersionRepository.findFirstByTenantIdAndBuiltAtIsNotNullOrderByBuiltAtDesc(tenantId);

        assertEquals("v2", versions.get(0).getVersionTag());
        assertTrue(latest.isPresent());
        assertEquals("v2", latest.get().getVersionTag());
    }

    @Test
    void persistsTenantActiveKbVersionId() {
        UUID tenantId = UUID.randomUUID();
        TenantKbVersion version = saveVersion(tenantId, "v1", "chatbot/kb/demo/v1", TenantKbVersionStatus.READY, Instant.parse("2026-06-01T00:00:00Z"));
        Tenant tenant = new Tenant();
        tenant.setId(tenantId);
        tenant.setCode("demo-" + tenantId);
        tenant.setName("Demo Tenant");
        tenant.setApiKey("api-" + tenantId);
        tenant.setStatus("ACTIVE");
        tenant.setKbDir("chatbot/kb/demo");
        tenant.setActiveKbVersionId(version.getId());

        tenantRepository.saveAndFlush(tenant);
        entityManager.clear();

        Tenant loaded = tenantRepository.findById(tenantId).orElseThrow();
        assertEquals(version.getId(), loaded.getActiveKbVersionId());
        assertEquals("chatbot/kb/demo", loaded.getKbDir());
    }

    private TenantKbVersion saveVersion(UUID tenantId, String versionTag, String kbDir, TenantKbVersionStatus status, Instant builtAt) {
        return tenantKbVersionRepository.saveAndFlush(newVersion(tenantId, versionTag, kbDir, status, builtAt));
    }

    private TenantKbVersion newVersion(UUID tenantId, String versionTag, String kbDir, TenantKbVersionStatus status, Instant builtAt) {
        TenantKbVersion version = new TenantKbVersion();
        version.setTenantId(tenantId);
        version.setVersionTag(versionTag);
        version.setKbDir(kbDir);
        version.setSourceUrlSnapshot("[\"https://example.com/help\"]");
        version.setArtifactCount(4);
        version.setStatus(status);
        version.setBuiltAt(builtAt);
        return version;
    }
}
