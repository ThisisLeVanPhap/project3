package com.app.kb;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

@RestController
@RequestMapping("/api/kb/rebuild")
@RequiredArgsConstructor
public class TenantKbRebuildController {

    private final TenantKbRebuildService tenantKbRebuildService;
    private final SessionPrincipalAccessor principalAccessor;

    @PostMapping
    public TenantKbRebuildService.RebuildResponse rebuild() {
        return tenantKbRebuildService.rebuild(currentTenantId());
    }

    private UUID currentTenantId() {
        AppPrincipal principal = principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN);
        String tenantId = principal.tenantId();
        if ((tenantId == null || tenantId.isBlank()) && principal.role() == AppRole.PLATFORM_ADMIN) {
            tenantId = TenantContext.get();
        }
        if (tenantId == null || tenantId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Tenant-bound principal required");
        }
        return UUID.fromString(tenantId);
    }
}
