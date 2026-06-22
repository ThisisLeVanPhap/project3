package com.app.chat;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.customers.CustomerIdentityService;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
import com.app.purchases.PurchaseRequest;
import com.app.purchases.PurchaseRequestRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.times;

@ExtendWith(MockitoExtension.class)
class ConversationResetServiceTest {

    @Mock
    private ConversationRepository conversationRepository;

    @Mock
    private MessageRepository messageRepository;

    @Mock
    private CustomerIdentityService customerIdentityService;

    @Mock
    private ChatbotInstanceRepository chatbotInstanceRepository;

    @Mock
    private LlmInstanceManager llmInstanceManager;

    @Mock
    private PythonChatClient pythonChatClient;

    @Mock
    private LeadRepository leadRepository;

    @Mock
    private PurchaseRequestRepository purchaseRequestRepository;

    @Test
    void resetsConversationForSelectedTenantAndDeletesMessages() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        Conversation conversation = conversation(tenantId, conversationId, "CLOSED");

        when(conversationRepository.findById(conversationId)).thenReturn(Optional.of(conversation));
        when(messageRepository.countByTenantIdAndConversationId(tenantId, conversationId)).thenReturn(3L);

        ConversationResetService service = service();
        ConversationResetResponse response = service.reset(
                tenantId,
                new ConversationResetRequest(conversationId.toString(), null, null, null, true, false)
        );

        assertEquals(true, response.success());
        assertEquals(tenantId.toString(), response.tenantId());
        assertEquals(conversationId.toString(), response.conversationId());
        assertEquals(3L, response.messagesDeleted());
        assertFalse(response.runtimeCacheCleared());
        assertEquals(0L, response.leadsDeleted());
        assertEquals(0L, response.purchaseRequestsDeleted());
        assertEquals("ACTIVE", conversation.getStatus());
        verify(messageRepository).deleteByTenantIdAndConversationId(tenantId, conversationId);
        verify(conversationRepository).save(conversation);
    }

    @Test
    void tenantCannotResetConversationFromAnotherTenant() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID otherTenantId = UUID.fromString("6c1970e2-827d-40e8-b421-3971fc3d00d5");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        when(conversationRepository.findById(conversationId)).thenReturn(Optional.of(conversation(otherTenantId, conversationId, "ACTIVE")));

        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () ->
                service().reset(tenantId, new ConversationResetRequest(conversationId.toString(), null, null, null, true, false)));

        assertEquals(403, ex.getStatusCode().value());
        verify(messageRepository, never()).deleteByTenantIdAndConversationId(tenantId, conversationId);
    }

    @Test
    void missingConversationReturnsNotFound() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        when(conversationRepository.findById(conversationId)).thenReturn(Optional.empty());

        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () ->
                service().reset(tenantId, new ConversationResetRequest(conversationId.toString(), null, null, null, true, false)));

        assertEquals(404, ex.getStatusCode().value());
    }

    @Test
    void canResolveMessengerConversationByExternalUserKeyAndChatbot() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.fromString("573ad2de-68a9-449a-bb85-7ce029b22fe6");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        String userKey = "messenger:page:page-1:sender:psid-1";
        Conversation conversation = conversation(tenantId, conversationId, "ACTIVE");
        conversation.setChatbotId(chatbotId);
        conversation.setUserExternalId(userKey);

        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                userKey,
                "ACTIVE"
        )).thenReturn(Optional.of(conversation));
        when(messageRepository.countByTenantIdAndConversationId(tenantId, conversationId)).thenReturn(2L);

        ConversationResetResponse response = service().reset(
                tenantId,
                new ConversationResetRequest(null, "messenger", "page:page-1:sender:psid-1", chatbotId.toString(), true, false)
        );

        assertEquals(conversationId.toString(), response.conversationId());
        assertEquals(2L, response.messagesDeleted());
        verify(messageRepository).deleteByTenantIdAndConversationId(tenantId, conversationId);
    }

    @Test
    void canResetWithoutDeletingMessages() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        Conversation conversation = conversation(tenantId, conversationId, "CLOSED");
        when(conversationRepository.findById(conversationId)).thenReturn(Optional.of(conversation));

        ConversationResetResponse response = service().reset(
                tenantId,
                new ConversationResetRequest(conversationId.toString(), null, null, null, false, false)
        );

        assertEquals(0L, response.messagesDeleted());
        assertEquals(0L, response.leadsDeleted());
        assertEquals(0L, response.purchaseRequestsDeleted());
        verify(messageRepository, never()).deleteByTenantIdAndConversationId(tenantId, conversationId);
    }

    @Test
    void defaultResetPreservesUnifiedCustomerAndLeadCreatedGuard() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        UUID unifiedCustomerId = UUID.fromString("ad6339f1-05f2-4a27-99bb-13fd750f1b9f");
        Conversation conversation = conversation(tenantId, conversationId, "ACTIVE");
        conversation.setUnifiedCustomerId(unifiedCustomerId);
        conversation.setLeadCreated(true);
        when(conversationRepository.findById(conversationId)).thenReturn(Optional.of(conversation));

        ConversationResetResponse response = service().reset(
                tenantId,
                new ConversationResetRequest(conversationId.toString(), null, null, null, true, false)
        );

        assertEquals(unifiedCustomerId, conversation.getUnifiedCustomerId());
        assertEquals(true, conversation.isLeadCreated());
        assertEquals(0L, response.leadsDeleted());
        assertEquals(0L, response.purchaseRequestsDeleted());
    }

    @Test
    void resetBusinessFlagsAllowsTestingPurchaseFlowAgainWithoutDeletingOldRecords() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        Conversation conversation = conversation(tenantId, conversationId, "ACTIVE");
        conversation.setLeadCreated(true);
        when(conversationRepository.findById(conversationId)).thenReturn(Optional.of(conversation));

        ConversationResetResponse response = service().reset(
                tenantId,
                new ConversationResetRequest(conversationId.toString(), null, null, null, true, true)
        );

        assertFalse(conversation.isLeadCreated());
        assertEquals(0L, response.leadsDeleted());
        assertEquals(0L, response.purchaseRequestsDeleted());
    }

    @Test
    void resetBusinessFlagsDiscardsOnlyInProgressLeadsForCurrentConversation() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        Conversation conversation = conversation(tenantId, conversationId, "ACTIVE");
        Lead pending = Lead.createNew(tenantId.toString(), "web", conversationId.toString(), "guest", "{}", "");
        Lead contacted = Lead.createNew(tenantId.toString(), "web", conversationId.toString(), "guest", "{}", "");
        contacted.setStatus("CONTACTED");
        Lead fulfilled = Lead.createNew(tenantId.toString(), "web", conversationId.toString(), "guest", "{}", "");
        fulfilled.setStatus("CONTACTED");
        fulfilled.setStage("FULFILLED");
        Lead shipped = Lead.createNew(tenantId.toString(), "web", conversationId.toString(), "guest", "{}", "");
        shipped.setShippingStatus("SHIPPED");
        when(conversationRepository.findById(conversationId)).thenReturn(Optional.of(conversation));
        when(leadRepository.findByTenantIdAndConversationId(tenantId.toString(), conversationId.toString()))
                .thenReturn(List.of(pending, contacted, fulfilled, shipped));

        service().reset(
                tenantId,
                new ConversationResetRequest(conversationId.toString(), null, null, null, true, true)
        );

        assertEquals("CLOSED", pending.getStatus());
        assertEquals("DISCOVER", pending.getStage());
        assertEquals("CLOSED", contacted.getStatus());
        assertEquals("DISCOVER", contacted.getStage());
        assertEquals("CONTACTED", fulfilled.getStatus());
        assertEquals("FULFILLED", fulfilled.getStage());
        assertEquals("NEW", shipped.getStatus());
        assertEquals("SHIPPED", shipped.getShippingStatus());
        verify(leadRepository).save(pending);
        verify(leadRepository).save(contacted);
        verify(leadRepository, never()).save(fulfilled);
        verify(leadRepository, never()).save(shipped);
    }

    @Test
    void resetBusinessFlagsDiscardsOnlyInProgressPurchaseRequestsForCurrentConversation() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        Conversation conversation = conversation(tenantId, conversationId, "ACTIVE");
        PurchaseRequest newRequest = purchaseRequest(tenantId, conversationId, "NEW");
        PurchaseRequest contactedRequest = purchaseRequest(tenantId, conversationId, "CONTACTED");
        PurchaseRequest completedRequest = purchaseRequest(tenantId, conversationId, "COMPLETED");
        when(conversationRepository.findById(conversationId)).thenReturn(Optional.of(conversation));
        when(purchaseRequestRepository.findByTenantIdAndConversationId(tenantId.toString(), conversationId.toString()))
                .thenReturn(List.of(newRequest, contactedRequest, completedRequest));

        service().reset(
                tenantId,
                new ConversationResetRequest(conversationId.toString(), null, null, null, true, true)
        );

        assertEquals("RESET_DISCARDED", newRequest.getStatus());
        assertEquals("RESET_DISCARDED", contactedRequest.getStatus());
        assertEquals("COMPLETED", completedRequest.getStatus());
        verify(purchaseRequestRepository).save(newRequest);
        verify(purchaseRequestRepository).save(contactedRequest);
        verify(purchaseRequestRepository, never()).save(completedRequest);
    }

    @Test
    void runtimeResetSuccessSetsRuntimeCacheCleared() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        Conversation conversation = conversation(tenantId, conversationId, "ACTIVE");
        ChatbotInstance bot = chatbot(tenantId, conversation.getChatbotId());
        when(conversationRepository.findById(conversationId)).thenReturn(Optional.of(conversation));
        when(chatbotInstanceRepository.findById(conversation.getChatbotId())).thenReturn(Optional.of(bot));
        when(llmInstanceManager.getOrStartSession(tenantId, bot))
                .thenReturn(new LlmInstanceManager.Session("http://python.test", false, false));

        ConversationResetResponse response = service().reset(
                tenantId,
                new ConversationResetRequest(conversationId.toString(), null, null, null, true, false)
        );

        assertEquals(true, response.runtimeCacheCleared());
        verify(pythonChatClient).resetState("http://python.test", tenantId.toString(), conversationId.toString());
    }

    @Test
    void runtimeResetFailureKeepsDatabaseResetSuccessful() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        Conversation conversation = conversation(tenantId, conversationId, "CLOSED");
        ChatbotInstance bot = chatbot(tenantId, conversation.getChatbotId());
        when(conversationRepository.findById(conversationId)).thenReturn(Optional.of(conversation));
        when(chatbotInstanceRepository.findById(conversation.getChatbotId())).thenReturn(Optional.of(bot));
        when(llmInstanceManager.getOrStartSession(tenantId, bot))
                .thenReturn(new LlmInstanceManager.Session("http://python.test", false, false));
        doThrow(new RuntimeException("runtime down"))
                .when(pythonChatClient).resetState("http://python.test", tenantId.toString(), conversationId.toString());

        ConversationResetResponse response = service().reset(
                tenantId,
                new ConversationResetRequest(conversationId.toString(), null, null, null, true, false)
        );

        assertFalse(response.runtimeCacheCleared());
        assertEquals("ACTIVE", conversation.getStatus());
        verify(conversationRepository).save(conversation);
    }

    @Test
    void newConsultationClosesMatchingActiveConversationsAndCreatesCleanConversation() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.fromString("573ad2de-68a9-449a-bb85-7ce029b22fe6");
        UUID unifiedCustomerId = UUID.fromString("ad6339f1-05f2-4a27-99bb-13fd750f1b9f");
        String userKey = "messenger:page:page-1:sender:psid-1";
        Conversation older = conversation(tenantId, UUID.randomUUID(), "ACTIVE");
        older.setChatbotId(chatbotId);
        older.setUserExternalId(userKey);
        older.setUnifiedCustomerId(unifiedCustomerId);
        older.setLeadCreated(true);
        Conversation latest = conversation(tenantId, UUID.randomUUID(), "ACTIVE");
        latest.setChatbotId(chatbotId);
        latest.setUserExternalId(userKey);
        latest.setLeadCreated(true);
        ChatbotInstance bot = chatbot(tenantId, chatbotId);
        Lead pendingLead = Lead.createNew(tenantId.toString(), "messenger", older.getId().toString(), "guest", "{}", "");
        pendingLead.setStatus("NEW");
        Lead fulfilledLead = Lead.createNew(tenantId.toString(), "messenger", older.getId().toString(), "guest", "{}", "");
        fulfilledLead.setStatus("CONTACTED");
        fulfilledLead.setStage("FULFILLED");
        PurchaseRequest newRequest = purchaseRequest(tenantId, latest.getId(), "NEW");
        PurchaseRequest completedRequest = purchaseRequest(tenantId, latest.getId(), "COMPLETED");

        when(conversationRepository.findByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                userKey,
                "ACTIVE"
        )).thenReturn(List.of(latest, older));
        when(messageRepository.countByTenantIdAndConversationId(tenantId, latest.getId())).thenReturn(2L);
        when(messageRepository.countByTenantIdAndConversationId(tenantId, older.getId())).thenReturn(3L);
        when(chatbotInstanceRepository.findById(chatbotId)).thenReturn(Optional.of(bot));
        when(llmInstanceManager.getOrStartSession(tenantId, bot))
                .thenReturn(new LlmInstanceManager.Session("http://python.test", false, false));
        org.mockito.Mockito.doNothing()
                .when(pythonChatClient).resetState("http://python.test", tenantId.toString(), latest.getId().toString());
        doThrow(new RuntimeException("runtime down"))
                .when(pythonChatClient).resetState("http://python.test", tenantId.toString(), older.getId().toString());
        when(leadRepository.findByTenantIdAndConversationId(tenantId.toString(), older.getId().toString()))
                .thenReturn(List.of(pendingLead, fulfilledLead));
        when(leadRepository.findByTenantIdAndConversationId(tenantId.toString(), latest.getId().toString()))
                .thenReturn(List.of());
        when(purchaseRequestRepository.findByTenantIdAndConversationId(tenantId.toString(), latest.getId().toString()))
                .thenReturn(List.of(newRequest, completedRequest));
        when(purchaseRequestRepository.findByTenantIdAndConversationId(tenantId.toString(), older.getId().toString()))
                .thenReturn(List.of());
        when(conversationRepository.save(any(Conversation.class))).thenAnswer(invocation -> invocation.getArgument(0));

        NewConsultationSessionResponse response = service().startNewConsultationSession(
                tenantId,
                chatbotId,
                "messenger",
                "page:page-1:sender:psid-1",
                latest.getId(),
                null
        );

        assertEquals(2L, response.closedConversationCount());
        assertEquals(5L, response.deletedMessageCount());
        assertEquals(1L, response.runtimeResetCount());
        assertEquals(1L, response.discardedLeadCount());
        assertEquals(1L, response.discardedPurchaseRequestCount());
        assertEquals("CLOSED", older.getStatus());
        assertEquals("CLOSED", latest.getStatus());
        assertFalse(older.isLeadCreated());
        assertFalse(latest.isLeadCreated());
        assertEquals("CLOSED", pendingLead.getStatus());
        assertEquals("FULFILLED", fulfilledLead.getStage());
        assertEquals("RESET_DISCARDED", newRequest.getStatus());
        assertEquals("COMPLETED", completedRequest.getStatus());
        verify(messageRepository).deleteByTenantIdAndConversationId(tenantId, older.getId());
        verify(messageRepository).deleteByTenantIdAndConversationId(tenantId, latest.getId());
        verify(pythonChatClient).resetState("http://python.test", tenantId.toString(), latest.getId().toString());
        ArgumentCaptor<Conversation> savedConversation = ArgumentCaptor.forClass(Conversation.class);
        verify(conversationRepository, times(3)).save(savedConversation.capture());
        Conversation fresh = savedConversation.getAllValues().get(2);
        assertEquals("ACTIVE", fresh.getStatus());
        assertEquals(chatbotId, fresh.getChatbotId());
        assertEquals(userKey, fresh.getUserExternalId());
        assertEquals(unifiedCustomerId, fresh.getUnifiedCustomerId());
        assertFalse(fresh.isLeadCreated());
        assertEquals(fresh.getId().toString(), response.newConversationId());
    }

    private ConversationResetService service() {
        return new ConversationResetService(
                conversationRepository,
                messageRepository,
                new ChannelConversationService(conversationRepository, customerIdentityService),
                chatbotInstanceRepository,
                llmInstanceManager,
                pythonChatClient,
                leadRepository,
                purchaseRequestRepository
        );
    }

    private ChatbotInstance chatbot(UUID tenantId, UUID chatbotId) {
        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(chatbotId);
        bot.setTenantId(tenantId);
        return bot;
    }

    private PurchaseRequest purchaseRequest(UUID tenantId, UUID conversationId, String status) {
        PurchaseRequest purchaseRequest = new PurchaseRequest();
        purchaseRequest.setTenantId(tenantId.toString());
        purchaseRequest.setChannel("web");
        purchaseRequest.setConversationId(conversationId.toString());
        purchaseRequest.setStatus(status);
        return purchaseRequest;
    }

    private Conversation conversation(UUID tenantId, UUID conversationId, String status) {
        Conversation conversation = new Conversation();
        conversation.setId(conversationId);
        conversation.setTenantId(tenantId);
        conversation.setChatbotId(UUID.randomUUID());
        conversation.setUserExternalId("messenger:page:page-1:sender:psid-1");
        conversation.setStatus(status);
        return conversation;
    }
}
