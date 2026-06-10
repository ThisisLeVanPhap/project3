package com.app.modelserver;

import com.app.kb.ResolvedTenantKbDirectory;
import com.app.kb.TenantKbDirectoryResolver;
import com.app.kb.TenantKbDirectorySource;
import org.junit.jupiter.api.Test;

import java.util.UUID;
import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class LlmInstanceManagerTest {

    @Test
    void resolvesLegacyTenantKbDirWhenNoActiveVersionIsAvailable() {
        UUID tenantId = UUID.randomUUID();
        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenReturn(new ResolvedTenantKbDirectory(
                tenantId,
                "chatbot/kb/demo",
                TenantKbDirectorySource.LEGACY_TENANT_KB_DIR,
                null,
                null,
                null
        ));
        LlmInstanceManager manager = new LlmInstanceManager(new LlmProperties(), resolver);

        ResolvedTenantKbDirectory resolved = manager.resolveKbDirectoryForTenant(tenantId);

        assertEquals("chatbot/kb/demo", resolved.kbDir());
        assertEquals(TenantKbDirectorySource.LEGACY_TENANT_KB_DIR, resolved.source());
    }

    @Test
    void resolvesActiveReadyVersionKbDir() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenReturn(new ResolvedTenantKbDirectory(
                tenantId,
                "chatbot/kb/demo/versions/v20260609120000",
                TenantKbDirectorySource.ACTIVE_VERSION,
                versionId,
                "v20260609120000",
                null
        ));
        LlmInstanceManager manager = new LlmInstanceManager(new LlmProperties(), resolver);

        ResolvedTenantKbDirectory resolved = manager.resolveKbDirectoryForTenant(tenantId);

        assertEquals("chatbot/kb/demo/versions/v20260609120000", resolved.kbDir());
        assertEquals(TenantKbDirectorySource.ACTIVE_VERSION, resolved.source());
        assertEquals(versionId, resolved.versionId());
    }

    @Test
    void resolvesLegacyFallbackWhenActiveVersionIsInvalid() {
        UUID tenantId = UUID.randomUUID();
        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenReturn(new ResolvedTenantKbDirectory(
                tenantId,
                "chatbot/kb/demo",
                TenantKbDirectorySource.LEGACY_TENANT_KB_DIR,
                null,
                null,
                "ACTIVE_VERSION_NOT_READY"
        ));
        LlmInstanceManager manager = new LlmInstanceManager(new LlmProperties(), resolver);

        ResolvedTenantKbDirectory resolved = manager.resolveKbDirectoryForTenant(tenantId);

        assertEquals("chatbot/kb/demo", resolved.kbDir());
        assertEquals(TenantKbDirectorySource.LEGACY_TENANT_KB_DIR, resolved.source());
        assertEquals("ACTIVE_VERSION_NOT_READY", resolved.fallbackReason());
    }

    @Test
    void propagatesClearErrorWhenNoUsableKbDirExists() {
        UUID tenantId = UUID.randomUUID();
        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenThrow(new IllegalStateException("Tenant kb_dir is not configured"));
        LlmInstanceManager manager = new LlmInstanceManager(new LlmProperties(), resolver);

        IllegalStateException ex = assertThrows(IllegalStateException.class, () -> manager.resolveKbDirectoryForTenant(tenantId));

        assertEquals("Tenant kb_dir is not configured", ex.getMessage());
    }

    @Test
    void runtimeStatusBeforeTenantProcessStartsReturnsDesiredAndNoRunning() {
        UUID tenantId = UUID.randomUUID();
        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenReturn(new ResolvedTenantKbDirectory(
                tenantId,
                "chatbot/kb/demo/versions/v20260609120000",
                TenantKbDirectorySource.ACTIVE_VERSION,
                UUID.randomUUID(),
                "v20260609120000",
                null
        ));
        LlmInstanceManager manager = new LlmInstanceManager(new LlmProperties(), resolver);

        LlmInstanceManager.RuntimeKbStatusSnapshot status = manager.getRuntimeKbStatus(tenantId);

        assertEquals("chatbot/kb/demo/versions/v20260609120000", status.desired().kbDir());
        assertEquals("ACTIVE_VERSION", status.desired().source());
        assertNull(status.running());
        assertFalse(status.inSync());
    }

    @Test
    void runtimeStatusAfterJavaSpawnedStartupShowsRunningKbDir() {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        ResolvedTenantKbDirectory resolved = new ResolvedTenantKbDirectory(
                tenantId,
                "chatbot/kb/demo/versions/v20260609120000",
                TenantKbDirectorySource.ACTIVE_VERSION,
                versionId,
                "v20260609120000",
                null
        );
        when(resolver.resolve(tenantId)).thenReturn(resolved);
        LlmInstanceManager manager = new LlmInstanceManager(new LlmProperties(), resolver);

        manager.recordSpawnedRuntimeKb(tenantId, resolved, 1234L, Instant.parse("2026-06-09T12:00:00Z"), new FakeProcess(true));

        LlmInstanceManager.RuntimeKbStatusSnapshot status = manager.getRuntimeKbStatus(tenantId);
        assertEquals("JAVA_SPAWNED", status.running().mode());
        assertEquals("chatbot/kb/demo/versions/v20260609120000", status.running().kbDir());
        assertEquals("ACTIVE_VERSION", status.running().source());
        assertEquals(versionId, status.running().versionId());
        assertTrue(status.running().processAlive());
        assertEquals(1234L, status.running().pid());
        assertTrue(status.inSync());
    }

    @Test
    void runtimeStatusAfterActiveVersionChangesIsOutOfSyncUntilEvicted() {
        UUID tenantId = UUID.randomUUID();
        ResolvedTenantKbDirectory oldResolved = new ResolvedTenantKbDirectory(
                tenantId,
                "chatbot/kb/demo/versions/v1",
                TenantKbDirectorySource.ACTIVE_VERSION,
                UUID.randomUUID(),
                "v1",
                null
        );
        ResolvedTenantKbDirectory newResolved = new ResolvedTenantKbDirectory(
                tenantId,
                "chatbot/kb/demo/versions/v2",
                TenantKbDirectorySource.ACTIVE_VERSION,
                UUID.randomUUID(),
                "v2",
                null
        );
        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenReturn(newResolved);
        LlmInstanceManager manager = new LlmInstanceManager(new LlmProperties(), resolver);
        manager.recordSpawnedRuntimeKb(tenantId, oldResolved, 1234L, Instant.parse("2026-06-09T12:00:00Z"), new FakeProcess(true));

        LlmInstanceManager.RuntimeKbStatusSnapshot outOfSync = manager.getRuntimeKbStatus(tenantId);
        assertFalse(outOfSync.inSync());

        manager.evictTenant(tenantId);
        LlmInstanceManager.RuntimeKbStatusSnapshot evicted = manager.getRuntimeKbStatus(tenantId);
        assertNull(evicted.running());
        assertFalse(evicted.inSync());
    }

    @Test
    void runtimeStatusExternalModeDoesNotClaimActualKbDir() {
        UUID tenantId = UUID.randomUUID();
        LlmProperties props = new LlmProperties();
        props.setBaseUrl("http://external-chatbot:8000/");
        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenReturn(new ResolvedTenantKbDirectory(
                tenantId,
                "chatbot/kb/demo",
                TenantKbDirectorySource.LEGACY_TENANT_KB_DIR,
                null,
                null,
                null
        ));
        LlmInstanceManager manager = new LlmInstanceManager(props, resolver);

        LlmInstanceManager.RuntimeKbStatusSnapshot status = manager.getRuntimeKbStatus(tenantId);

        assertEquals("EXTERNAL_BASE_URL", status.running().mode());
        assertNull(status.running().kbDir());
        assertEquals("Java does not own external Python process", status.running().note());
        assertNull(status.inSync());
    }

    @Test
    void runtimeStatusDoesNotExposeSecretsOrEnvironment() {
        UUID tenantId = UUID.randomUUID();
        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenReturn(new ResolvedTenantKbDirectory(
                tenantId,
                "chatbot/kb/demo",
                TenantKbDirectorySource.LEGACY_TENANT_KB_DIR,
                null,
                null,
                null
        ));
        LlmInstanceManager manager = new LlmInstanceManager(new LlmProperties(), resolver);

        LlmInstanceManager.RuntimeKbStatusSnapshot status = manager.getRuntimeKbStatus(tenantId);

        String rendered = status.toString().toLowerCase();
        assertFalse(rendered.contains("token"));
        assertFalse(rendered.contains("secret"));
        assertFalse(rendered.contains("api_key"));
    }

    private static class FakeProcess extends Process {
        private boolean alive;

        private FakeProcess(boolean alive) {
            this.alive = alive;
        }

        @Override
        public java.io.OutputStream getOutputStream() {
            return java.io.OutputStream.nullOutputStream();
        }

        @Override
        public java.io.InputStream getInputStream() {
            return java.io.InputStream.nullInputStream();
        }

        @Override
        public java.io.InputStream getErrorStream() {
            return java.io.InputStream.nullInputStream();
        }

        @Override
        public int waitFor() {
            alive = false;
            return 0;
        }

        @Override
        public int exitValue() {
            if (alive) {
                throw new IllegalThreadStateException("Process is still alive");
            }
            return 0;
        }

        @Override
        public void destroy() {
            alive = false;
        }

        @Override
        public Process destroyForcibly() {
            alive = false;
            return this;
        }

        @Override
        public boolean isAlive() {
            return alive;
        }

        @Override
        public long pid() {
            return 1234L;
        }
    }
}
