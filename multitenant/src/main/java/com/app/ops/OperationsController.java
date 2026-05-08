package com.app.ops;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.ops.dto.BenchmarkSummaryDto;
import com.app.ops.dto.PlatformOperationsSnapshotDto;
import com.app.ops.dto.RuntimeActionResponseDto;
import com.app.ops.dto.TenantOperationsSnapshotDto;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

import static org.springframework.http.HttpStatus.BAD_REQUEST;
import static org.springframework.http.HttpStatus.FORBIDDEN;

@RestController
@RequestMapping("/api/ops")
@RequiredArgsConstructor
public class OperationsController {

    private final OperationsSnapshotService operationsSnapshotService;
    private final BenchmarkSummaryService benchmarkSummaryService;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping("/platform")
    public PlatformOperationsSnapshotDto platformSnapshot() {
        principalAccessor.requirePlatformAdmin();
        return operationsSnapshotService.getPlatformSnapshot();
    }

    @GetMapping("/benchmark-summary")
    public BenchmarkSummaryDto benchmarkSummary() {
        principalAccessor.requirePlatformAdmin();
        return benchmarkSummaryService.getBenchmarkSummary();
    }

    @GetMapping("/tenant")
    public TenantOperationsSnapshotDto tenantSnapshot() {
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return operationsSnapshotService.getTenantSnapshot(tenantId);
    }

    @PostMapping("/runtime/evict")
    public RuntimeActionResponseDto evictRuntime(@RequestParam(required = false) String tenantId) {
        AppPrincipal principal = principalAccessor.requireCurrent();
        UUID scopedTenantId = resolveEvictionTenantId(principal, tenantId);
        return operationsSnapshotService.evictTenantRuntime(scopedTenantId);
    }

    private UUID resolveEvictionTenantId(AppPrincipal principal, String tenantId) {
        if (principal.role() == AppRole.PLATFORM_ADMIN) {
            if (tenantId == null || tenantId.isBlank()) {
                throw new ResponseStatusException(BAD_REQUEST, "tenantId is required for platform runtime eviction");
            }
            return UUID.fromString(tenantId);
        }
        if (principal.role() == AppRole.TENANT_ADMIN) {
            String scopedTenantId = principalAccessor.requireTenantIdMatching(tenantId);
            return UUID.fromString(scopedTenantId);
        }
        throw new ResponseStatusException(FORBIDDEN, "Insufficient role");
    }
}
