package com.app.kb;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/kb/versions")
@RequiredArgsConstructor
public class TenantKbVersionController {

    private final TenantKbVersionService tenantKbVersionService;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public List<TenantKbVersionResponse> list() {
        UUID tenantId = currentTenantId();
        return tenantKbVersionService.listVersionsForTenant(tenantId);
    }

    @PostMapping("/{id}/publish")
    public TenantKbVersionResponse publish(@PathVariable UUID id) {
        UUID tenantId = currentTenantId();
        return tenantKbVersionService.publishVersion(tenantId, id);
    }

    @PostMapping("/{id}/archive")
    public TenantKbVersionResponse archive(@PathVariable UUID id) {
        UUID tenantId = currentTenantId();
        return tenantKbVersionService.archiveVersion(tenantId, id);
    }

    private UUID currentTenantId() {
        AppPrincipal principal = principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN);
        if (principal == null) {
            principal = principalAccessor.requireTenantAdmin();
        }
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
