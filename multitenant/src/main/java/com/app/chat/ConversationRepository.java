package com.app.chat;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ConversationRepository extends JpaRepository<Conversation, UUID> {

    // ✅ Needed by MessengerWebhookController / TelegramWebhookController
    Optional<Conversation> findByTenantIdAndChatbotIdAndUserExternalId(
            UUID tenantId,
            UUID chatbotId,
            String userExternalId
    );

    Optional<Conversation> findTop1ByTenantIdAndChatbotIdAndUserExternalIdOrderByCreatedAtDesc(
            UUID tenantId,
            UUID chatbotId,
            String userExternalId
    );

    Optional<Conversation> findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
            UUID tenantId,
            UUID chatbotId,
            String userExternalId,
            String status
    );

    Optional<Conversation> findTop1ByTenantIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
            UUID tenantId,
            String userExternalId,
            String status
    );

    List<Conversation> findByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
            UUID tenantId,
            UUID chatbotId,
            String userExternalId,
            String status
    );

    List<Conversation> findByTenantIdAndChatbotIdAndUserExternalIdStartingWithAndStatusOrderByCreatedAtDesc(
            UUID tenantId,
            UUID chatbotId,
            String userExternalIdPrefix,
            String status
    );

    // ✅ NEW: find all conversations for a unified customer (CRM integration)
    List<Conversation> findByTenantIdAndUnifiedCustomerId(UUID tenantId, UUID unifiedCustomerId);

    // New: list conversations for a chatbot (for web chat sidebar)
    List<Conversation> findTop50ByTenantIdAndChatbotIdOrderByCreatedAtDesc(UUID tenantId, UUID chatbotId);

    // For user conversation ownership filtering
    List<Conversation> findTop50ByTenantIdAndChatbotIdAndUserExternalIdOrderByCreatedAtDesc(
            UUID tenantId, UUID chatbotId, String userExternalId);
}
