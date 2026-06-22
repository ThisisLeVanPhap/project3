package com.app.leads;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.tenant.TenantContext;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@RestController
@RequestMapping("/admin/api/leads")
public class LeadAdminController {

    private final LeadRepository leadRepo;
    private final SessionPrincipalAccessor principalAccessor;

    public LeadAdminController(LeadRepository leadRepo, SessionPrincipalAccessor principalAccessor) {
        this.leadRepo = leadRepo;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping
    public List<Lead> list(@RequestParam("tenantId") String tenantId) {
        principalAccessor.requirePlatformAdmin();
        return leadRepo.findTop200ByTenantIdOrderByCreatedAtDesc(requirePlatformTenantId(tenantId));
    }

    @GetMapping("/{id}")
    public Lead detail(
            @PathVariable Long id,
            @RequestParam(value = "tenantId", required = false) String tenantId
    ) {
        principalAccessor.requirePlatformAdmin();
        String effectiveTenantId = requirePlatformTenantId(tenantId);
        return leadRepo.findByIdAndTenantId(id, effectiveTenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
    }

    @PostMapping("/{id}/status")
    public Lead updateStatus(
            @PathVariable Long id,
            @RequestParam("status") String status,
            @RequestParam(value = "tenantId", required = false) String tenantId
    ) {
        principalAccessor.requirePlatformAdmin();
        String effectiveTenantId = requirePlatformTenantId(tenantId);
        Lead l = leadRepo.findByIdAndTenantId(id, effectiveTenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        l.setStatus(status);
        return leadRepo.save(l);
    }

    private String requirePlatformTenantId(String requestedTenantId) {
        AppPrincipal principal = principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN);
        String tenantId = TenantContext.get();
        if ((tenantId == null || tenantId.isBlank()) && requestedTenantId != null && !requestedTenantId.isBlank()) {
            tenantId = requestedTenantId.trim();
        }
        if (tenantId == null || tenantId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Tenant context required. Select a tenant first.");
        }
        if (requestedTenantId != null && !requestedTenantId.isBlank() && !tenantId.equals(requestedTenantId.trim())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Tenant filter must match current tenant");
        }
        if (principal.role() != AppRole.PLATFORM_ADMIN) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Insufficient role");
        }
        return tenantId;
    }
}
