package com.app.purchases;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PurchaseRequestRepository extends JpaRepository<PurchaseRequest, Long> {

    long deleteByTenantId(String tenantId);

    Optional<PurchaseRequest> findByIdAndTenantId(Long id, String tenantId);

    Optional<PurchaseRequest> findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(String tenantId, String conversationId);

    List<PurchaseRequest> findByTenantIdAndConversationId(String tenantId, String conversationId);

    Optional<PurchaseRequest> findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(
            String tenantId,
            String conversationId,
            List<String> statuses
    );

    Optional<PurchaseRequest> findByTenantIdAndIdempotencyKey(String tenantId, String idempotencyKey);

    Optional<PurchaseRequest> findByTenantIdAndHandoffId(String tenantId, String handoffId);

    List<PurchaseRequest> findTop200ByTenantIdOrderByCreatedAtDesc(String tenantId);

    List<PurchaseRequest> findTop200ByTenantIdAndStatusOrderByCreatedAtDesc(String tenantId, String status);

    long countByStatus(String status);
}
