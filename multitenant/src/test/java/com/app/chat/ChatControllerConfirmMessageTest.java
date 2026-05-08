package com.app.chat;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.leads.Lead;
import com.app.leads.LeadService;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
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
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ChatControllerConfirmMessageTest {

    @Mock
    private ConversationRepository convRepo;
    @Mock
    private MessageRepository msgRepo;
    @Mock
    private ChatbotInstanceRepository botRepo;
    @Mock
    private PythonChatClient pythonChatClient;
    @Mock
    private LlmInstanceManager llmInstanceManager;
    @Mock
    private LeadService leadService;
    @Mock
    private PurchaseRequestService purchaseRequestService;

    @InjectMocks
    private ChatController chatController;

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void confirmSuccessReturnsClearPurchaseRequestMessage() {
        Fixture fixture = Fixture.create();
        PurchaseRequest purchaseRequest = new PurchaseRequest();
        purchaseRequest.setCustomerName("Nguyen Van A");
        purchaseRequest.setPhone("0912345678");
        purchaseRequest.setShippingAddress("123 Nguyen Trai, Ha Noi");

        mockBaseConversation(fixture);
        when(purchaseRequestService.findOrCreateFromLead(fixture.lead)).thenReturn(purchaseRequest);

        Map<String, Object> out = chatController.send(Map.of(
                "conversationId", fixture.conversationId.toString(),
                "message", "CONFIRM"
        ));

        assertEquals(
                "Cáº£m Æ¡n Nguyen Van A. MÃ¬nh Ä‘Ã£ táº¡o yÃªu cáº§u mua hÃ ng cho báº¡n.\nThÃ´ng tin mÃ¬nh Ä‘Ã£ ghi nháº­n:\n- há» tÃªn: Nguyen Van A\n- sá»‘ Ä‘iá»‡n thoáº¡i: 0912345678\n- Ä‘á»‹a chá»‰ nháº­n hÃ ng: 123 Nguyen Trai, Ha Noi\nNhÃ¢n viÃªn bÃªn mÃ¬nh sáº½ sá»›m liÃªn há»‡ Ä‘á»ƒ xÃ¡c nháº­n láº¡i thÃ´ng tin vÃ  hoÃ n táº¥t Ä‘Æ¡n hÃ ng.",
                out.get("reply")
        );
        assertEquals(18, out.get("latencyMs"));
        assertEquals("model-a", out.get("model"));
        assertEquals("adapter-a", out.get("adapter"));
    }

    @Test
    void confirmBlockedReturnsFriendlyMissingInfoMessage() {
        Fixture fixture = Fixture.create();

        mockBaseConversation(fixture);
        when(purchaseRequestService.findOrCreateFromLead(fixture.lead))
                .thenThrow(new IllegalStateException("missing required buyer details"));

        Map<String, Object> out = chatController.send(Map.of(
                "conversationId", fixture.conversationId.toString(),
                "message", "CONFIRM"
        ));

        assertEquals(
                "MÃ¬nh cÃ³ thá»ƒ táº¡o yÃªu cáº§u mua hÃ ng cho báº¡n, nhÆ°ng trÆ°á»›c khi xÃ¡c nháº­n báº¡n vui lÃ²ng gá»­i Ä‘áº§y Ä‘á»§ há» tÃªn, sá»‘ Ä‘iá»‡n thoáº¡i vÃ  Ä‘á»‹a chá»‰ nháº­n hÃ ng trong Ä‘oáº¡n chat nÃ y nhÃ©.",
                out.get("reply")
        );
        assertEquals(18, out.get("latencyMs"));
        assertEquals("model-a", out.get("model"));
        assertEquals("adapter-a", out.get("adapter"));
    }

    private void mockBaseConversation(Fixture fixture) {
        TenantContext.set(fixture.tenantId.toString());

        when(convRepo.findById(fixture.conversationId)).thenReturn(Optional.of(fixture.conversation));
        when(botRepo.findById(fixture.chatbotId)).thenReturn(Optional.of(fixture.bot));
        when(msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(fixture.conversationId))
                .thenReturn(List.of(new Message(UUID.randomUUID(), fixture.conversationId, "user", "CONFIRM")));
        when(llmInstanceManager.getOrStartSession(fixture.tenantId, fixture.bot))
                .thenReturn(new LlmInstanceManager.Session("http://127.0.0.1:8101", false, false));
        when(pythonChatClient.chat(
                "http://127.0.0.1:8101",
                "CONFIRM",
                List.of("CONFIRM"),
                fixture.bot,
                fixture.conversationId.toString(),
                "web",
                fixture.tenantId.toString(),
                false,
                false
        )).thenReturn(new ChatResponse("upstream", 18, "model-a", "adapter-a"));
        when(leadService.createLeadFromConversation(
                "http://127.0.0.1:8101",
                fixture.tenantId.toString(),
                "web",
                fixture.conversationId.toString(),
                ""
        )).thenReturn(fixture.lead);
    }

    private static final class Fixture {
        private final UUID tenantId;
        private final UUID conversationId;
        private final UUID chatbotId;
        private final Conversation conversation;
        private final ChatbotInstance bot;
        private final Lead lead;

        private Fixture(UUID tenantId, UUID conversationId, UUID chatbotId, Conversation conversation, ChatbotInstance bot, Lead lead) {
            this.tenantId = tenantId;
            this.conversationId = conversationId;
            this.chatbotId = chatbotId;
            this.conversation = conversation;
            this.bot = bot;
            this.lead = lead;
        }

        private static Fixture create() {
            UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
            UUID conversationId = UUID.randomUUID();
            UUID chatbotId = UUID.randomUUID();

            Conversation conversation = new Conversation();
            conversation.setId(conversationId);
            conversation.setTenantId(tenantId);
            conversation.setChatbotId(chatbotId);

            ChatbotInstance bot = new ChatbotInstance();
            bot.setId(chatbotId);

            Lead lead = Lead.createNew(tenantId.toString(), "web", conversationId.toString(), "", "{}", "");
            return new Fixture(tenantId, conversationId, chatbotId, conversation, bot, lead);
        }
    }
}
