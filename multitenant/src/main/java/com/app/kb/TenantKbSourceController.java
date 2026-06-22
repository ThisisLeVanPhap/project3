package com.app.kb;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

@RestController
@RequestMapping("/api/kb/source-urls")
@RequiredArgsConstructor
public class TenantKbSourceController {

    private final TenantKbSourceService tenantKbSourceService;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public TenantKbSourceService.SourceUrlsResponse list() {
        return tenantKbSourceService.list(currentTenantId());
    }

    @PostMapping
    public TenantKbSourceService.SourceUrlsResponse add(@RequestBody TenantKbSourceService.SourceUrlRequest request) {
        return tenantKbSourceService.add(currentTenantId(), request);
    }

    @DeleteMapping
    public TenantKbSourceService.SourceUrlsResponse remove(@RequestBody TenantKbSourceService.SourceUrlRequest request) {
        return tenantKbSourceService.remove(currentTenantId(), request);
    }

    @GetMapping("/config")
    public TenantKbSourceService.SourceConfigResponse config() {
        return tenantKbSourceService.getConfig(currentTenantId());
    }

    @PostMapping("/sitemap")
    public TenantKbSourceService.SourceConfigResponse setSitemap(@RequestBody TenantKbSourceService.SitemapSourceRequest request) {
        return tenantKbSourceService.setSitemap(currentTenantId(), request);
    }

    private UUID currentTenantId() {
        AppPrincipal principal = principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN);
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
