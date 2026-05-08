package com.app.purchases;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PurchaseRequestRepository extends JpaRepository<PurchaseRequest, Long> {

    Optional<PurchaseRequest> findByIdAndTenantId(Long id, String tenantId);

    Optional<PurchaseRequest> findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(String tenantId, String conversationId);

    List<PurchaseRequest> findTop200ByTenantIdOrderByCreatedAtDesc(String tenantId);

    List<PurchaseRequest> findTop200ByTenantIdAndStatusOrderByCreatedAtDesc(String tenantId, String status);
}
