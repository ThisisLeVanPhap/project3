package com.app.kb;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface TenantKbBindingRepository extends JpaRepository<TenantKbBinding, UUID> {
    Optional<TenantKbBinding> findFirstByTenantIdAndActiveTrue(UUID tenantId);

    List<TenantKbBinding> findAllByDatasetIdAndActiveTrueAndUpdatePolicy(String datasetId, TenantKbBindingUpdatePolicy updatePolicy);

    List<TenantKbBinding> findAllByTenantIdOrderByUpdatedAtDescCreatedAtDesc(UUID tenantId);
}
