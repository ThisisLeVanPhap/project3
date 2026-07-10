package com.app.messenger;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.chat.ChannelConversationService;
import com.app.chat.Conversation;
import com.app.chat.ConversationRepository;
import com.app.chat.ConversationResetService;
import com.app.chat.CrossChannelConversationContextService;
import com.app.chat.Message;
import com.app.chat.MessageRepository;
import com.app.customers.CustomerIdentityService;
import com.app.feedback.FeedbackRepository;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.leads.LeadService;
// ✅ NEW: ChannelConversationService now requires CustomerIdentityService
import com.app.modelserver.ChatRuntimeService;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.dto.ChatResponse;
import com.app.purchases.PurchaseRequestService;
import com.app.tenant.TenantContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.lang.reflect.Method;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class MessengerWebhookControllerContinuityTest {

    @Mock
    private MessengerPageBindingRepository bindingRepo;
    @Mock
    private ChatbotInstanceRepository botRepo;
    @Mock
    private ConversationRepository conversationRepository;
    @Mock
    private MessageRepository msgRepo;
    @Mock
    private LeadRepository leadRepo;
    @Mock
    private ChatRuntimeService chatRuntimeService;
    @Mock
    private LlmInstanceManager llmInstanceManager;
    @Mock
    private MessengerSendService sendService;
    @Mock
    private LeadService leadService;
    @Mock
    private PurchaseRequestService purchaseRequestService;
    @Mock
    private FeedbackRepository feedbackRepo;
    @Mock
    private CustomerIdentityService customerIdentityService;
    @Mock
    private ConversationResetService conversationResetService;
    @Mock
    private CrossChannelConversationContextService crossChannelConversationContextService;
    // ✅ customerIdentityService is also passed to ChannelConversationService below

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void sameSenderReusesConversationAndCarriesHistoryAcrossMessengerWebhookMessages() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.randomUUID();
        String pageId = "page-123";
        String senderId = "sender-999";
        String firstText = "Hi, I'm looking for a sofa for a small apartment.";
        String secondText = "Modern style, easy to clean, under $800.";
        String expectedConversationKey = "messenger:page:page-123:sender:sender-999";
        List<Conversation> savedConversations = new ArrayList<>();
        List<Message> savedMessages = new ArrayList<>();

        MessengerPageBinding binding = new MessengerPageBinding();
        binding.setId(UUID.randomUUID());
        binding.setTenantId(tenantId);
        binding.setChatbotId(chatbotId);
        binding.setPageId(pageId);
        binding.setPageAccessToken("token-1");

        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(chatbotId);
        bot.setBaseModel("model-a");
        bot.setAdapterPath("adapter-a");

        when(bindingRepo.findByPageIdAndStatus(pageId, "ACTIVE")).thenReturn(Optional.of(binding));
        when(botRepo.findById(chatbotId)).thenReturn(Optional.of(bot));
        when(leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(any(), any()))
                .thenReturn(Optional.empty());

        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                expectedConversationKey,
                "ACTIVE"
        )).thenAnswer(invocation -> savedConversations.stream()
                .filter(conversation -> tenantId.equals(conversation.getTenantId()))
                .filter(conversation -> expectedConversationKey.equals(conversation.getUserExternalId()))
                .filter(conversation -> "ACTIVE".equals(conversation.getStatus()))
                .max(Comparator.comparing(Conversation::getCreatedAt)));
        when(conversationRepository.save(any(Conversation.class))).thenAnswer(invocation -> {
            Conversation conversation = invocation.getArgument(0);
            savedConversations.add(conversation);
            return conversation;
        });

        when(msgRepo.save(any(Message.class))).thenAnswer(invocation -> {
            Message message = invocation.getArgument(0);
            if (message.getCreatedAt() == null) {
                message.setCreatedAt(Instant.now());
            }
            savedMessages.add(message);
            return message;
        });
        when(msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(any(UUID.class))).thenAnswer(invocation -> {
            UUID conversationId = invocation.getArgument(0);
            return savedMessages.stream()
                    .filter(message -> conversationId.equals(message.getConversationId()))
                    .sorted(Comparator.comparing(Message::getCreatedAt))
                    .toList();
        });

        when(chatRuntimeService.chat(
                any(UUID.class),
                any(ChatbotInstance.class),
                any(String.class),
                any(List.class),
                any(String.class),
                any(String.class),
                any(String.class)
        )).thenAnswer(invocation -> {
            String prompt = invocation.getArgument(2);
            @SuppressWarnings("unchecked")
            List<String> history = invocation.getArgument(3);
            assertEquals("tenant_sales", invocation.getArgument(6));
            if (prompt.equals(firstText)) {
                return new ChatRuntimeService.Result(
                        new ChatResponse("What style and budget are you aiming for?", 6, "model-a", null, false, null, null,
                                Map.of("mode", "tenant_sales")),
                        "http://127.0.0.1:8101",
                        ""
                );
            }
            if (prompt.equals(secondText)) {
                return new ChatRuntimeService.Result(
                        new ChatResponse("For a small apartment, a modern sofa that's easy to clean and under $800 is a strong fit.", 4, "model-a", null, false, null, null,
                                Map.of("mode", "tenant_sales")),
                        "http://127.0.0.1:8101",
                        ""
                );
            }

            fail("Unexpected prompt: " + prompt);
            return null;
        });

        MessengerWebhookController controller = new MessengerWebhookController(
                bindingRepo,
                messengerProperties(),
                botRepo,
                new ChannelConversationService(conversationRepository, customerIdentityService),
                msgRepo,
                leadRepo,
                chatRuntimeService,
                llmInstanceManager,
                sendService,
                leadService,
                purchaseRequestService,
                feedbackRepo,
                customerIdentityService,
                conversationResetService,
                crossChannelConversationContextService
        );

        invokeHandlePayload(controller, messengerPayload(pageId, senderId, "mid-1", firstText));
        invokeHandlePayload(controller, messengerPayload(pageId, senderId, "mid-2", secondText));

        assertEquals(1, savedConversations.size());
        Conversation conversation = savedConversations.get(0);
        assertEquals(expectedConversationKey, conversation.getUserExternalId());

        assertEquals(4, savedMessages.size());
        assertTrue(savedMessages.stream().allMatch(message -> conversation.getId().equals(message.getConversationId())));
        assertEquals(List.of("user", "assistant", "user", "assistant"),
                savedMessages.stream().map(Message::getRole).toList());
        assertEquals(List.of(
                firstText,
                "What style and budget are you aiming for?",
                secondText,
                "For a small apartment, a modern sofa that's easy to clean and under $800 is a strong fit."
        ), savedMessages.stream().map(Message::getContent).toList());

        // Resolver được gọi từ cả MessengerWebhookController và ChannelConversationService
        // Mỗi message gọi 2 lần (1 từ webhook, 1 từ ChannelConversationService), tổng 4 lần cho 2 messages
    }

    @Test
    void inactiveOrMissingBindingIsIgnoredWithoutCallingChatbotOrSend() throws Exception {
        String pageId = "page-inactive";
        String senderId = "sender-999";

        when(bindingRepo.findByPageIdAndStatus(pageId, "ACTIVE")).thenReturn(Optional.empty());

        MessengerWebhookController controller = new MessengerWebhookController(
                bindingRepo,
                messengerProperties(),
                botRepo,
                new ChannelConversationService(conversationRepository, customerIdentityService),
                msgRepo,
                leadRepo,
                chatRuntimeService,
                llmInstanceManager,
                sendService,
                leadService,
                purchaseRequestService,
                feedbackRepo,
                customerIdentityService,
                conversationResetService,
                crossChannelConversationContextService
        );

        invokeHandlePayload(controller, messengerPayload(pageId, senderId, "mid-inactive", "Hello"));

        verify(botRepo, never()).findById(any(UUID.class));
        verify(llmInstanceManager, never()).getOrStartSession(any(UUID.class), any(ChatbotInstance.class));
        verify(sendService, never()).sendText(any(String.class), any(String.class), any(String.class), any(String.class));
    }

    @Test
    void askConfirmationReplyUsesMessengerQuickReplies() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.randomUUID();
        String pageId = "page-confirm";
        String senderId = "sender-confirm";
        String expectedConversationKey = "messenger:page:page-confirm:sender:sender-confirm";
        Conversation conversation = conversation(tenantId, chatbotId, expectedConversationKey);
        MessengerPageBinding binding = binding(tenantId, chatbotId, pageId);
        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(chatbotId);
        bot.setBaseModel("model-a");

        when(bindingRepo.findByPageIdAndStatus(pageId, "ACTIVE")).thenReturn(Optional.of(binding));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                expectedConversationKey,
                "ACTIVE"
        )).thenReturn(Optional.of(conversation));
        when(botRepo.findById(chatbotId)).thenReturn(Optional.of(bot));
        when(leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(any(), any()))
                .thenReturn(Optional.empty());
        when(msgRepo.save(any(Message.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(any(UUID.class))).thenReturn(List.of());
        when(chatRuntimeService.chat(
                any(UUID.class),
                any(ChatbotInstance.class),
                any(String.class),
                any(List.class),
                any(String.class),
                any(String.class),
                any(String.class)
        )).thenReturn(new ChatRuntimeService.Result(
                new ChatResponse(
                        "Bạn xác nhận gửi yêu cầu này cho cửa hàng không?",
                        4,
                        "sales-template",
                        null,
                        false,
                        null,
                        null,
                        Map.of(
                                "mode", "tenant_sales",
                                "sales_action_taken", "ask_confirmation",
                                "confirmation_status", "pending",
                                "handoff_status", "pending_confirmation"
                        )
                ),
                "http://127.0.0.1:8101",
                ""
        ));

        MessengerWebhookController controller = controller();
        invokeHandlePayload(controller, messengerPayload(pageId, senderId, "mid-confirm", "Toi lay P1, so toi 0987654321"));

        verify(sendService).sendTextWithQuickReplies(
                eq(pageId),
                eq(senderId),
                eq("Bạn xác nhận gửi yêu cầu này cho cửa hàng không?"),
                eq("token-1"),
                argThat(replies -> replies.stream().anyMatch(item -> "BUY_CONFIRM".equals(item.get("payload")))
                        && replies.stream().anyMatch(item -> "BUY_REJECT".equals(item.get("payload"))))
        );
        verify(sendService, never()).sendText(eq(pageId), eq(senderId), eq("Bạn xác nhận gửi yêu cầu này cho cửa hàng không?"), eq("token-1"));
    }

    @Test
    void buyConfirmQuickReplyCreatesLeadWithoutPurchaseRequest() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.randomUUID();
        String pageId = "page-confirm";
        String senderId = "sender-confirm";
        String expectedConversationKey = "messenger:page:page-confirm:sender:sender-confirm";
        Conversation conversation = conversation(tenantId, chatbotId, expectedConversationKey);
        MessengerPageBinding binding = binding(tenantId, chatbotId, pageId);
        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(chatbotId);
        bot.setBaseModel("model-a");
        Lead lead = Lead.createNew(tenantId.toString(), "messenger", conversation.getId().toString(), senderId, "{}", "");

        mockConfirmedMessengerTurn(tenantId, chatbotId, pageId, expectedConversationKey, conversation, binding, bot, lead);

        MessengerWebhookController controller = controller();
        invokeHandlePayload(controller, messengerQuickReplyPayload(pageId, senderId, "mid-buy-confirm", "BUY_CONFIRM"));

        verify(leadService).createFromChatbotHandoff(argThat(data ->
                tenantId.toString().equals(data.tenantId())
                        && conversation.getId().toString().equals(data.conversationId())
                        && "messenger".equals(data.channel())
                        && senderId.equals(data.customerExternalId())
                        && "handoff-1".equals(data.handoffId())
        ));
        verify(purchaseRequestService, never()).findOrCreateFromLead(any());
    }

    @Test
    void textConfirmCreatesLeadWithoutPurchaseRequest() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.randomUUID();
        String pageId = "page-text-confirm";
        String senderId = "sender-text-confirm";
        String expectedConversationKey = "messenger:page:page-text-confirm:sender:sender-text-confirm";
        Conversation conversation = conversation(tenantId, chatbotId, expectedConversationKey);
        MessengerPageBinding binding = binding(tenantId, chatbotId, pageId);
        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(chatbotId);
        bot.setBaseModel("model-a");
        Lead lead = Lead.createNew(tenantId.toString(), "messenger", conversation.getId().toString(), senderId, "{}", "");

        mockConfirmedMessengerTurn(tenantId, chatbotId, pageId, expectedConversationKey, conversation, binding, bot, lead);

        MessengerWebhookController controller = controller();
        invokeHandlePayload(controller, messengerPayload(pageId, senderId, "mid-text-confirm", "co"));

        verify(leadService).createFromChatbotHandoff(any(LeadService.ChatbotHandoffLeadData.class));
        verify(purchaseRequestService, never()).findOrCreateFromLead(any());
    }

    @Test
    void repeatedConfirmDoesNotCreateDuplicateLead() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.randomUUID();
        String pageId = "page-repeat-confirm";
        String senderId = "sender-repeat-confirm";
        String expectedConversationKey = "messenger:page:page-repeat-confirm:sender:sender-repeat-confirm";
        Conversation conversation = conversation(tenantId, chatbotId, expectedConversationKey);
        MessengerPageBinding binding = binding(tenantId, chatbotId, pageId);
        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(chatbotId);
        bot.setBaseModel("model-a");
        Lead lead = Lead.createNew(tenantId.toString(), "messenger", conversation.getId().toString(), senderId, "{}", "");

        mockConfirmedMessengerTurn(tenantId, chatbotId, pageId, expectedConversationKey, conversation, binding, bot, lead);

        MessengerWebhookController controller = controller();
        invokeHandlePayload(controller, messengerQuickReplyPayload(pageId, senderId, "mid-repeat-1", "BUY_CONFIRM"));
        invokeHandlePayload(controller, messengerQuickReplyPayload(pageId, senderId, "mid-repeat-2", "BUY_CONFIRM"));

        verify(leadService, times(1)).createFromChatbotHandoff(any(LeadService.ChatbotHandoffLeadData.class));
        verify(purchaseRequestService, never()).findOrCreateFromLead(any());
    }

    @Test
    void buyRejectDoesNotCreateLead() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.randomUUID();
        String pageId = "page-reject";
        String senderId = "sender-reject";
        String expectedConversationKey = "messenger:page:page-reject:sender:sender-reject";
        Conversation conversation = conversation(tenantId, chatbotId, expectedConversationKey);
        MessengerPageBinding binding = binding(tenantId, chatbotId, pageId);
        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(chatbotId);
        bot.setBaseModel("model-a");

        when(bindingRepo.findByPageIdAndStatus(pageId, "ACTIVE")).thenReturn(Optional.of(binding));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                expectedConversationKey,
                "ACTIVE"
        )).thenReturn(Optional.of(conversation));
        when(botRepo.findById(chatbotId)).thenReturn(Optional.of(bot));
        when(leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(any(), any()))
                .thenReturn(Optional.empty());
        when(msgRepo.save(any(Message.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(any(UUID.class))).thenReturn(List.of());
        when(chatRuntimeService.chat(any(UUID.class), any(ChatbotInstance.class), any(String.class), any(List.class), any(String.class), any(String.class), any(String.class)))
                .thenReturn(new ChatRuntimeService.Result(
                        new ChatResponse("Da huy.", 4, "sales-template", null, false, null, null,
                                Map.of(
                                        "mode", "tenant_sales",
                                        "sales_action_taken", "confirmation_cancelled",
                                        "confirmation_status", "cancelled",
                                        "handoff_status", "cancelled"
                                )),
                        "http://127.0.0.1:8101",
                        ""
                ));

        MessengerWebhookController controller = controller();
        invokeHandlePayload(controller, messengerQuickReplyPayload(pageId, senderId, "mid-reject", "BUY_REJECT"));

        verify(leadService, never()).createFromChatbotHandoff(any());
        verify(purchaseRequestService, never()).findOrCreateFromLead(any());
    }

    @Test
    void resetCommandResetsCurrentMessengerConversationWithoutCallingChatbotOrSavingMessage() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.randomUUID();
        String pageId = "page-123";
        String senderId = "sender-999";
        String expectedConversationKey = "messenger:page:page-123:sender:sender-999";
        Conversation conversation = conversation(tenantId, chatbotId, expectedConversationKey);
        MessengerPageBinding binding = binding(tenantId, chatbotId, pageId);

        when(bindingRepo.findByPageIdAndStatus(pageId, "ACTIVE")).thenReturn(Optional.of(binding));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                expectedConversationKey,
                "ACTIVE"
        )).thenReturn(Optional.of(conversation));

        MessengerWebhookController controller = controller();
        invokeHandlePayload(controller, messengerPayload(pageId, senderId, "mid-reset", " /reset "));

        verify(conversationResetService).reset(
                eq(tenantId),
                argThat(request -> request.conversationId().equals(conversation.getId().toString())
                        && request.shouldDeleteMessages()
                        && request.shouldResetBusinessFlags())
        );
        verify(msgRepo, never()).save(any(Message.class));
        verify(chatRuntimeService, never()).chat(any(UUID.class), any(ChatbotInstance.class), any(String.class), any(List.class), any(String.class), any(String.class));
        verify(sendService).sendText(pageId, senderId, "Xong.", "token-1");
    }

    @Test
    void resetTestCommandResetsBusinessFlagsForConversation() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID chatbotId = UUID.randomUUID();
        String pageId = "page-456";
        String senderId = "sender-888";
        String expectedConversationKey = "messenger:page:page-456:sender:sender-888";
        Conversation conversation = conversation(tenantId, chatbotId, expectedConversationKey);
        MessengerPageBinding binding = binding(tenantId, chatbotId, pageId);

        when(bindingRepo.findByPageIdAndStatus(pageId, "ACTIVE")).thenReturn(Optional.of(binding));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                expectedConversationKey,
                "ACTIVE"
        )).thenReturn(Optional.of(conversation));

        MessengerWebhookController controller = controller();
        invokeHandlePayload(controller, messengerPayload(pageId, senderId, "mid-reset-test", "/reset-test"));

        verify(conversationResetService).reset(
                eq(tenantId),
                argThat(request -> request.conversationId().equals(conversation.getId().toString())
                        && request.shouldDeleteMessages()
                        && request.shouldResetBusinessFlags())
        );
        verify(msgRepo, never()).save(any(Message.class));
        verify(chatRuntimeService, never()).chat(any(UUID.class), any(ChatbotInstance.class), any(String.class), any(List.class), any(String.class), any(String.class));
    }

    private MessengerWebhookController controller() {
        return new MessengerWebhookController(
                bindingRepo,
                messengerProperties(),
                botRepo,
                new ChannelConversationService(conversationRepository, customerIdentityService),
                msgRepo,
                leadRepo,
                chatRuntimeService,
                llmInstanceManager,
                sendService,
                leadService,
                purchaseRequestService,
                feedbackRepo,
                customerIdentityService,
                conversationResetService,
                crossChannelConversationContextService
        );
    }

    private static MessengerPageBinding binding(UUID tenantId, UUID chatbotId, String pageId) {
        MessengerPageBinding binding = new MessengerPageBinding();
        binding.setId(UUID.randomUUID());
        binding.setTenantId(tenantId);
        binding.setChatbotId(chatbotId);
        binding.setPageId(pageId);
        binding.setPageAccessToken("token-1");
        return binding;
    }

    private static Conversation conversation(UUID tenantId, UUID chatbotId, String userExternalId) {
        Conversation conversation = new Conversation();
        conversation.setId(UUID.randomUUID());
        conversation.setTenantId(tenantId);
        conversation.setChatbotId(chatbotId);
        conversation.setUserExternalId(userExternalId);
        conversation.setStatus("ACTIVE");
        return conversation;
    }

    private void mockConfirmedMessengerTurn(
            UUID tenantId,
            UUID chatbotId,
            String pageId,
            String expectedConversationKey,
            Conversation conversation,
            MessengerPageBinding binding,
            ChatbotInstance bot,
            Lead lead
    ) {
        when(bindingRepo.findByPageIdAndStatus(pageId, "ACTIVE")).thenReturn(Optional.of(binding));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                expectedConversationKey,
                "ACTIVE"
        )).thenReturn(Optional.of(conversation));
        when(botRepo.findById(chatbotId)).thenReturn(Optional.of(bot));
        when(leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(any(), any()))
                .thenReturn(Optional.empty());
        when(msgRepo.save(any(Message.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(any(UUID.class))).thenReturn(List.of());
        when(leadService.createFromChatbotHandoff(any(LeadService.ChatbotHandoffLeadData.class))).thenReturn(lead);
        when(chatRuntimeService.chat(any(UUID.class), any(ChatbotInstance.class), any(String.class), any(List.class), any(String.class), any(String.class), any(String.class)))
                .thenReturn(new ChatRuntimeService.Result(
                        new ChatResponse("Da gui yeu cau cho cua hang.", 4, "sales-template", null, false, "0912345678", "Nguyen Van A",
                                Map.of(
                                        "mode", "tenant_sales",
                                        "sales_action_taken", "handoff_sent",
                                        "confirmation_status", "confirmed",
                                        "handoff_status", "sent",
                                        "handoff_id", "handoff-1",
                                        "product_sku", "GHO-607",
                                        "quantity", 1
                                )),
                        "http://127.0.0.1:8101",
                        ""
                ));
    }

    private static void invokeHandlePayload(MessengerWebhookController controller, Map<String, Object> payload) throws Exception {
        Method method = MessengerWebhookController.class.getDeclaredMethod("handlePayload", Map.class);
        method.setAccessible(true);
        method.invoke(controller, payload);
    }

    private static Map<String, Object> messengerPayload(String pageId, String senderId, String mid, String text) {
        return Map.of(
                "object", "page",
                "entry", List.of(Map.of(
                        "id", pageId,
                        "messaging", List.of(Map.of(
                                "sender", Map.of("id", senderId),
                                "recipient", Map.of("id", pageId),
                                "message", Map.of("mid", mid, "text", text)
                        ))
                ))
        );
    }

    private static Map<String, Object> messengerQuickReplyPayload(String pageId, String senderId, String mid, String payload) {
        return Map.of(
                "object", "page",
                "entry", List.of(Map.of(
                        "id", pageId,
                        "messaging", List.of(Map.of(
                                "sender", Map.of("id", senderId),
                                "recipient", Map.of("id", pageId),
                                "message", Map.of(
                                        "mid", mid,
                                        "text", payload,
                                        "quick_reply", Map.of("payload", payload)
                                )
                        ))
                ))
        );
    }

    private static MessengerProperties messengerProperties() {
        MessengerProperties props = new MessengerProperties();
        props.setVerifyToken("test-verify-token");
        return props;
    }
}
