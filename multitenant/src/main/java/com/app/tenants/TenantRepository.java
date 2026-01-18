package com.app.tenants;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;
import java.util.UUID;

public interface TenantRepository extends JpaRepository<Tenant, UUID> {

    @Query("select t.id from Tenant t where t.apiKey = :apiKey")
    Optional<UUID> findIdByApiKey(@Param("apiKey") String apiKey);

    @Query("select t.kbDir from Tenant t where t.id = :tenantId")
    Optional<String> findKbDirById(@Param("tenantId") UUID tenantId);
}
