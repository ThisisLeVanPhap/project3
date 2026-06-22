package com.app.admin;

import com.app.auth.SessionPrincipalAccessor;
import com.app.kb.TenantKbVersion;
import com.app.kb.TenantKbVersionRepository;
import com.app.tenants.Tenant;
import com.app.tenants.TenantProvisioningService;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/admin/tenants")
@RequiredArgsConstructor
public class TenantAdminController {
    private final TenantProvisioningService tenantProvisioningService;
    private final TenantKbVersionRepository tenantKbVersionRepository;
    private final SessionPrincipalAccessor principalAccessor;

    @PostMapping
    public TenantResponse create(@RequestBody TenantProvisioningService.CreateTenantRequest request) {
        principalAccessor.requirePlatformAdmin();
        return from(tenantProvisioningService.create(request));
    }

    @GetMapping
    public List<TenantResponse> list() {
        principalAccessor.requirePlatformAdmin();
        return tenantProvisioningService.list().stream()
                .map(this::from)
                .toList();
    }

    @GetMapping("/{tenantId}")
    public TenantResponse get(@PathVariable UUID tenantId) {
        principalAccessor.requirePlatformAdmin();
        return from(tenantProvisioningService.get(tenantId));
    }

    @DeleteMapping("/{tenantId}")
    public void delete(@PathVariable UUID tenantId) {
        principalAccessor.requirePlatformAdmin();
        tenantProvisioningService.delete(tenantId);
    }

    private TenantResponse from(Tenant tenant) {
        TenantKbVersion activeVersion = tenant.getActiveKbVersionId() == null
                ? null
                : tenantKbVersionRepository.findByTenantIdAndId(tenant.getId(), tenant.getActiveKbVersionId()).orElse(null);
        return new TenantResponse(
                tenant.getId(),
                tenant.getCode(),
                tenant.getName(),
                tenant.getApiKey(),
                tenant.getKbDir(),
                tenant.getStatus(),
                tenant.getActiveKbVersionId(),
                activeVersion == null ? null : activeVersion.getVersionTag(),
                activeVersion == null ? null : activeVersion.getKbDir()
        );
    }

    public record TenantResponse(
            UUID id,
            String code,
            String name,
            String apiKey,
            String kbDir,
            String status,
            @JsonProperty("active_kb_version_id")
            UUID activeKbVersionId,
            @JsonProperty("active_kb_version_tag")
            String activeKbVersionTag,
            @JsonProperty("active_kb_dir")
            String activeKbDir
    ) {
    }
}
