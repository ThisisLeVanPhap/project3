package com.app.leads;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

public interface LeadRepository extends JpaRepository<Lead, Long> {

    List<Lead> findTop200ByTenantIdOrderByCreatedAtDesc(String tenantId);

    // --- stats ---
    @Query("select count(l) from Lead l where l.createdAt >= :since")
    long countAllSince(@Param("since") Instant since);

    @Query("select count(l) from Lead l where l.createdAt >= :since and l.shippingStatus = 'SHIPPED'")
    long countShippedSince(@Param("since") Instant since);

    @Query("select l.status as k, count(l) as v from Lead l where l.createdAt >= :since group by l.status")
    List<Object[]> statusBreakdownSince(@Param("since") Instant since);

    @Query("select l.tenantId as k, count(l) as v from Lead l where l.createdAt >= :since group by l.tenantId")
    List<Object[]> leadsByTenantSince(@Param("since") Instant since);

    @Query("select l.tenantId as k, count(l) as v from Lead l where l.createdAt >= :since and l.shippingStatus='SHIPPED' group by l.tenantId")
    List<Object[]> shippedByTenantSince(@Param("since") Instant since);

    @Query("select l.tenantId as k, count(l) as v from Lead l where l.createdAt >= :since and l.status='CONTACTED' group by l.tenantId")
    List<Object[]> contactedByTenantSince(@Param("since") Instant since);

    Optional<Lead> findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(String tenantId, String conversationId);
}
