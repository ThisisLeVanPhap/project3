package com.app.kb;

import com.app.auth.SessionPrincipalAccessor;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/api/kb/rebuild")
@RequiredArgsConstructor
public class TenantKbRebuildController {

    private final TenantKbRebuildService tenantKbRebuildService;
    private final SessionPrincipalAccessor principalAccessor;

    @PostMapping
    public TenantKbRebuildService.RebuildResponse rebuild() {
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return tenantKbRebuildService.rebuild(tenantId);
    }
}
