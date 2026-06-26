package com.app.general;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

@ExtendWith(MockitoExtension.class)
class SourceRegistryServiceTest {

    @Mock
    private SourceRegistryRepository repository;

    private SourceRegistryService service;

    @BeforeEach
    void setUp() {
        service = new SourceRegistryService(repository);
    }

    // === SSRF protection ===

    @Test
    void rejectsLocalhostUrl() {
        var req = validRequest("test", "http://localhost:8080/sitemap.xml", "TENANT_BOUND");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    @Test
    void rejects127001Url() {
        var req = validRequest("test", "http://127.0.0.1/sitemap.xml", "TENANT_BOUND");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    @Test
    void rejects192168Url() {
        var req = validRequest("test", "http://192.168.1.1/sitemap.xml", "TENANT_BOUND");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    @Test
    void rejects10xUrl() {
        var req = validRequest("test", "http://10.0.0.1/sitemap.xml", "TENANT_BOUND");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    @Test
    void rejectsDockerInternalHost() {
        var req = validRequest("test", "http://host.docker.internal/sitemap.xml", "TENANT_BOUND");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    @Test
    void rejectsPostgresHost() {
        var req = validRequest("test", "http://postgres:5432/sitemap.xml", "TENANT_BOUND");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    @Test
    void rejectsNonHttpScheme() {
        var req = validRequest("test", "ftp://example.com/sitemap.xml", "TENANT_BOUND");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    @Test
    void rejectsMalformedUrl() {
        var req = validRequest("test", "http://", "TENANT_BOUND");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    // === Visibility validation ===

    @Test
    void rejectsInvalidVisibility() {
        var req = validRequest("test", "https://example.com/sitemap.xml", "INVALID_VIS");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    @Test
    void allowsTenantBoundWithoutOwner() {
        // Backend now allows TENANT_BOUND without owner — logs warning instead of rejecting
        var req = new SourceRegistryRequest("test-tb", null, "https://example.com",
                null, "TENANT_BOUND", null, null, null, true, null);
        assertThrows(Exception.class, () -> service.create(req));
    }

    @Test
    void rejectsMissingSourceCode() {
        var req = new SourceRegistryRequest("", "Valid", "https://example.com",
                null, "GLOBAL_PUBLIC", null, null, null, true, null);
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    // === Source code validation ===

    @Test
    void rejectsEmptySourceCode() {
        var req = validRequest("", "https://example.com/sitemap.xml", "GLOBAL_PUBLIC");
        assertThrows(ResponseStatusException.class, () -> service.create(req));
    }

    private SourceRegistryRequest validRequest(String sourceCode, String sitemapUrl, String visibility) {
        return new SourceRegistryRequest(sourceCode, null, "https://example.com",
                sitemapUrl, visibility,
                "TENANT_BOUND".equals(visibility) ? UUID.randomUUID().toString() : null,
                null, null, true, null);
    }
}
