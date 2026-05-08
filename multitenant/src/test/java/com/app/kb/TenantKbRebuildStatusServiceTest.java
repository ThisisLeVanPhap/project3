package com.app.kb;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TenantKbRebuildStatusServiceTest {

    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

    @Test
    void returnsTrackedSnapshotWhenPresent() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        TenantKbRebuildStatusRepository repository = mock(TenantKbRebuildStatusRepository.class);
        TenantKbRebuildStatus entity = new TenantKbRebuildStatus();
        entity.setTenantId(tenantId);
        entity.setLastRebuildStartedAt(Instant.parse("2026-04-06T05:00:00Z"));
        entity.setLastRebuildFinishedAt(Instant.parse("2026-04-06T05:05:00Z"));
        entity.setLastRebuildStatus("SUCCESS");
        entity.setLastRebuildMessage("KB rebuilt successfully");
        entity.setRebuildHistoryJson("""
                [{"startedAt":"2026-04-06T05:00:00Z","finishedAt":"2026-04-06T05:05:00Z","status":"SUCCESS","message":"KB rebuilt successfully"}]
                """);
        when(repository.findById(tenantId)).thenReturn(Optional.of(entity));

        TenantKbRebuildStatusService service = new TenantKbRebuildStatusService(repository, objectMapper);
        TenantKbRebuildStatusService.RebuildTrackingSnapshot snapshot = service.getSnapshot(tenantId);

        assertEquals("SUCCESS", snapshot.lastRebuildStatus());
        assertEquals("KB rebuilt successfully", snapshot.lastRebuildMessage());
        assertEquals(Instant.parse("2026-04-06T05:00:00Z"), snapshot.lastRebuildStartedAt());
        assertEquals(Instant.parse("2026-04-06T05:05:00Z"), snapshot.lastRebuildFinishedAt());
        assertEquals(1, snapshot.history().size());
    }

    @Test
    void writesAndUpdatesRecentHistory() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        TenantKbRebuildStatusRepository repository = mock(TenantKbRebuildStatusRepository.class);
        TenantKbRebuildStatus entity = new TenantKbRebuildStatus();
        entity.setTenantId(tenantId);
        when(repository.findById(tenantId)).thenReturn(Optional.of(entity));

        TenantKbRebuildStatusService service = new TenantKbRebuildStatusService(repository, objectMapper);
        Instant startedAt = Instant.parse("2026-04-06T05:00:00Z");
        Instant finishedAt = Instant.parse("2026-04-06T05:05:00Z");

        service.markStarted(tenantId, startedAt, "KB rebuild started");
        assertFalse(entity.getRebuildHistoryJson().isBlank());

        service.markFinished(tenantId, startedAt, finishedAt, "SUCCESS", "KB rebuilt successfully");
        TenantKbRebuildStatusService.RebuildTrackingSnapshot snapshot = service.getSnapshot(tenantId);

        assertEquals(1, snapshot.history().size());
        assertEquals("SUCCESS", snapshot.history().get(0).status());
        assertEquals(finishedAt, snapshot.history().get(0).finishedAt());
        verify(repository, times(2)).save(entity);
    }
}
