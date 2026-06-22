package com.app.chat;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
import com.app.purchases.PurchaseRequestRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class ConversationResetService {

    private static final String ACTIVE_STATUS = "ACTIVE";

    private final ConversationRepository conversationRepository;
    private final MessageRepository messageRepository;
    private final ChannelConversationService channelConversationService;
    private final ChatbotInstanceRepository chatbotInstanceRepository;
    private final LlmInstanceManager llmInstanceManager;
    private final PythonChatClient pythonChatClient;
    private final LeadRepository leadRepository;
    private final PurchaseRequestRepository purchaseRequestRepository;

    @Transactional
    public NewConsultationSessionResponse startNewConsultationSession(
            UUID tenantId,
            UUID chatbotId,
            String channel,
            String senderKeyOrUserExternalId,
            UUID currentConversationId,
            UUID unifiedCustomerId
    ) {
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Tenant context required");
        }
        if (chatbotId == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "chatbotId is required");
        }
        String normalizedChannel = normalizeChannel(channel);
        String conversationUserKey = toConversationUserKey(normalizedChannel, requireText(senderKeyOrUserExternalId, "senderKey"));
        List<Conversation> activeConversations = conversationRepository
                .findByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                        tenantId,
                        chatbotId,
                        conversationUserKey,
                        ACTIVE_STATUS
                );

        long deletedMessageCount = 0;
        long runtimeResetCount = 0;
        long discardedLeadCount = 0;
        long discardedPurchaseRequestCount = 0;
        UUID retainedUnifiedCustomerId = unifiedCustomerId;

        for (Conversation conversation : activeConversations) {
            if (retainedUnifiedCustomerId == null && conversation.getUnifiedCustomerId() != null) {
                retainedUnifiedCustomerId = conversation.getUnifiedCustomerId();
            }
            deletedMessageCount += deleteMessages(tenantId, conversation.getId());
            if (clearRuntimeState(tenantId, conversation)) {
                runtimeResetCount++;
            }
            conversation.setLeadCreated(false);
            discardedLeadCount += discardInProgressLead(tenantId, conversation.getId());
            discardedPurchaseRequestCount += discardInProgressPurchaseRequests(tenantId, conversation.getId());
            conversation.setStatus("CLOSED");
            conversationRepository.save(conversation);
        }

        Conversation fresh = new Conversation();
        fresh.setId(UUID.randomUUID());
        fresh.setTenantId(tenantId);
        fresh.setChatbotId(chatbotId);
        fresh.setUserExternalId(conversationUserKey);
        fresh.setUnifiedCustomerId(retainedUnifiedCustomerId);
        fresh.setStatus(ACTIVE_STATUS);
        fresh.setLeadCreated(false);
        Conversation saved = conversationRepository.save(fresh);

        return new NewConsultationSessionResponse(
                tenantId.toString(),
                saved.getId().toString(),
                activeConversations.size(),
                deletedMessageCount,
                runtimeResetCount,
                discardedLeadCount,
                discardedPurchaseRequestCount
        );
    }

    @Transactional
    public ConversationResetResponse reset(UUID tenantId, ConversationResetRequest request) {
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Tenant context required");
        }
        if (request == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Reset request is required");
        }

        Conversation conversation = resolveConversation(tenantId, request);
        if (!tenantId.equals(conversation.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Conversation does not belong to this tenant");
        }

        long messagesDeleted = 0;
        if (request.shouldDeleteMessages()) {
            messagesDeleted = deleteMessages(tenantId, conversation.getId());
        }

        boolean runtimeCacheCleared = clearRuntimeState(tenantId, conversation);

        conversation.setStatus(ACTIVE_STATUS);
        if (request.shouldResetBusinessFlags()) {
            conversation.setLeadCreated(false);
            discardInProgressLead(tenantId, conversation.getId());
            discardInProgressPurchaseRequests(tenantId, conversation.getId());
        }
        conversationRepository.save(conversation);

        return ConversationResetResponse.success(
                tenantId.toString(),
                conversation.getId().toString(),
                messagesDeleted,
                runtimeCacheCleared
        );
    }

    private long deleteMessages(UUID tenantId, UUID conversationId) {
        long messagesDeleted = messageRepository.countByTenantIdAndConversationId(tenantId, conversationId);
        messageRepository.deleteByTenantIdAndConversationId(tenantId, conversationId);
        return messagesDeleted;
    }

    private long discardInProgressLead(UUID tenantId, UUID conversationId) {
        List<Lead> leads = leadRepository.findByTenantIdAndConversationId(tenantId.toString(), conversationId.toString());
        if (leads == null) {
            return 0;
        }
        long discarded = 0;
        for (Lead lead : leads) {
            if (isInProgressLead(lead)) {
                lead.setStatus("CLOSED");
                lead.setStage("DISCOVER");
                leadRepository.save(lead);
                discarded++;
            }
        }
        return discarded;
    }

    private boolean isInProgressLead(Lead lead) {
        String status = normalize(lead.getStatus());
        String stage = normalize(lead.getStage());
        String shippingStatus = normalize(lead.getShippingStatus());
        if (status.equals("CLOSED") || stage.equals("FULFILLED") || shippingStatus.equals("SHIPPED")) {
            return false;
        }
        return status.equals("NEW")
                || status.equals("CONTACTED")
                || stage.equals("HANDOFF")
                || stage.equals("DISCOVER")
                || stage.equals("SUGGEST")
                || stage.equals("CONFIRM");
    }

    private long discardInProgressPurchaseRequests(UUID tenantId, UUID conversationId) {
        var requests = purchaseRequestRepository.findByTenantIdAndConversationId(
                tenantId.toString(),
                conversationId.toString()
        );
        if (requests == null) {
            return 0;
        }
        long discarded = 0;
        for (var request : requests) {
            if (com.app.purchases.PurchaseRequestStatus.isInProgress(request.getStatus())) {
                request.setStatus(com.app.purchases.PurchaseRequestStatus.RESET_DISCARDED.name());
                purchaseRequestRepository.save(request);
                discarded++;
            }
        }
        return discarded;
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toUpperCase(Locale.ROOT);
    }

    private boolean clearRuntimeState(UUID tenantId, Conversation conversation) {
        try {
            ChatbotInstance bot = chatbotInstanceRepository.findById(conversation.getChatbotId())
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Chatbot not found"));
            if (!tenantId.equals(bot.getTenantId())) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Chatbot does not belong to this tenant");
            }
            LlmInstanceManager.Session session = llmInstanceManager.getOrStartSession(tenantId, bot);
            pythonChatClient.resetState(session.baseUrl(), tenantId.toString(), conversation.getId().toString());
            return true;
        } catch (Exception ex) {
            log.info("Runtime conversation state reset skipped tenant={} conversationId={} reason={}",
                    tenantId,
                    conversation.getId(),
                    ex.getMessage());
            return false;
        }
    }

    private Conversation resolveConversation(UUID tenantId, ConversationResetRequest request) {
        String conversationId = trimToNull(request.conversationId());
        if (conversationId != null) {
            UUID id = parseUuid(conversationId, "conversationId");
            Conversation conversation = conversationRepository.findById(id)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found"));
            if (!tenantId.equals(conversation.getTenantId())) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Conversation does not belong to this tenant");
            }
            return conversation;
        }

        String channel = normalizeChannel(request.channel());
        String externalUserId = trimToNull(request.externalUserId());
        String chatbotId = trimToNull(request.chatbotId());
        if (channel == null || externalUserId == null || chatbotId == null) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "conversationId or channel, externalUserId, and chatbotId are required"
            );
        }

        UUID botId = parseUuid(chatbotId, "chatbotId");
        String conversationUserKey = toConversationUserKey(channel, externalUserId);

        return conversationRepository
                .findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                        tenantId,
                        botId,
                        conversationUserKey,
                        ACTIVE_STATUS
                )
                .or(() -> conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdOrderByCreatedAtDesc(
                        tenantId,
                        botId,
                        conversationUserKey
                ))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found"));
    }

    private String toConversationUserKey(String channel, String externalUserId) {
        if ("web".equals(channel)) {
            return externalUserId;
        }
        if (externalUserId.startsWith(channel + ":")) {
            return externalUserId;
        }
        if ("telegram".equals(channel) && !externalUserId.startsWith("chat:")) {
            return channelConversationService.buildConversationUserKey(channel, "chat:" + externalUserId);
        }
        return channelConversationService.buildConversationUserKey(channel, externalUserId);
    }

    private String normalizeChannel(String value) {
        String channel = trimToNull(value);
        if (channel == null) {
            return null;
        }
        channel = channel.toLowerCase(Locale.ROOT);
        if (!channel.equals("web") && !channel.equals("messenger") && !channel.equals("telegram")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Unsupported channel: " + value);
        }
        return channel;
    }

    private UUID parseUuid(String value, String fieldName) {
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, fieldName + " must be a valid UUID");
        }
    }

    private String requireText(String value, String fieldName) {
        String trimmed = trimToNull(value);
        if (trimmed == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, fieldName + " is required");
        }
        return trimmed;
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isBlank() ? null : trimmed;
    }
}
