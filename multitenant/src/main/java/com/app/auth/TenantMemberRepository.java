package com.app.auth;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface TenantMemberRepository extends JpaRepository<TenantMember, UUID> {
    List<TenantMember> findAllByEmailIgnoreCase(String email);

    List<TenantMember> findAllByTenantIdOrderByEmailAsc(UUID tenantId);

    Optional<TenantMember> findByIdAndTenantId(UUID id, UUID tenantId);

    Optional<TenantMember> findByTenantIdAndEmailIgnoreCase(UUID tenantId, String email);
}
