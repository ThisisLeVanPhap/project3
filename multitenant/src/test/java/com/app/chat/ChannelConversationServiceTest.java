package com.app.chat;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ChannelConversationServiceTest {

    @Mock
    private ConversationRepository conversationRepository;

    @InjectMocks
    private ChannelConversationService channelConversationService;

    @Test
    void sameSenderSameTenantAndChatbotReusesConversation() {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        Conversation existing = conversation(tenantId, chatbotId);
        String senderKey = channelConversationService.buildMessengerSenderKey("page-1", "sender-1");

        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "messenger:page:page-1:sender:sender-1",
                "ACTIVE"
        )).thenReturn(Optional.of(existing));

        Conversation resolved = channelConversationService.findOrCreateActiveConversation(
                tenantId,
                chatbotId,
                "messenger",
                senderKey
        );

        assertEquals(existing.getId(), resolved.getId());
    }

    @Test
    void sameSenderDifferentTenantGetsDifferentConversation() {
        UUID tenantA = UUID.randomUUID();
        UUID tenantB = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        String senderKey = channelConversationService.buildMessengerSenderKey("page-1", "sender-1");
        Conversation existingTenantA = conversation(tenantA, chatbotId);
        Conversation createdTenantB = conversation(tenantB, chatbotId);

        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                eq(tenantA),
                eq(chatbotId),
                eq("messenger:page:page-1:sender:sender-1"),
                eq("ACTIVE")
        )).thenReturn(Optional.of(existingTenantA));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                eq(tenantB),
                eq(chatbotId),
                eq("messenger:page:page-1:sender:sender-1"),
                eq("ACTIVE")
        )).thenReturn(Optional.empty());
        when(conversationRepository.findByTenantIdAndChatbotIdAndUserExternalIdStartingWithAndStatusOrderByCreatedAtDesc(
                tenantB,
                chatbotId,
                "messenger:page:page-1:sender:sender-1#demo:",
                "ACTIVE"
        )).thenReturn(List.of());
        when(conversationRepository.save(any(Conversation.class))).thenReturn(createdTenantB);

        Conversation resolvedA = channelConversationService.findOrCreateActiveConversation(
                tenantA,
                chatbotId,
                "messenger",
                senderKey
        );
        Conversation resolvedB = channelConversationService.findOrCreateActiveConversation(
                tenantB,
                chatbotId,
                "messenger",
                senderKey
        );

        assertEquals(existingTenantA.getId(), resolvedA.getId());
        assertNotEquals(resolvedA.getId(), resolvedB.getId());
        assertEquals(tenantB, resolvedB.getTenantId());
    }

    @Test
    void sameSenderDifferentChatbotCreatesDifferentConversation() {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotA = UUID.randomUUID();
        UUID chatbotB = UUID.randomUUID();
        String senderKey = channelConversationService.buildMessengerSenderKey("page-1", "sender-1");
        Conversation existingBotA = conversation(tenantId, chatbotA);
        Conversation createdBotB = conversation(tenantId, chatbotB);

        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotA,
                "messenger:page:page-1:sender:sender-1",
                "ACTIVE"
        )).thenReturn(Optional.of(existingBotA));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotB,
                "messenger:page:page-1:sender:sender-1",
                "ACTIVE"
        )).thenReturn(Optional.empty());
        when(conversationRepository.findByTenantIdAndChatbotIdAndUserExternalIdStartingWithAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotB,
                "messenger:page:page-1:sender:sender-1#demo:",
                "ACTIVE"
        )).thenReturn(List.of());
        when(conversationRepository.save(any(Conversation.class))).thenReturn(createdBotB);

        Conversation resolvedA = channelConversationService.findOrCreateActiveConversation(tenantId, chatbotA, "messenger", senderKey);
        Conversation resolvedB = channelConversationService.findOrCreateActiveConversation(tenantId, chatbotB, "messenger", senderKey);

        assertEquals(existingBotA.getId(), resolvedA.getId());
        assertEquals(chatbotB, resolvedB.getChatbotId());
        assertNotEquals(resolvedA.getId(), resolvedB.getId());
    }

    @Test
    void newSenderCreatesNewConversation() {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        String senderKey = channelConversationService.buildMessengerSenderKey("page-1", "sender-2");
        ArgumentCaptor<Conversation> savedConversation = ArgumentCaptor.forClass(Conversation.class);

        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "messenger:page:page-1:sender:sender-2",
                "ACTIVE"
        )).thenReturn(Optional.empty());
        when(conversationRepository.findByTenantIdAndChatbotIdAndUserExternalIdStartingWithAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "messenger:page:page-1:sender:sender-2#demo:",
                "ACTIVE"
        )).thenReturn(List.of());
        when(conversationRepository.save(savedConversation.capture()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        Conversation resolved = channelConversationService.findOrCreateActiveConversation(
                tenantId,
                chatbotId,
                "messenger",
                senderKey
        );

        assertEquals(chatbotId, resolved.getChatbotId());
        assertEquals(tenantId, resolved.getTenantId());
        assertEquals("messenger:page:page-1:sender:sender-2", resolved.getUserExternalId());
        assertEquals(resolved.getId(), savedConversation.getValue().getId());
    }

    @Test
    void activeDemoConversationTakesPriorityWhenBaseConversationIsClosed() {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        String senderKey = channelConversationService.buildMessengerSenderKey("page-1", "sender-3");
        Conversation demoConversation = conversation(tenantId, chatbotId);
        demoConversation.setUserExternalId("messenger:page:page-1:sender:sender-3#demo:abc");

        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "messenger:page:page-1:sender:sender-3",
                "ACTIVE"
        )).thenReturn(Optional.empty());
        when(conversationRepository.findByTenantIdAndChatbotIdAndUserExternalIdStartingWithAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "messenger:page:page-1:sender:sender-3#demo:",
                "ACTIVE"
        )).thenReturn(List.of(demoConversation));

        Conversation resolved = channelConversationService.findOrCreateActiveConversation(
                tenantId,
                chatbotId,
                "messenger",
                senderKey
        );

        assertEquals(demoConversation.getId(), resolved.getId());
    }

    @Test
    void secondMessageContinuesSameConversationId() {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        Conversation existing = conversation(tenantId, chatbotId);
        String senderKey = channelConversationService.buildMessengerSenderKey("page-9", "sender-9");

        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "messenger:page:page-9:sender:sender-9",
                "ACTIVE"
        )).thenReturn(Optional.of(existing));

        Conversation first = channelConversationService.findOrCreateActiveConversation(
                tenantId,
                chatbotId,
                "messenger",
                senderKey
        );
        Conversation second = channelConversationService.findOrCreateActiveConversation(
                tenantId,
                chatbotId,
                "messenger",
                senderKey
        );

        assertEquals(first.getId(), second.getId());
        verify(conversationRepository, times(2)).findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "messenger:page:page-9:sender:sender-9",
                "ACTIVE"
        );
    }

    private static Conversation conversation(UUID tenantId, UUID chatbotId) {
        Conversation conversation = new Conversation();
        conversation.setId(UUID.randomUUID());
        conversation.setTenantId(tenantId);
        conversation.setChatbotId(chatbotId);
        conversation.setStatus("ACTIVE");
        return conversation;
    }
}
