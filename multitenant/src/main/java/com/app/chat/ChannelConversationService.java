package com.app.chat;

import com.app.customers.CustomerIdentityService;
import com.app.customers.ResolvedCustomer;
import org.springframework.stereotype.Service;

import java.util.Optional;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class ChannelConversationService {

    private static final String ACTIVE_STATUS = "ACTIVE";
    static final String DEMO_CUSTOMER_SUFFIX = "#demo:";
    private static final Pattern EMAIL_PATTERN = Pattern.compile(
            "[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}",
            Pattern.CASE_INSENSITIVE
    );
    private static final Pattern PHONE_PATTERN = Pattern.compile(
            "(?<!\\d)(?:\\+?84|0)(?:[\\s.\\-]?\\d){8,10}(?!\\d)"
    );

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
                .or(() -> findActiveDemoConversation(tenantId, chatbotId, conversationUserKey, channel))
                .orElseGet(() -> createConversation(tenantId, chatbotId, conversationUserKey));

        // ✅ NEW: Resolve and set unified customer ID if not already set
        if (conversation.getUnifiedCustomerId() == null && customerIdentityService != null) {
            try {
                ResolvedCustomer resolved = customerIdentityService.resolveOrCreateIdentity(
                        tenantId,
                        channel,
                        identityExternalUserId(conversation, senderKey),
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

    public Optional<ResolvedCustomer> linkIdentityFromMessage(
            UUID tenantId,
            Conversation conversation,
            String channel,
            String senderKey,
            String displayName,
            String message
    ) {
        if (conversation == null || customerIdentityService == null) {
            return Optional.empty();
        }
        String phone = firstMatch(PHONE_PATTERN, message);
        String email = firstMatch(EMAIL_PATTERN, message);
        if (phone == null && email == null) {
            return Optional.empty();
        }
        try {
            ResolvedCustomer resolved = customerIdentityService.resolveOrCreateIdentity(
                    tenantId,
                    channel,
                    identityExternalUserId(conversation, senderKey),
                    displayName,
                    phone,
                    email
            );
            conversation.setUnifiedCustomerId(resolved.unifiedCustomer().getId());
            conversationRepository.save(conversation);
            return Optional.of(resolved);
        } catch (RuntimeException ex) {
            return Optional.empty();
        }
    }

    private java.util.Optional<Conversation> findActiveDemoConversation(
            UUID tenantId,
            UUID chatbotId,
            String conversationUserKey,
            String channel
    ) {
        if ("web".equalsIgnoreCase(channel)) {
            return java.util.Optional.empty();
        }
        String baseKey = stripDemoSuffix(conversationUserKey);
        return conversationRepository
                .findByTenantIdAndChatbotIdAndUserExternalIdStartingWithAndStatusOrderByCreatedAtDesc(
                        tenantId,
                        chatbotId,
                        baseKey + DEMO_CUSTOMER_SUFFIX,
                        ACTIVE_STATUS
                )
                .stream()
                .findFirst();
    }

    private String identityExternalUserId(Conversation conversation, String senderKey) {
        String userExternalId = conversation.getUserExternalId();
        if (userExternalId != null && userExternalId.contains(DEMO_CUSTOMER_SUFFIX)) {
            return userExternalId;
        }
        return senderKey;
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

    static String stripDemoSuffix(String userExternalId) {
        int index = userExternalId == null ? -1 : userExternalId.indexOf(DEMO_CUSTOMER_SUFFIX);
        return index < 0 ? userExternalId : userExternalId.substring(0, index);
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

    private static String firstMatch(Pattern pattern, String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        Matcher matcher = pattern.matcher(value);
        return matcher.find() ? matcher.group() : null;
    }
}
