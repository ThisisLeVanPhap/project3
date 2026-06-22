package com.app.feedback;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.List;

public interface FeedbackRepository extends JpaRepository<Feedback, Long> {

    long deleteByTenantId(String tenantId);

    @Query("select count(f) from Feedback f where f.createdAt >= :since")
    long countAllSince(@Param("since") Instant since);

    @Query("select count(f) from Feedback f where f.createdAt >= :since and f.rating = 1")
    long countGoodSince(@Param("since") Instant since);

    @Query("select f.tenantId as k, sum(case when f.rating=1 then 1 else 0 end) as good, count(f) as total " +
            "from Feedback f where f.createdAt >= :since group by f.tenantId")
    List<Object[]> posRateByTenantSince(@Param("since") Instant since);

    @Query("select f.tenantId as k, sum(case when f.rating=1 then 1 else 0 end) as good, " +
            "sum(case when f.rating=-1 then 1 else 0 end) as bad " +
            "from Feedback f where f.createdAt >= :since group by f.tenantId")
    List<Object[]> goodBadByTenantSince(@Param("since") Instant since);
}
