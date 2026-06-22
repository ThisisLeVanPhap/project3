package com.app.crm;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.tenant.TenantContext;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

@RestController
@RequestMapping("/api/crm/customers")
public class CrmCustomerActivityController {

    private final CrmCustomerActivityService activityService;
    private final SessionPrincipalAccessor principalAccessor;

    public CrmCustomerActivityController(
            CrmCustomerActivityService activityService,
            SessionPrincipalAccessor principalAccessor
    ) {
        this.activityService = activityService;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping("/{unifiedCustomerId}/activity")
    public CrmCustomerActivityService.CrmCustomerActivityResponse getActivity(
            @PathVariable UUID unifiedCustomerId
    ) {
        return activityService.getActivity(resolveTenantId(), unifiedCustomerId);
    }

    private UUID resolveTenantId() {
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
