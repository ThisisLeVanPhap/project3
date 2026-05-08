package com.app.kb;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface TenantKbRebuildStatusRepository extends JpaRepository<TenantKbRebuildStatus, UUID> {
}
