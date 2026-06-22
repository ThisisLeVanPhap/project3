package com.app.customers;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface CustomerIdentityRepository extends JpaRepository<CustomerIdentity, UUID> {

    Optional<CustomerIdentity> findByTenantIdAndChannelAndExternalUserId(
            UUID tenantId,
            String channel,
            String externalUserId
    );

    List<CustomerIdentity> findByTenantIdAndUnifiedCustomerId(UUID tenantId, UUID unifiedCustomerId);
}
