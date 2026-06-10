package com.app.messenger;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.chat.ChannelConversationService;
import com.app.chat.Conversation;
import com.app.chat.ConversationRepository;
import com.app.chat.Message;
import com.app.chat.MessageRepository;
import com.app.feedback.FeedbackRepository;
import com.app.leads.LeadRepository;
import com.app.leads.LeadService;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
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
    private PythonChatClient python;
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
        when(llmInstanceManager.getOrStartSession(tenantId, bot))
                .thenReturn(new LlmInstanceManager.Session("http://127.0.0.1:8101", false, false));

        when(conversationRepository.findTop1ByTenantIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
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

        when(python.chat(
                eq("http://127.0.0.1:8101"),
                any(String.class),
                any(List.class),
                eq(bot),
                any(String.class),
                eq("messenger"),
                eq(tenantId.toString()),
                eq(false),
                eq(false)
        )).thenAnswer(invocation -> {
            String prompt = invocation.getArgument(1);
            @SuppressWarnings("unchecked")
            List<String> history = invocation.getArgument(2);

            if (firstText.equals(prompt)) {
                assertEquals(List.of(firstText), history);
                return new ChatResponse("What style and budget are you aiming for?", 12, "model-a", "adapter-a", false, null, null, Map.of("mode", "tenant_sales"));
            }
            if (secondText.equals(prompt)) {
                assertEquals(List.of(firstText, secondText), history);
                return new ChatResponse(
                        "For a small apartment, a modern sofa that's easy to clean and under $800 is a strong fit.",
                        14,
                        "model-a",
                        "adapter-a",
                        false,
                        null,
                        null,
                        Map.of("mode", "tenant_sales")
                );
            }

            fail("Unexpected prompt: " + prompt);
            return null;
        });

        MessengerWebhookController controller = new MessengerWebhookController(
                bindingRepo,
                messengerProperties(),
                botRepo,
                new ChannelConversationService(conversationRepository),
                msgRepo,
                leadRepo,
                python,
                llmInstanceManager,
                sendService,
                leadService,
                purchaseRequestService,
                feedbackRepo
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

        verify(conversationRepository, times(2))
                .findTop1ByTenantIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                        tenantId,
                        expectedConversationKey,
                        "ACTIVE"
                );
        verify(conversationRepository, times(1)).save(any(Conversation.class));
        verify(sendService).sendText(pageId, senderId, "What style and budget are you aiming for?", "token-1");
        verify(sendService).sendText(
                pageId,
                senderId,
                "For a small apartment, a modern sofa that's easy to clean and under $800 is a strong fit.",
                "token-1"
        );
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
                new ChannelConversationService(conversationRepository),
                msgRepo,
                leadRepo,
                python,
                llmInstanceManager,
                sendService,
                leadService,
                purchaseRequestService,
                feedbackRepo
        );

        invokeHandlePayload(controller, messengerPayload(pageId, senderId, "mid-inactive", "Hello"));

        verify(botRepo, never()).findById(any(UUID.class));
        verify(llmInstanceManager, never()).getOrStartSession(any(UUID.class), any(ChatbotInstance.class));
        verify(sendService, never()).sendText(any(String.class), any(String.class), any(String.class), any(String.class));
    }

    private static void invokeHandlePayload(MessengerWebhookController controller, Map<String, Object> payload) throws Exception {
        Method method = MessengerWebhookController.class.getDeclaredMethod("handlePayload", Map.class);
        method.setAccessible(true);
        method.invoke(controller, payload);
    }

    private static MessengerProperties messengerProperties() {
        MessengerProperties properties = new MessengerProperties();
        properties.setVerifyToken("woodchat_secret");
        properties.setDemoMode(false);
        return properties;
    }

    private static Map<String, Object> messengerPayload(String pageId, String senderId, String mid, String text) {
        return Map.of(
                "entry", List.of(
                        Map.of(
                                "id", pageId,
                                "messaging", List.of(
                                        Map.of(
                                                "sender", Map.of("id", senderId),
                                                "message", Map.of(
                                                        "mid", mid,
                                                        "text", text
                                                )
                                        )
                                )
                        )
                )
        );
    }
}
