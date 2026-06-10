package com.app.kb;

import com.app.auth.SessionPrincipalAccessor;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

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
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return tenantKbVersionService.listVersionsForTenant(tenantId);
    }

    @PostMapping("/{id}/publish")
    public TenantKbVersionResponse publish(@PathVariable UUID id) {
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return tenantKbVersionService.publishVersion(tenantId, id);
    }

    @PostMapping("/{id}/archive")
    public TenantKbVersionResponse archive(@PathVariable UUID id) {
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return tenantKbVersionService.archiveVersion(tenantId, id);
    }
}
