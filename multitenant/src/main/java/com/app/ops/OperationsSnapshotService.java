package com.app.ops;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.kb.TenantKbRebuildService;
import com.app.modelserver.LlmInstanceManager;
import com.app.ops.dto.BotOperationsDto;
import com.app.ops.dto.KbOperationsDto;
import com.app.ops.dto.PlatformOperationsSnapshotDto;
import com.app.ops.dto.PurchaseRequestOpsStatsDto;
import com.app.ops.dto.RuntimeOperationsDto;
import com.app.ops.dto.RuntimeActionResponseDto;
import com.app.ops.dto.TenantOperationsSnapshotDto;
import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class OperationsSnapshotService {

    private final TenantRepository tenantRepository;
    private final ChatbotInstanceRepository chatbotInstanceRepository;
    private final LlmInstanceManager llmInstanceManager;
    private final TenantKbRebuildService tenantKbRebuildService;
    private final PurchaseRequestOpsStatsService purchaseRequestOpsStatsService;

    public PlatformOperationsSnapshotDto getPlatformSnapshot() {
        Instant now = Instant.now();
        Map<UUID, LlmInstanceManager.RuntimeStatusSnapshot> runtimeByTenant = llmInstanceManager.dumpRuntimeStatuses();
        Map<UUID, List<ChatbotInstance>> botsByTenant = chatbotInstanceRepository.findAll().stream()
                .collect(Collectors.groupingBy(ChatbotInstance::getTenantId));
        Map<String, PurchaseRequestOpsStatsDto> purchaseRequestStatsByTenant = purchaseRequestOpsStatsService.getStatsByTenant();

        List<TenantOperationsSnapshotDto> tenants = tenantRepository.findAll().stream()
                .sorted(Comparator.comparing(Tenant::getName, Comparator.nullsLast(String.CASE_INSENSITIVE_ORDER)))
                .map(tenant -> toTenantSnapshot(
                        tenant,
                        now,
                        runtimeByTenant.get(tenant.getId()),
                        botsByTenant.get(tenant.getId()),
                        purchaseRequestStatsByTenant.getOrDefault(tenant.getId().toString(), PurchaseRequestOpsStatsDto.empty())
                ))
                .toList();

        int activeRuntimeSessionCount = (int) tenants.stream()
                .filter(snapshot -> snapshot.runtime().active())
                .count();

        return new PlatformOperationsSnapshotDto(
                now,
                tenants.size(),
                activeRuntimeSessionCount,
                purchaseRequestOpsStatsService.getPlatformStats(),
                tenants
        );
    }

    public TenantOperationsSnapshotDto getTenantSnapshot(UUID tenantId) {
        Tenant tenant = tenantRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Tenant not found"));
        Instant now = Instant.now();
        LlmInstanceManager.RuntimeStatusSnapshot runtime = llmInstanceManager.dumpRuntimeStatuses().get(tenantId);
        List<ChatbotInstance> bots = chatbotInstanceRepository.findAllByTenant(tenantId);
        return toTenantSnapshot(
                tenant,
                now,
                runtime,
                bots,
                purchaseRequestOpsStatsService.getTenantStats(tenantId.toString())
        );
    }

    public RuntimeActionResponseDto evictTenantRuntime(UUID tenantId) {
        tenantRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Tenant not found"));
        llmInstanceManager.evictTenant(tenantId);
        return new RuntimeActionResponseDto(
                true,
                "EVICT_RUNTIME",
                tenantId,
                "Tenant runtime evicted. The next request will cold start a fresh runtime if needed.",
                Instant.now()
        );
    }

    private TenantOperationsSnapshotDto toTenantSnapshot(
            Tenant tenant,
            Instant generatedAt,
            LlmInstanceManager.RuntimeStatusSnapshot runtime,
            List<ChatbotInstance> bots,
            PurchaseRequestOpsStatsDto purchaseRequestStats
    ) {
        List<BotOperationsDto> botDtos = (bots == null ? List.<ChatbotInstance>of() : bots).stream()
                .sorted(Comparator.comparing(ChatbotInstance::getName, Comparator.nullsLast(String.CASE_INSENSITIVE_ORDER)))
                .map(bot -> new BotOperationsDto(
                        bot.getId(),
                        bot.getName(),
                        bot.getChannel(),
                        bot.getStatus(),
                        bot.getBaseModel(),
                        bot.getResponseStyle()
                ))
                .toList();

        RuntimeOperationsDto runtimeDto = new RuntimeOperationsDto(
                runtime != null,
                runtime == null ? "STOPPED" : (runtime.healthy() ? "RUNNING" : "UNHEALTHY"),
                runtime == null ? null : runtime.baseUrl(),
                runtime == null ? -1 : runtime.pid(),
                runtime == null ? null : runtime.lastUsedAt()
        );

        TenantKbRebuildService.KbStatusSnapshot kbSnapshot = tenantKbRebuildService.inspectStatus(tenant.getId());
        KbOperationsDto kbDto = new KbOperationsDto(
                kbSnapshot.kbDir(),
                kbSnapshot.status(),
                kbSnapshot.lastRebuildAt(),
                kbSnapshot.artifactCount(),
                kbSnapshot.sourceType(),
                kbSnapshot.datasetId(),
                kbSnapshot.source(),
                kbSnapshot.sourceUrl(),
                kbSnapshot.lastRebuildStartedAt(),
                kbSnapshot.lastRebuildFinishedAt(),
                kbSnapshot.lastRebuildStatus(),
                kbSnapshot.lastRebuildMessage(),
                kbSnapshot.rebuildHistory()
        );

        return new TenantOperationsSnapshotDto(
                tenant.getId(),
                tenant.getCode(),
                tenant.getName(),
                generatedAt,
                runtimeDto,
                kbDto,
                botDtos,
                purchaseRequestStats
        );
    }
}
