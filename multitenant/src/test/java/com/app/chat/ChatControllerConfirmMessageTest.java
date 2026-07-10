package com.app.chat;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.leads.LeadService;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
import com.app.modelserver.ChatRuntimeService;
import com.app.modelserver.dto.ChatResponse;
import com.app.purchases.PurchaseRequest;
import com.app.purchases.PurchaseRequestService;
import com.app.tenant.TenantContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.eq;

@ExtendWith(MockitoExtension.class)
class ChatControllerConfirmMessageTest {

    @Mock
    private ConversationRepository convRepo;
    @Mock
    private MessageRepository msgRepo;
    @Mock
    private ChatbotInstanceRepository botRepo;
    @Mock
    private ChatRuntimeService chatRuntimeService;
    @Mock
    private PythonChatClient pythonChatClient;
    @Mock
    private LlmInstanceManager llmInstanceManager;
    @Mock
    private LeadService leadService;
    @Mock
    private LeadRepository leadRepo;
    @Mock
    private PurchaseRequestService purchaseRequestService;
    @Mock
    private ConversationResetService conversationResetService;
    @Mock
    private CrossChannelConversationContextService crossChannelConversationContextService;

    @InjectMocks
    private ChatController chatController;

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void confirmSuccessReturnsClearPurchaseRequestMessage() {
        Fixture fixture = Fixture.create();

        mockBaseConversation(fixture);

        Map<String, Object> out = chatController.send(Map.of(
                "conversationId", fixture.conversationId.toString(),
                "message", "CONFIRM",
                "userExternalId", fixture.userExternalId
        ));

        String reply = String.valueOf(out.get("reply"));
        assertTrue(reply.contains("Ma lead"));
        assertEquals(18, out.get("latencyMs"));
        assertEquals("model-a", out.get("model"));
        assertEquals("adapter-a", out.get("adapter"));
        verify(leadService).createFromChatbotHandoff(any(LeadService.ChatbotHandoffLeadData.class));
        verify(purchaseRequestService, never()).findOrCreateFromLead(any());
    }

    @Test
    void confirmBlockedReturnsFriendlyMissingInfoMessage() {
        Fixture fixture = Fixture.create();

        mockBaseConversation(fixture, new ChatResponse("upstream", 18, "model-a", "adapter-a", true, null, null, Map.of("mode", "tenant_sales")), false);
        when(leadService.createFromChatbotHandoff(any(LeadService.ChatbotHandoffLeadData.class)))
                .thenThrow(new IllegalStateException("missing required buyer details"));

        Map<String, Object> out = chatController.send(Map.of(
                "conversationId", fixture.conversationId.toString(),
                "message", "CONFIRM",
                "userExternalId", fixture.userExternalId
        ));

        String reply = String.valueOf(out.get("reply"));
        assertTrue(reply.length() > 20);
        assertTrue(!"upstream".equals(reply));
        assertEquals(18, out.get("latencyMs"));
        assertEquals("model-a", out.get("model"));
        assertEquals("adapter-a", out.get("adapter"));
        verify(leadRepo, never()).save(any());
        verify(purchaseRequestService, never()).findOrCreateFromLead(any());
    }

    @Test
    void tenantWebChatForcesTenantSalesModeEvenIfBotModeIsGeneralCompare() {
        Fixture fixture = Fixture.create();
        fixture.bot.setMode("general_compare");
        ChatResponse upstreamResponse = new ChatResponse(
                "upstream",
                18,
                "model-a",
                "adapter-a",
                true,
                null,
                null,
                Map.of("mode", "tenant_sales")
        );

        mockBaseConversation(fixture, upstreamResponse, true);

        Map<String, Object> out = chatController.send(Map.of(
                "conversationId", fixture.conversationId.toString(),
                "message", "CONFIRM",
                "userExternalId", fixture.userExternalId
        ));

        assertTrue(String.valueOf(out.get("reply")).contains("Ma lead"));
        assertEquals(18, out.get("latencyMs"));
        verify(leadService).createFromChatbotHandoff(any(LeadService.ChatbotHandoffLeadData.class));
        verify(purchaseRequestService, never()).findOrCreateFromLead(any());
    }

    @Test
    void resetCommandResetsCurrentConversationWithoutCallingPythonOrSavingMessage() {
        Fixture fixture = Fixture.create();
        TenantContext.set(fixture.tenantId.toString());
        when(convRepo.findById(fixture.conversationId)).thenReturn(Optional.of(fixture.conversation));

        Map<String, Object> out = chatController.send(Map.of(
                "conversationId", fixture.conversationId.toString(),
                "message", " /reset ",
                "userExternalId", fixture.userExternalId
        ));

        assertEquals("Xong.", out.get("reply"));
        assertEquals(0, out.get("latencyMs"));
        assertEquals("system", out.get("model"));
        verify(conversationResetService).reset(
                org.mockito.ArgumentMatchers.eq(fixture.tenantId),
                argThat(request -> request.conversationId().equals(fixture.conversationId.toString())
                        && request.shouldDeleteMessages()
                        && request.shouldResetBusinessFlags())
        );
        verify(msgRepo, never()).save(any());
        verify(pythonChatClient, never()).chat(anyString(), anyString(), any(), any(), anyString(), anyString(), anyString(), org.mockito.ArgumentMatchers.anyBoolean(), org.mockito.ArgumentMatchers.anyBoolean());
    }

    @Test
    void resetTestCommandResetsBusinessFlagsWithoutCallingPythonOrSavingMessage() {
        Fixture fixture = Fixture.create();
        TenantContext.set(fixture.tenantId.toString());
        when(convRepo.findById(fixture.conversationId)).thenReturn(Optional.of(fixture.conversation));

        Map<String, Object> out = chatController.send(Map.of(
                "conversationId", fixture.conversationId.toString(),
                "message", "/reset-test",
                "userExternalId", fixture.userExternalId
        ));

        assertEquals("Xong.", out.get("reply"));
        assertEquals(0, out.get("latencyMs"));
        assertEquals("system", out.get("model"));
        verify(conversationResetService).reset(
                org.mockito.ArgumentMatchers.eq(fixture.tenantId),
                argThat(request -> request.conversationId().equals(fixture.conversationId.toString())
                        && request.shouldDeleteMessages()
                        && request.shouldResetBusinessFlags())
        );
        verify(msgRepo, never()).save(any());
        verify(pythonChatClient, never()).chat(anyString(), anyString(), any(), any(), anyString(), anyString(), anyString(), org.mockito.ArgumentMatchers.anyBoolean(), org.mockito.ArgumentMatchers.anyBoolean());
        verify(purchaseRequestService, never()).findOrCreateFromLead(any());
    }

    @Test
    void newCommandCreatesFreshConversationWithoutCallingPythonOrSavingMessage() {
        Fixture fixture = Fixture.create();
        TenantContext.set(fixture.tenantId.toString());
        UUID newConversationId = UUID.randomUUID();
        when(convRepo.findById(fixture.conversationId)).thenReturn(Optional.of(fixture.conversation));
        when(conversationResetService.startNewConsultationSession(
                fixture.tenantId,
                fixture.chatbotId,
                "web",
                fixture.userExternalId,
                fixture.conversationId,
                null
        )).thenReturn(new NewConsultationSessionResponse(fixture.tenantId.toString(), newConversationId.toString(), 1, 2, 1, 0, 0));

        Map<String, Object> out = chatController.send(Map.of(
                "conversationId", fixture.conversationId.toString(),
                "message", "/new",
                "userExternalId", fixture.userExternalId
        ));

        assertEquals("Xong.", out.get("reply"));
        assertEquals(newConversationId.toString(), out.get("newConversationId"));
        verify(msgRepo, never()).save(any());
        verify(pythonChatClient, never()).chat(anyString(), anyString(), any(), any(), anyString(), anyString(), anyString(), org.mockito.ArgumentMatchers.anyBoolean(), org.mockito.ArgumentMatchers.anyBoolean());
    }

    @Test
    void resetAllCommandAliasesNewConversationFlow() {
        Fixture fixture = Fixture.create();
        TenantContext.set(fixture.tenantId.toString());
        UUID newConversationId = UUID.randomUUID();
        when(convRepo.findById(fixture.conversationId)).thenReturn(Optional.of(fixture.conversation));
        when(conversationResetService.startNewConsultationSession(
                fixture.tenantId,
                fixture.chatbotId,
                "web",
                fixture.userExternalId,
                fixture.conversationId,
                null
        )).thenReturn(new NewConsultationSessionResponse(fixture.tenantId.toString(), newConversationId.toString(), 1, 2, 1, 0, 0));

        Map<String, Object> out = chatController.send(Map.of(
                "conversationId", fixture.conversationId.toString(),
                "message", "/reset-all",
                "userExternalId", fixture.userExternalId
        ));

        assertEquals("Xong.", out.get("reply"));
        assertEquals(newConversationId.toString(), out.get("newConversationId"));
        verify(msgRepo, never()).save(any());
        verify(pythonChatClient, never()).chat(anyString(), anyString(), any(), any(), anyString(), anyString(), anyString(), org.mockito.ArgumentMatchers.anyBoolean(), org.mockito.ArgumentMatchers.anyBoolean());
    }

    private void mockBaseConversation(Fixture fixture) {
        mockBaseConversation(
                fixture,
                new ChatResponse("upstream", 18, "model-a", "adapter-a", true, null, null, Map.of("mode", "tenant_sales")),
                true
        );
    }

    private void mockBaseConversation(Fixture fixture, ChatResponse upstreamResponse, boolean stubLeadCapture) {
        TenantContext.set(fixture.tenantId.toString());

        when(convRepo.findById(fixture.conversationId)).thenReturn(Optional.of(fixture.conversation));
        when(botRepo.findById(fixture.chatbotId)).thenReturn(Optional.of(fixture.bot));
        when(msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(fixture.conversationId))
                .thenReturn(List.of(new Message(UUID.randomUUID(), fixture.conversationId, "user", "CONFIRM")));
        when(chatRuntimeService.chat(
                eq(fixture.tenantId),
                eq(fixture.bot),
                eq("CONFIRM"),
                any(List.class),
                eq(fixture.conversationId.toString()),
                eq("web"),
                eq("tenant_sales")
        )).thenReturn(new ChatRuntimeService.Result(upstreamResponse, "http://127.0.0.1:8101", "external"));

        if (stubLeadCapture) {
            lenient().when(leadService.createFromChatbotHandoff(any(LeadService.ChatbotHandoffLeadData.class)))
                    .thenReturn(fixture.lead);
        }
    }

    private static final class Fixture {
        private final UUID tenantId;
        private final UUID conversationId;
        private final UUID chatbotId;
        private final String userExternalId;
        private final Conversation conversation;
        private final ChatbotInstance bot;
        private final Lead lead;

        private Fixture(UUID tenantId, UUID conversationId, UUID chatbotId, String userExternalId, Conversation conversation, ChatbotInstance bot, Lead lead) {
            this.tenantId = tenantId;
            this.conversationId = conversationId;
            this.chatbotId = chatbotId;
            this.userExternalId = userExternalId;
            this.conversation = conversation;
            this.bot = bot;
            this.lead = lead;
        }

        private static Fixture create() {
            UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
            UUID conversationId = UUID.randomUUID();
            UUID chatbotId = UUID.randomUUID();
            String userExternalId = "guest:test-user";

            Conversation conversation = new Conversation();
            conversation.setId(conversationId);
            conversation.setTenantId(tenantId);
            conversation.setChatbotId(chatbotId);
            conversation.setUserExternalId(userExternalId);

            ChatbotInstance bot = new ChatbotInstance();
            bot.setId(chatbotId);
            bot.setMode("tenant_sales");

            Lead lead = Lead.createNew(tenantId.toString(), "web", conversationId.toString(), "", "{}", "");
            return new Fixture(tenantId, conversationId, chatbotId, userExternalId, conversation, bot, lead);
        }
    }
}
