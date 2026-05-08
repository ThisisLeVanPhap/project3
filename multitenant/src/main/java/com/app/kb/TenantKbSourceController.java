package com.app.kb;

import com.app.auth.SessionPrincipalAccessor;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/api/kb/source-urls")
@RequiredArgsConstructor
public class TenantKbSourceController {

    private final TenantKbSourceService tenantKbSourceService;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public TenantKbSourceService.SourceUrlsResponse list() {
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return tenantKbSourceService.list(tenantId);
    }

    @PostMapping
    public TenantKbSourceService.SourceUrlsResponse add(@RequestBody TenantKbSourceService.SourceUrlRequest request) {
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return tenantKbSourceService.add(tenantId, request);
    }

    @DeleteMapping
    public TenantKbSourceService.SourceUrlsResponse remove(@RequestBody TenantKbSourceService.SourceUrlRequest request) {
        UUID tenantId = UUID.fromString(principalAccessor.requireTenantAdmin().tenantId());
        return tenantKbSourceService.remove(tenantId, request);
    }
}
