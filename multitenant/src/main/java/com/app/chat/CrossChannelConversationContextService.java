package com.app.chat;

import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class CrossChannelConversationContextService {

    private static final int MAX_CURRENT_HISTORY = 4;
    private static final int MAX_CONTEXT_CONVERSATIONS = 3;
    private static final int MAX_CONTEXT_LINES = 8;
    private static final int MAX_LINE_CHARS = 180;

    private final ConversationRepository conversationRepository;
    private final MessageRepository messageRepository;

    public CrossChannelConversationContextService(
            ConversationRepository conversationRepository,
            MessageRepository messageRepository
    ) {
        this.conversationRepository = conversationRepository;
        this.messageRepository = messageRepository;
    }

    public List<String> enrichHistory(UUID tenantId, Conversation currentConversation, List<String> currentHistory) {
        List<String> enriched = tail(currentHistory, MAX_CURRENT_HISTORY);
        String memory = buildMemory(tenantId, currentConversation);
        if (!memory.isBlank()) {
            enriched.add(memory);
        }
        return enriched;
    }

    private String buildMemory(UUID tenantId, Conversation currentConversation) {
        if (tenantId == null || currentConversation == null || currentConversation.getUnifiedCustomerId() == null) {
            return "";
        }
        UUID currentConversationId = currentConversation.getId();
        List<Conversation> relatedConversations = conversationRepository
                .findByTenantIdAndUnifiedCustomerId(tenantId, currentConversation.getUnifiedCustomerId())
                .stream()
                .filter(conversation -> !conversation.getId().equals(currentConversationId))
                .sorted(Comparator.comparing(Conversation::getCreatedAt, Comparator.nullsLast(Comparator.naturalOrder())).reversed())
                .limit(MAX_CONTEXT_CONVERSATIONS)
                .sorted(Comparator.comparing(Conversation::getCreatedAt, Comparator.nullsLast(Comparator.naturalOrder())))
                .toList();

        List<String> lines = new ArrayList<>();
        for (Conversation conversation : relatedConversations) {
            String channel = channelLabel(conversation.getUserExternalId());
            List<Message> messages = messageRepository.findTop200ByTenantIdAndConversationIdOrderByCreatedAtAsc(
                    tenantId,
                    conversation.getId()
            );
            for (Message message : tail(messages, 6)) {
                if (lines.size() >= MAX_CONTEXT_LINES) {
                    break;
                }
                String role = normalizeRole(message.getRole());
                if (role.isBlank()) {
                    continue;
                }
                String content = compact(message.getContent(), MAX_LINE_CHARS);
                if (!content.isBlank()) {
                    lines.add("- " + channel + " " + role + ": " + content);
                }
            }
            if (lines.size() >= MAX_CONTEXT_LINES) {
                break;
            }
        }
        if (lines.isEmpty()) {
            return "";
        }
        return "Ghi chu he thong: day la boi canh tu cac cuoc tro chuyen truoc cua cung khach hang. "
                + "Neu khach hoi 'nay toi da hoi gi' hoac 'ban co nho toi khong', hay dua vao cac dong nay de tra loi ngan gon.\n"
                + String.join("\n", lines);
    }

    private static <T> List<T> tail(List<T> values, int maxItems) {
        if (values == null || values.isEmpty()) {
            return new ArrayList<>();
        }
        int from = Math.max(0, values.size() - maxItems);
        return new ArrayList<>(values.subList(from, values.size()));
    }

    private static String normalizeRole(String role) {
        String normalized = role == null ? "" : role.trim().toLowerCase(Locale.ROOT);
        if ("user".equals(normalized)) {
            return "khach";
        }
        if ("assistant".equals(normalized)) {
            return "bot";
        }
        return "";
    }

    private static String channelLabel(String userExternalId) {
        String value = userExternalId == null ? "" : userExternalId.trim();
        int index = value.indexOf(':');
        if (index <= 0) {
            return "[kenh truoc]";
        }
        return "[" + value.substring(0, index) + "]";
    }

    private static String compact(String value, int maxChars) {
        if (value == null) {
            return "";
        }
        String compacted = value.replaceAll("\\s+", " ").trim();
        if (compacted.length() <= maxChars) {
            return compacted;
        }
        return compacted.substring(0, Math.max(0, maxChars - 3)).trim() + "...";
    }
}
