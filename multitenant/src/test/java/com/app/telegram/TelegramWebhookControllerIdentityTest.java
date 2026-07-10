package com.app.telegram;

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
import com.app.leads.LeadRepository;
import com.app.leads.LeadService;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TelegramWebhookControllerIdentityTest {

    @Mock
    private TelegramBotBindingRepository bindingRepo;
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
    private TelegramSendService sendService;
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

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void telegramWebhookResolvesIdentityBeforeChat() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        String secretPath = "secret-1";
        String chatId = "42";
        String senderKey = "chat:42";
        List<Conversation> savedConversations = new ArrayList<>();
        List<Message> savedMessages = new ArrayList<>();

        TelegramBotBinding binding = new TelegramBotBinding();
        binding.setId(UUID.randomUUID());
        binding.setTenantId(tenantId);
        binding.setChatbotId(chatbotId);
        binding.setBotToken("bot-token");
        binding.setSecretPath(secretPath);
        binding.setStatus("ACTIVE");

        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(chatbotId);
        bot.setBaseModel("model-a");
        bot.setAdapterPath("adapter-a");

        when(bindingRepo.findBySecretPathAndStatus(secretPath, "ACTIVE")).thenReturn(Optional.of(binding));
        when(botRepo.findById(chatbotId)).thenReturn(Optional.of(bot));
        when(leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(any(), any())).thenReturn(Optional.empty());

        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "telegram:" + senderKey,
                "ACTIVE"
        )).thenAnswer(invocation -> savedConversations.stream()
                .filter(conversation -> tenantId.equals(conversation.getTenantId()))
                .filter(conversation -> ("telegram:" + senderKey).equals(conversation.getUserExternalId()))
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
                eq(tenantId),
                eq(bot),
                eq("Xin chào"),
                any(List.class),
                any(String.class),
                eq("telegram")
        )).thenReturn(new ChatRuntimeService.Result(
                new ChatResponse("Chào bạn!", 8, "model-a", "adapter-a", false, null, null, Map.of("mode", "tenant_sales")),
                "http://127.0.0.1:8101",
                ""
        ));

        TelegramWebhookController controller = new TelegramWebhookController(
                bindingRepo,
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

        invokeHandle(controller, secretPath, telegramPayload(chatId, "Xin chào", "An", "Nguyen", 1001L));

        verify(customerIdentityService, times(1))
                .resolveOrCreateIdentity(tenantId, "telegram", senderKey, null, null, null);
        verify(sendService).sendText("bot-token", chatId, "Chào bạn!");
        assertEquals(1, savedConversations.size());
    }

    @Test
    void resetCommandResetsCurrentTelegramConversationWithoutCallingChatbotOrSavingMessage() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        String secretPath = "secret-1";
        String chatId = "42";
        Conversation conversation = conversation(tenantId, chatbotId, "telegram:chat:42");
        TelegramBotBinding binding = binding(tenantId, chatbotId, secretPath);

        when(bindingRepo.findBySecretPathAndStatus(secretPath, "ACTIVE")).thenReturn(Optional.of(binding));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "telegram:chat:42",
                "ACTIVE"
        )).thenReturn(Optional.of(conversation));

        TelegramWebhookController controller = controller();
        invokeHandle(controller, secretPath, telegramPayload(chatId, " /reset ", "An", "Nguyen", 2001L));

        verify(conversationResetService).reset(
                eq(tenantId),
                argThat(request -> request.conversationId().equals(conversation.getId().toString())
                        && request.shouldDeleteMessages()
                        && request.shouldResetBusinessFlags())
        );
        verify(msgRepo, never()).save(any(Message.class));
        verify(chatRuntimeService, never()).chat(any(UUID.class), any(ChatbotInstance.class), any(String.class), any(List.class), any(String.class), any(String.class));
        verify(sendService).sendText("bot-token", chatId, "Xong.");
    }

    @Test
    void resetTestCommandResetsBusinessFlagsForCurrentTelegramConversation() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        String secretPath = "secret-1";
        String chatId = "42";
        Conversation conversation = conversation(tenantId, chatbotId, "telegram:chat:42");
        TelegramBotBinding binding = binding(tenantId, chatbotId, secretPath);

        when(bindingRepo.findBySecretPathAndStatus(secretPath, "ACTIVE")).thenReturn(Optional.of(binding));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "telegram:chat:42",
                "ACTIVE"
        )).thenReturn(Optional.of(conversation));

        TelegramWebhookController controller = controller();
        invokeHandle(controller, secretPath, telegramPayload(chatId, "/reset-test", "An", "Nguyen", 2002L));

        verify(conversationResetService).reset(
                eq(tenantId),
                argThat(request -> request.conversationId().equals(conversation.getId().toString())
                        && request.shouldDeleteMessages()
                        && request.shouldResetBusinessFlags())
        );
        verify(msgRepo, never()).save(any(Message.class));
        verify(purchaseRequestService, never()).findOrCreateFromLead(any());
        verify(sendService).sendText("bot-token", chatId, "Xong.");
    }

    @Test
    void newCommandStartsFreshTelegramConversationWithoutCallingChatbotOrSavingMessage() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID chatbotId = UUID.randomUUID();
        UUID newConversationId = UUID.randomUUID();
        String secretPath = "secret-1";
        String chatId = "42";
        Conversation conversation = conversation(tenantId, chatbotId, "telegram:chat:42");
        TelegramBotBinding binding = binding(tenantId, chatbotId, secretPath);

        when(bindingRepo.findBySecretPathAndStatus(secretPath, "ACTIVE")).thenReturn(Optional.of(binding));
        when(conversationRepository.findTop1ByTenantIdAndChatbotIdAndUserExternalIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                chatbotId,
                "telegram:chat:42",
                "ACTIVE"
        )).thenReturn(Optional.of(conversation));
        when(conversationResetService.startNewConsultationSession(
                tenantId,
                chatbotId,
                "telegram",
                "telegram:chat:42",
                conversation.getId(),
                null
        )).thenReturn(new com.app.chat.NewConsultationSessionResponse(tenantId.toString(), newConversationId.toString(), 1, 2, 1, 0, 0));

        TelegramWebhookController controller = controller();
        invokeHandle(controller, secretPath, telegramPayload(chatId, "/new", "An", "Nguyen", 2003L));

        verify(conversationResetService).startNewConsultationSession(
                tenantId,
                chatbotId,
                "telegram",
                "telegram:chat:42",
                conversation.getId(),
                null
        );
        verify(msgRepo, never()).save(any(Message.class));
        verify(chatRuntimeService, never()).chat(any(UUID.class), any(ChatbotInstance.class), any(String.class), any(List.class), any(String.class), any(String.class));
        verify(sendService).sendText("bot-token", chatId, "Xong.");
    }

    private TelegramWebhookController controller() {
        return new TelegramWebhookController(
                bindingRepo,
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

    private static TelegramBotBinding binding(UUID tenantId, UUID chatbotId, String secretPath) {
        TelegramBotBinding binding = new TelegramBotBinding();
        binding.setId(UUID.randomUUID());
        binding.setTenantId(tenantId);
        binding.setChatbotId(chatbotId);
        binding.setBotToken("bot-token");
        binding.setSecretPath(secretPath);
        binding.setStatus("ACTIVE");
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

    private static void invokeHandle(TelegramWebhookController controller, String secretPath, Map<String, Object> update) throws Exception {
        Method method = TelegramWebhookController.class.getDeclaredMethod("handle", String.class, Map.class);
        method.setAccessible(true);
        method.invoke(controller, secretPath, update);
    }

    private static Map<String, Object> telegramPayload(String chatId, String text, String firstName, String lastName, Long updateId) {
        return Map.of(
                "update_id", updateId,
                "message", Map.of(
                        "message_id", 1,
                        "from", Map.of(
                                "id", 42L,
                                "is_bot", false,
                                "first_name", firstName,
                                "last_name", lastName,
                                "language_code", "vi"
                        ),
                        "chat", Map.of(
                                "id", chatId,
                                "type", "private"
                        ),
                        "date", (int) (Instant.now().getEpochSecond()),
                        "text", text
                )
        );
    }
}
