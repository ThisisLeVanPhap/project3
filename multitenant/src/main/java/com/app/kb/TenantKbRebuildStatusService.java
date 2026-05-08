package com.app.kb;

import com.app.ops.dto.KbRebuildHistoryItemDto;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class TenantKbRebuildStatusService {

    private static final int HISTORY_LIMIT = 5;

    public record RebuildTrackingSnapshot(
            Instant lastRebuildStartedAt,
            Instant lastRebuildFinishedAt,
            String lastRebuildStatus,
            String lastRebuildMessage,
            List<KbRebuildHistoryItemDto> history
    ) {
    }

    private final TenantKbRebuildStatusRepository repository;
    private final ObjectMapper objectMapper;

    public void markStarted(UUID tenantId, Instant startedAt, String message) {
        TenantKbRebuildStatus status = repository.findById(tenantId)
                .orElseGet(() -> newStatus(tenantId));
        status.setLastRebuildStartedAt(startedAt);
        status.setLastRebuildFinishedAt(null);
        status.setLastRebuildStatus("IN_PROGRESS");
        status.setLastRebuildMessage(message);
        status.setRebuildHistoryJson(writeHistory(updateHistory(readHistory(status), startedAt, null, "IN_PROGRESS", message)));
        repository.save(status);
    }

    public void markFinished(UUID tenantId, Instant startedAt, Instant finishedAt, String rebuildStatus, String message) {
        TenantKbRebuildStatus status = repository.findById(tenantId)
                .orElseGet(() -> newStatus(tenantId));
        status.setLastRebuildStartedAt(startedAt);
        status.setLastRebuildFinishedAt(finishedAt);
        status.setLastRebuildStatus(rebuildStatus);
        status.setLastRebuildMessage(message);
        status.setRebuildHistoryJson(writeHistory(updateHistory(readHistory(status), startedAt, finishedAt, rebuildStatus, message)));
        repository.save(status);
    }

    public RebuildTrackingSnapshot getSnapshot(UUID tenantId) {
        return repository.findById(tenantId)
                .map(status -> new RebuildTrackingSnapshot(
                        status.getLastRebuildStartedAt(),
                        status.getLastRebuildFinishedAt(),
                        status.getLastRebuildStatus(),
                        status.getLastRebuildMessage(),
                        readHistory(status)
                ))
                .orElse(new RebuildTrackingSnapshot(null, null, null, null, List.of()));
    }

    private TenantKbRebuildStatus newStatus(UUID tenantId) {
        TenantKbRebuildStatus status = new TenantKbRebuildStatus();
        status.setTenantId(tenantId);
        return status;
    }

    private List<KbRebuildHistoryItemDto> readHistory(TenantKbRebuildStatus status) {
        String json = status.getRebuildHistoryJson();
        if (json == null || json.isBlank()) {
            return List.of();
        }
        try {
            return List.copyOf(objectMapper.readValue(json, new TypeReference<List<KbRebuildHistoryItemDto>>() {}));
        } catch (JsonProcessingException e) {
            return List.of();
        }
    }

    private String writeHistory(List<KbRebuildHistoryItemDto> history) {
        try {
            return objectMapper.writeValueAsString(history);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Failed to serialize KB rebuild history", e);
        }
    }

    private List<KbRebuildHistoryItemDto> updateHistory(
            List<KbRebuildHistoryItemDto> existing,
            Instant startedAt,
            Instant finishedAt,
            String status,
            String message
    ) {
        List<KbRebuildHistoryItemDto> updated = new ArrayList<>(existing);
        KbRebuildHistoryItemDto nextItem = new KbRebuildHistoryItemDto(startedAt, finishedAt, status, message);
        int existingIndex = -1;
        for (int i = 0; i < updated.size(); i++) {
            KbRebuildHistoryItemDto item = updated.get(i);
            if (startedAt != null && startedAt.equals(item.startedAt())) {
                existingIndex = i;
                break;
            }
        }
        if (existingIndex >= 0) {
            updated.set(existingIndex, nextItem);
        } else {
            updated.add(nextItem);
        }
        return updated.stream()
                .sorted(Comparator.comparing(KbRebuildHistoryItemDto::startedAt, Comparator.nullsLast(Comparator.reverseOrder())))
                .limit(HISTORY_LIMIT)
                .toList();
    }
}
