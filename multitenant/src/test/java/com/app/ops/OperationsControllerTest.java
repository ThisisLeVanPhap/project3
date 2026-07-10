package com.app.ops;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
import com.app.ops.dto.BenchmarkModeSummaryDto;
import com.app.ops.dto.BenchmarkSummaryDto;
import com.app.ops.dto.BotOperationsDto;
import com.app.ops.dto.KbRebuildHistoryItemDto;
import com.app.ops.dto.KbOperationsDto;
import com.app.ops.dto.PlatformOperationsSnapshotDto;
import com.app.ops.dto.PurchaseRequestOpsStatsDto;
import com.app.ops.dto.RuntimeActionResponseDto;
import com.app.ops.dto.RuntimeOperationsDto;
import com.app.ops.dto.TenantOperationsSnapshotDto;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class OperationsControllerTest {

    @Mock
    private OperationsSnapshotService operationsSnapshotService;

    @Mock
    private BenchmarkSummaryService benchmarkSummaryService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void platformAdminCanLoadPlatformSnapshot() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requirePlatformAdmin()).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "platform@example.com")
        );
        when(operationsSnapshotService.getPlatformSnapshot()).thenReturn(
                new PlatformOperationsSnapshotDto(
                        Instant.parse("2026-04-06T05:00:00Z"),
                        1,
                        1,
                        new PurchaseRequestOpsStatsDto(6, 2, 2, 2, 4, 2),
                        List.of(new TenantOperationsSnapshotDto(
                                tenantId,
                                "demo",
                                "Demo Tenant",
                                Instant.parse("2026-04-06T05:00:00Z"),
                                new RuntimeOperationsDto(true, "RUNNING", "http://127.0.0.1:8101", 4321L, Instant.parse("2026-04-06T04:58:00Z")),
                                new KbOperationsDto(
                                        "F:/kb/demo",
                                        "READY",
                                        Instant.parse("2026-04-06T04:30:00Z"),
                                        4,
                                        null,
                                        null,
                                        null,
                                        null,
                                        Instant.parse("2026-04-06T04:20:00Z"),
                                        Instant.parse("2026-04-06T04:30:00Z"),
                                        "SUCCESS",
                                        "KB rebuilt successfully",
                                        List.of(new KbRebuildHistoryItemDto(
                                                Instant.parse("2026-04-06T04:20:00Z"),
                                                Instant.parse("2026-04-06T04:30:00Z"),
                                                "SUCCESS",
                                                "KB rebuilt successfully"
                                        ))
                                ),
                                List.of(new BotOperationsDto(UUID.fromString("1f1d6f13-b440-462d-a110-5a3e624c3f5d"), "Sales Bot", "telegram", "ACTIVE", "TinyLlama", "balanced")),
                                new PurchaseRequestOpsStatsDto(6, 2, 2, 2, 4, 2)
                        ))
                )
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new OperationsController(operationsSnapshotService, benchmarkSummaryService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/ops/platform"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenantCount").value(1))
                .andExpect(jsonPath("$.activeRuntimeSessionCount").value(1))
                .andExpect(jsonPath("$.purchaseRequests.totalRequests").value(6))
                .andExpect(jsonPath("$.tenants[0].runtime.status").value("RUNNING"))
                .andExpect(jsonPath("$.tenants[0].knowledgeBase.status").value("READY"))
                .andExpect(jsonPath("$.tenants[0].knowledgeBase.rebuildHistory[0].status").value("SUCCESS"))
                .andExpect(jsonPath("$.tenants[0].bots[0].responseStyle").value("balanced"))
                .andExpect(jsonPath("$.tenants[0].purchaseRequests.assignedCount").value(4));

        verify(principalAccessor).requirePlatformAdmin();
        verify(operationsSnapshotService).getPlatformSnapshot();
    }

    @Test
    void tenantAdminCanLoadTenantSnapshot() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requireTenantOperator()).thenReturn(
                new AppPrincipal("tenant-admin", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "tenant@example.com")
        );
        when(operationsSnapshotService.getTenantSnapshot(tenantId)).thenReturn(
                new TenantOperationsSnapshotDto(
                        tenantId,
                        "demo",
                        "Demo Tenant",
                        Instant.parse("2026-04-06T05:00:00Z"),
                        new RuntimeOperationsDto(false, "STOPPED", null, -1, null),
                        new KbOperationsDto(
                                "F:/kb/demo",
                                "NO_ARTIFACTS",
                                null,
                                0,
                                null,
                                null,
                                null,
                                null,
                                null,
                                null,
                                "FAILED",
                                "KB build failed",
                                List.of(new KbRebuildHistoryItemDto(
                                        Instant.parse("2026-04-06T04:20:00Z"),
                                        Instant.parse("2026-04-06T04:25:00Z"),
                                        "FAILED",
                                        "KB build failed"
                                ))
                        ),
                        List.of(),
                        new PurchaseRequestOpsStatsDto(3, 1, 1, 1, 2, 1)
                )
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new OperationsController(operationsSnapshotService, benchmarkSummaryService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/ops/tenant"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenantCode").value("demo"))
                .andExpect(jsonPath("$.runtime.status").value("STOPPED"))
                .andExpect(jsonPath("$.knowledgeBase.status").value("NO_ARTIFACTS"))
                .andExpect(jsonPath("$.knowledgeBase.lastRebuildStatus").value("FAILED"))
                .andExpect(jsonPath("$.knowledgeBase.rebuildHistory[0].status").value("FAILED"))
                .andExpect(jsonPath("$.purchaseRequests.totalRequests").value(3))
                .andExpect(jsonPath("$.purchaseRequests.unassignedCount").value(1));

        verify(principalAccessor).requireTenantOperator();
        verify(operationsSnapshotService).getTenantSnapshot(tenantId);
    }

    @Test
    void tenantAdminCannotLoadPlatformSnapshot() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requirePlatformAdmin();

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new OperationsController(operationsSnapshotService, benchmarkSummaryService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/ops/platform"))
                .andExpect(status().isForbidden());
    }

    @Test
    void platformAdminCanEvictAnyTenantRuntime() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requireCurrent()).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "platform@example.com")
        );
        when(operationsSnapshotService.evictTenantRuntime(tenantId)).thenReturn(
                new RuntimeActionResponseDto(
                        true,
                        "EVICT_RUNTIME",
                        tenantId,
                        "Tenant runtime evicted. The next request will cold start a fresh runtime if needed.",
                        Instant.parse("2026-04-06T05:10:00Z")
                )
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new OperationsController(operationsSnapshotService, benchmarkSummaryService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/ops/runtime/evict").param("tenantId", tenantId.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.tenantId").value(tenantId.toString()))
                .andExpect(jsonPath("$.action").value("EVICT_RUNTIME"));

        verify(principalAccessor).requireCurrent();
        verify(operationsSnapshotService).evictTenantRuntime(tenantId);
    }

    @Test
    void tenantAdminCanEvictOwnRuntime() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requireCurrent()).thenReturn(
                new AppPrincipal("tenant-admin", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "tenant@example.com")
        );
        when(principalAccessor.requireTenantIdMatching(null)).thenReturn(tenantId.toString());
        when(operationsSnapshotService.evictTenantRuntime(tenantId)).thenReturn(
                new RuntimeActionResponseDto(
                        true,
                        "EVICT_RUNTIME",
                        tenantId,
                        "Tenant runtime evicted. The next request will cold start a fresh runtime if needed.",
                        Instant.parse("2026-04-06T05:10:00Z")
                )
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new OperationsController(operationsSnapshotService, benchmarkSummaryService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/ops/runtime/evict"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.tenantId").value(tenantId.toString()));

        verify(principalAccessor).requireTenantIdMatching(null);
        verify(operationsSnapshotService).evictTenantRuntime(tenantId);
    }

    @Test
    void tenantMemberCannotEvictRuntime() throws Exception {
        when(principalAccessor.requireCurrent()).thenReturn(
                new AppPrincipal("tenant-member", AppRole.TENANT_MEMBER, "daf0378f-53e1-4705-8234-41c74287e489", "Tenant Member", "member@example.com")
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new OperationsController(operationsSnapshotService, benchmarkSummaryService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/ops/runtime/evict"))
                .andExpect(status().isForbidden());

        verify(principalAccessor).requireCurrent();
        verify(operationsSnapshotService, never()).evictTenantRuntime(org.mockito.ArgumentMatchers.any());
    }

    @Test
    void platformAdminCanLoadBenchmarkSummary() throws Exception {
        when(principalAccessor.requirePlatformAdmin()).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "platform@example.com")
        );
        when(benchmarkSummaryService.getBenchmarkSummary()).thenReturn(
                new BenchmarkSummaryDto(
                        "F:/20251/prj3/chatbot/eval/results.json",
                        "chatbot/eval/dataset.jsonl",
                        48,
                        5,
                        "Keyword is strongest on the current 48-question Vietnamese dataset.",
                        List.of(
                                "Keyword is strongest on the current 48-question Vietnamese dataset.",
                                "Vector, hybrid, and hybrid_rerank did not outperform the tuned keyword baseline."
                        ),
                        List.of(
                                new BenchmarkModeSummaryDto("keyword", 0.7917, 0.7333, 48),
                                new BenchmarkModeSummaryDto("vector", 0.6667, 0.4639, 48),
                                new BenchmarkModeSummaryDto("hybrid", 0.7917, 0.6708, 48),
                                new BenchmarkModeSummaryDto("hybrid_rerank", 0.7708, 0.6285, 48)
                        )
                )
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new OperationsController(operationsSnapshotService, benchmarkSummaryService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/ops/benchmark-summary"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.datasetSize").value(48))
                .andExpect(jsonPath("$.topK").value(5))
                .andExpect(jsonPath("$.modes[0].mode").value("keyword"))
                .andExpect(jsonPath("$.modes[0].recallAt5").value(0.7917))
                .andExpect(jsonPath("$.summary").value("Keyword is strongest on the current 48-question Vietnamese dataset."));

        verify(principalAccessor).requirePlatformAdmin();
        verify(benchmarkSummaryService).getBenchmarkSummary();
    }
}

