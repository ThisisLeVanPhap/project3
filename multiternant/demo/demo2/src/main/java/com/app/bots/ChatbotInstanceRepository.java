package com.app.bots;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.UUID;

public interface ChatbotInstanceRepository extends JpaRepository<ChatbotInstance, UUID> {
    @Query("select c from ChatbotInstance c where c.tenantId = :tenantId")
    List<ChatbotInstance> findAllByTenant(@Param("tenantId") UUID tenantId);
}
