package com.app.admin;

import com.app.auth.SessionPrincipalAccessor;
import com.app.auth.TenantMemberManagementService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/admin/tenant-members")
@RequiredArgsConstructor
public class TenantMemberAdminController {

    private final TenantMemberManagementService tenantMemberManagementService;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public List<TenantMemberManagementService.TenantMemberResponse> list(@RequestParam UUID tenantId) {
        principalAccessor.requirePlatformAdmin();
        return tenantMemberManagementService.listByTenant(tenantId);
    }

    @PostMapping
    public TenantMemberManagementService.TenantMemberResponse create(
            @RequestParam UUID tenantId,
            @RequestBody TenantMemberManagementService.CreateTenantMemberRequest request
    ) {
        principalAccessor.requirePlatformAdmin();
        return tenantMemberManagementService.create(tenantId, request);
    }
}
