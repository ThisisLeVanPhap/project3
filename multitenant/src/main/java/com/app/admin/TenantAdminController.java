package com.app.admin;

import com.app.auth.SessionPrincipalAccessor;
import com.app.tenants.Tenant;
import com.app.tenants.TenantProvisioningService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/admin/tenants")
@RequiredArgsConstructor
public class TenantAdminController {
    private final TenantProvisioningService tenantProvisioningService;
    private final SessionPrincipalAccessor principalAccessor;

    @PostMapping
    public TenantResponse create(@RequestBody TenantProvisioningService.CreateTenantRequest request) {
        principalAccessor.requirePlatformAdmin();
        return TenantResponse.from(tenantProvisioningService.create(request));
    }

    @GetMapping
    public List<TenantResponse> list() {
        principalAccessor.requirePlatformAdmin();
        return tenantProvisioningService.list().stream()
                .map(TenantResponse::from)
                .toList();
    }

    @GetMapping("/{tenantId}")
    public TenantResponse get(@PathVariable UUID tenantId) {
        principalAccessor.requirePlatformAdmin();
        return TenantResponse.from(tenantProvisioningService.get(tenantId));
    }

    public record TenantResponse(
            UUID id,
            String code,
            String name,
            String apiKey,
            String kbDir,
            String status
    ) {
        static TenantResponse from(Tenant tenant) {
            return new TenantResponse(
                    tenant.getId(),
                    tenant.getCode(),
                    tenant.getName(),
                    tenant.getApiKey(),
                    tenant.getKbDir(),
                    tenant.getStatus()
            );
        }
    }
}
