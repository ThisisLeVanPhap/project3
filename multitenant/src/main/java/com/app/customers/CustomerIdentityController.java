package com.app.customers;

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

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/customer-identities/customers")
public class CustomerIdentityController {

    private final CustomerIdentityQueryService queryService;
    private final SessionPrincipalAccessor principalAccessor;

    public CustomerIdentityController(
            CustomerIdentityQueryService queryService,
            SessionPrincipalAccessor principalAccessor
    ) {
        this.queryService = queryService;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping
    public List<CustomerIdentityQueryService.CustomerIdentityCustomerView> listCustomers() {
        return queryService.listCustomers(resolveTenantId());
    }

    @GetMapping("/{customerId}")
    public CustomerIdentityQueryService.CustomerIdentityCustomerDetailView getCustomerDetail(@PathVariable UUID customerId) {
        return queryService.getCustomerDetail(resolveTenantId(), customerId);
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
