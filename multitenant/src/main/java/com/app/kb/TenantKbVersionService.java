package com.app.kb;

import com.app.modelserver.LlmInstanceManager;
import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
public class TenantKbVersionService {

    private final TenantKbVersionRepository tenantKbVersionRepository;
    private final TenantRepository tenantRepository;
    private final LlmInstanceManager llmInstanceManager;

    public TenantKbVersionService(
            TenantKbVersionRepository tenantKbVersionRepository,
            TenantRepository tenantRepository,
            LlmInstanceManager llmInstanceManager
    ) {
        this.tenantKbVersionRepository = tenantKbVersionRepository;
        this.tenantRepository = tenantRepository;
        this.llmInstanceManager = llmInstanceManager;
    }

    public List<TenantKbVersionResponse> listVersionsForTenant(UUID tenantId) {
        Tenant tenant = requireTenant(tenantId);
        UUID activeKbVersionId = tenant.getActiveKbVersionId();
        return tenantKbVersionRepository.findAllByTenantIdOrderByBuiltAtDescCreatedAtDesc(tenantId).stream()
                .map(version -> TenantKbVersionResponse.from(version, activeKbVersionId))
                .toList();
    }

    public TenantKbVersionResponse publishVersion(UUID tenantId, UUID versionId) {
        Tenant tenant = requireTenant(tenantId);
        TenantKbVersion version = requireTenantVersion(tenantId, versionId);
        if (version.getStatus() != TenantKbVersionStatus.READY) {
            throw new IllegalStateException("Only READY KB versions can be published");
        }

        Instant now = Instant.now();
        tenant.setActiveKbVersionId(version.getId());
        version.setPublishedAt(now);
        tenantRepository.save(tenant);
        tenantKbVersionRepository.save(version);
        llmInstanceManager.evictTenant(tenantId);
        return TenantKbVersionResponse.from(version, tenant.getActiveKbVersionId());
    }

    public TenantKbVersionResponse archiveVersion(UUID tenantId, UUID versionId) {
        Tenant tenant = requireTenant(tenantId);
        TenantKbVersion version = requireTenantVersion(tenantId, versionId);
        if (version.getId() != null && version.getId().equals(tenant.getActiveKbVersionId())) {
            throw new IllegalStateException("Active KB version cannot be archived");
        }
        if (version.getStatus() == TenantKbVersionStatus.BUILDING) {
            throw new IllegalStateException("BUILDING KB version cannot be archived");
        }

        version.setStatus(TenantKbVersionStatus.ARCHIVED);
        tenantKbVersionRepository.save(version);
        return TenantKbVersionResponse.from(version, tenant.getActiveKbVersionId());
    }

    private Tenant requireTenant(UUID tenantId) {
        return tenantRepository.findById(tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Tenant not found"));
    }

    private TenantKbVersion requireTenantVersion(UUID tenantId, UUID versionId) {
        return tenantKbVersionRepository.findByTenantIdAndId(tenantId, versionId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "KB version not found"));
    }
}
