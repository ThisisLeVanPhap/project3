package com.app.chat;

import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
public class ChannelConversationService {

    private static final String ACTIVE_STATUS = "ACTIVE";

    private final ConversationRepository conversationRepository;

    public ChannelConversationService(ConversationRepository conversationRepository) {
        this.conversationRepository = conversationRepository;
    }

    public Conversation findOrCreateActiveConversation(
            UUID tenantId,
            UUID chatbotId,
            String channel,
            String senderKey
    ) {
        String conversationUserKey = toConversationUserKey(channel, senderKey);
        return conversationRepository
                .findTop1ByTenantIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                        tenantId,
                        conversationUserKey,
                        ACTIVE_STATUS
                )
                .orElseGet(() -> createConversation(tenantId, chatbotId, conversationUserKey));
    }

    public String buildMessengerSenderKey(String pageId, String senderId) {
        return "page:" + normalize(pageId) + ":sender:" + normalize(senderId);
    }

    public String buildTelegramSenderKey(String chatId) {
        return "chat:" + normalize(chatId);
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
