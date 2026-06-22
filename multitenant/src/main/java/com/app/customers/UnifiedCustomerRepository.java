package com.app.customers;

import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface UnifiedCustomerRepository extends JpaRepository<UnifiedCustomer, UUID> {

    Optional<UnifiedCustomer> findFirstByTenantIdAndNormalizedPhone(UUID tenantId, String normalizedPhone);

    Optional<UnifiedCustomer> findFirstByTenantIdAndNormalizedEmail(UUID tenantId, String normalizedEmail);

    List<UnifiedCustomer> findByTenantId(UUID tenantId, Sort sort);

    Optional<UnifiedCustomer> findByIdAndTenantId(UUID id, UUID tenantId);
}
