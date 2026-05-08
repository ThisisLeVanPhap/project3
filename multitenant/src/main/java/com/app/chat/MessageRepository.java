package com.app.chat;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public interface MessageRepository extends JpaRepository<Message, UUID> {

    List<Message> findTop20ByConversationIdOrderByCreatedAtAsc(UUID conversationId);

    // ✅ stats: total distinct conversations in window
    @Query("select count(distinct m.conversationId) from Message m where m.createdAt >= :since")
    long countDistinctConversationsSince(@Param("since") Instant since);

    @Query("select m.tenantId as k, count(distinct m.conversationId) as v from Message m where m.createdAt >= :since group by m.tenantId")
    List<Object[]> conversationsByTenantSince(@Param("since") Instant since);

    List<Message> findTop200ByTenantIdAndConversationIdOrderByCreatedAtAsc(UUID tenantId, UUID conversationId);

    // New: get latest message in a conversation for preview
    Message findFirstByConversationIdOrderByCreatedAtDesc(UUID conversationId);

    // Count messages in conversation
    long countByConversationId(UUID conversationId);
    void deleteByConversationId(UUID conversationId);
}
