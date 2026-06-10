package com.app.kb;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface TenantKbVersionRepository extends JpaRepository<TenantKbVersion, UUID> {

    List<TenantKbVersion> findAllByTenantIdOrderByBuiltAtDesc(UUID tenantId);

    List<TenantKbVersion> findAllByTenantIdOrderByBuiltAtDescCreatedAtDesc(UUID tenantId);

    Optional<TenantKbVersion> findByTenantIdAndVersionTag(UUID tenantId, String versionTag);

    Optional<TenantKbVersion> findFirstByTenantIdAndBuiltAtIsNotNullOrderByBuiltAtDesc(UUID tenantId);

    Optional<TenantKbVersion> findByTenantIdAndId(UUID tenantId, UUID id);

    long countByStatus(TenantKbVersionStatus status);
}
