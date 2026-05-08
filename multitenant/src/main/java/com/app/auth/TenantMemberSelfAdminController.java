package com.app.auth;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/tenant-members")
@RequiredArgsConstructor
public class TenantMemberSelfAdminController {

    private final TenantMemberManagementService tenantMemberManagementService;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public List<TenantMemberManagementService.TenantMemberResponse> list() {
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return tenantMemberManagementService.listByTenant(tenantId);
    }

    @PostMapping
    public TenantMemberManagementService.TenantMemberResponse create(
            @RequestBody TenantMemberManagementService.CreateTenantMemberRequest request
    ) {
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return tenantMemberManagementService.create(tenantId, request);
    }
}
