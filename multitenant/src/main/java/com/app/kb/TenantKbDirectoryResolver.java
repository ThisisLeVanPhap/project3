package com.app.kb;

import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;
import java.util.UUID;

@Service
public class TenantKbDirectoryResolver {

    private final TenantRepository tenantRepository;
    private final TenantKbVersionRepository tenantKbVersionRepository;

    public TenantKbDirectoryResolver(TenantRepository tenantRepository, TenantKbVersionRepository tenantKbVersionRepository) {
        this.tenantRepository = tenantRepository;
        this.tenantKbVersionRepository = tenantKbVersionRepository;
    }

    public ResolvedTenantKbDirectory resolve(UUID tenantId) {
        Tenant tenant = tenantRepository.findById(tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Tenant not found"));

        UUID activeKbVersionId = tenant.getActiveKbVersionId();
        if (activeKbVersionId != null) {
            Optional<TenantKbVersion> activeVersion = tenantKbVersionRepository.findByTenantIdAndId(tenantId, activeKbVersionId);
            if (activeVersion.isPresent()) {
                TenantKbVersion version = activeVersion.get();
                if (version.getStatus() == TenantKbVersionStatus.READY && !isBlank(version.getKbDir())) {
                    return new ResolvedTenantKbDirectory(
                            tenantId,
                            version.getKbDir().trim(),
                            TenantKbDirectorySource.ACTIVE_VERSION,
                            version.getId(),
                            version.getVersionTag(),
                            null
                    );
                }
                return legacyFallback(tenant, fallbackReasonForInvalidVersion(version));
            }
            return legacyFallback(tenant, "ACTIVE_VERSION_NOT_FOUND");
        }

        return legacyFallback(tenant, null);
    }

    private ResolvedTenantKbDirectory legacyFallback(Tenant tenant, String fallbackReason) {
        String kbDir = tenant.getKbDir();
        if (isBlank(kbDir)) {
            throw new IllegalStateException("Tenant kb_dir is not configured");
        }
        return new ResolvedTenantKbDirectory(
                tenant.getId(),
                kbDir.trim(),
                TenantKbDirectorySource.LEGACY_TENANT_KB_DIR,
                null,
                null,
                fallbackReason
        );
    }

    private String fallbackReasonForInvalidVersion(TenantKbVersion version) {
        if (version.getStatus() != TenantKbVersionStatus.READY) {
            return "ACTIVE_VERSION_NOT_READY";
        }
        return "ACTIVE_VERSION_KB_DIR_BLANK";
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isBlank();
    }
}
