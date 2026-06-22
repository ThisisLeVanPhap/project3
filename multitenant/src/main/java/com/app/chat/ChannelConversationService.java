package com.app.chat;

import com.app.customers.CustomerIdentityService;
import com.app.customers.ResolvedCustomer;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
public class ChannelConversationService {

    private static final String ACTIVE_STATUS = "ACTIVE";

    private final ConversationRepository conversationRepository;
    private final CustomerIdentityService customerIdentityService;

    public ChannelConversationService(
            ConversationRepository conversationRepository,
            CustomerIdentityService customerIdentityService
    ) {
        this.conversationRepository = conversationRepository;
        this.customerIdentityService = customerIdentityService;
    }

    public Conversation findOrCreateActiveConversation(
            UUID tenantId,
            UUID chatbotId,
            String channel,
            String senderKey
    ) {
        String conversationUserKey = toConversationUserKey(channel, senderKey);
        Conversation conversation = conversationRepository
                .findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                        tenantId,
                        chatbotId,
                        conversationUserKey,
                        ACTIVE_STATUS
                )
                .orElseGet(() -> createConversation(tenantId, chatbotId, conversationUserKey));

        // ✅ NEW: Resolve and set unified customer ID if not already set
        if (conversation.getUnifiedCustomerId() == null && customerIdentityService != null) {
            try {
                ResolvedCustomer resolved = customerIdentityService.resolveOrCreateIdentity(
                        tenantId,
                        channel,
                        senderKey,
                        null,
                        null,
                        null
                );
                conversation.setUnifiedCustomerId(resolved.unifiedCustomer().getId());
                conversationRepository.save(conversation);
            } catch (Exception e) {
                // Identity resolution failed - conversation still usable without unified customer
            }
        }

        return conversation;
    }

    public String buildMessengerSenderKey(String pageId, String senderId) {
        return "page:" + normalize(pageId) + ":sender:" + normalize(senderId);
    }

    public String buildTelegramSenderKey(String chatId) {
        return "chat:" + normalize(chatId);
    }

    public String buildConversationUserKey(String channel, String senderKey) {
        return toConversationUserKey(channel, senderKey);
    }

    static String toConversationUserKey(String channel, String senderKey) {
        return normalize(channel) + ":" + normalize(senderKey);
    }

    private Conversation createConversation(UUID tenantId, UUID chatbotId, String conversationUserKey) {
        Conversation conversation = new Conversation();
        conversation.setId(UUID.randomUUID());
        conversation.setTenantId(tenantId);
        conversation.setChatbotId(chatbotId);
        conversation.setUserExternalId(conversationUserKey);
        conversation.setStatus(ACTIVE_STATUS);
        return conversationRepository.save(conversation);
    }

    private static String normalize(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Sender mapping value must not be blank");
        }
        return value.trim();
    }
}
