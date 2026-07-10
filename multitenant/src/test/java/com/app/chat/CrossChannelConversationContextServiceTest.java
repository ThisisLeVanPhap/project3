package com.app.chat;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class CrossChannelConversationContextServiceTest {

    @Test
    void enrichHistoryAddsPreviousChannelConversationForSameCustomer() {
        ConversationRepository conversationRepository = mock(ConversationRepository.class);
        MessageRepository messageRepository = mock(MessageRepository.class);
        CrossChannelConversationContextService service =
                new CrossChannelConversationContextService(conversationRepository, messageRepository);

        UUID tenantId = UUID.randomUUID();
        UUID unifiedCustomerId = UUID.randomUUID();
        Conversation current = conversation(tenantId, UUID.randomUUID(), "telegram:chat:42", unifiedCustomerId);
        Conversation previous = conversation(tenantId, UUID.randomUUID(), "messenger:page:p1:sender:s1", unifiedCustomerId);

        when(conversationRepository.findByTenantIdAndUnifiedCustomerId(tenantId, unifiedCustomerId))
                .thenReturn(List.of(current, previous));
        when(messageRepository.findTop200ByTenantIdAndConversationIdOrderByCreatedAtAsc(tenantId, previous.getId()))
                .thenReturn(List.of(
                        message(tenantId, previous.getId(), "user", "Tôi cần tư vấn sofa nhỏ cho phòng khách"),
                        message(tenantId, previous.getId(), "assistant", "Bạn có thể cân nhắc mẫu sofa góc nhỏ.")
                ));

        List<String> enriched = service.enrichHistory(tenantId, current, List.of("Tôi quay lại đây"));

        assertEquals(2, enriched.size());
        assertEquals("Tôi quay lại đây", enriched.get(0));
        assertTrue(enriched.get(1).contains("boi canh tu cac cuoc tro chuyen truoc"));
        assertTrue(enriched.get(1).contains("[messenger] khach: Tôi cần tư vấn sofa nhỏ"));
        assertTrue(enriched.get(1).contains("[messenger] bot: Bạn có thể cân nhắc"));
    }

    private static Conversation conversation(UUID tenantId, UUID id, String userExternalId, UUID unifiedCustomerId) {
        Conversation conversation = new Conversation();
        conversation.setId(id);
        conversation.setTenantId(tenantId);
        conversation.setChatbotId(UUID.randomUUID());
        conversation.setUserExternalId(userExternalId);
        conversation.setUnifiedCustomerId(unifiedCustomerId);
        conversation.setStatus("ACTIVE");
        return conversation;
    }

    private static Message message(UUID tenantId, UUID conversationId, String role, String content) {
        Message message = new Message(UUID.randomUUID(), conversationId, role, content);
        message.setTenantId(tenantId);
        return message;
    }
}
