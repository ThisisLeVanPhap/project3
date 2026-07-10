package com.app.telegram;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.chat.ChannelConversationService;
import com.app.chat.Conversation;
import com.app.chat.ConversationResetRequest;
import com.app.chat.ConversationResetService;
import com.app.chat.CrossChannelConversationContextService;
import com.app.chat.Message;
import com.app.chat.MessageRepository;
import com.app.chat.NewConsultationSessionResponse;
import com.app.customers.CustomerIdentityService;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.leads.LeadService;
import com.app.modelserver.ChatbotMode;
import com.app.modelserver.ChatRuntimeService;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.dto.ChatResponse;
import com.app.purchases.PurchaseRequestService;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

// ✅ NEW: feedback imports
import com.app.feedback.Feedback;
import com.app.feedback.FeedbackRepository;

import java.util.*;
import java.util.concurrent.*;

@Slf4j
@RestController
@RequestMapping("/webhook/telegram")
@RequiredArgsConstructor
public class TelegramWebhookController {

    private final TelegramBotBindingRepository bindingRepo;
    private final ChatbotInstanceRepository botRepo;

    private final ChannelConversationService channelConversationService;
    private final MessageRepository msgRepo;
    private final LeadRepository leadRepo;

    private final ChatRuntimeService chatRuntimeService;
    private final LlmInstanceManager llmInstanceManager;
    private final TelegramSendService sendService;

    private final LeadService leadService;
    private final PurchaseRequestService purchaseRequestService;

    // ✅ NEW: feedback repo
    private final FeedbackRepository feedbackRepo;
    private final CustomerIdentityService customerIdentityService;
    private final ConversationResetService conversationResetService;
    private final CrossChannelConversationContextService crossChannelConversationContextService;

    private final Set<Long> processedUpdateIds = ConcurrentHashMap.newKeySet();
    private final ExecutorService workerPool = Executors.newFixedThreadPool(8);

    @PostMapping("/{secretPath}")
    public ResponseEntity<String> onUpdate(
            @PathVariable String secretPath,
            @RequestBody Map<String, Object> update
    ) {
        workerPool.submit(() -> {
            try { handle(secretPath, update); }
            catch (Exception e) { log.error("Telegram webhook async error", e); }
        });
        return ResponseEntity.ok("ok");
    }

    @SuppressWarnings("unchecked")
    private void handle(String secretPath, Map<String, Object> update) {
        TelegramBotBinding binding = bindingRepo.findBySecretPathAndStatus(secretPath, "ACTIVE")
                .orElseThrow(() -> new IllegalArgumentException("Invalid telegram secretPath"));

        Long updateId = update.get("update_id") instanceof Number n ? n.longValue() : null;
        if (updateId != null && !processedUpdateIds.add(updateId)) return;

        String prevTenant = TenantContext.get();
        try {
            TenantContext.set(binding.getTenantId().toString());

            Map<String, Object> msg = (Map<String, Object>) update.get("message");
            if (msg == null) return;

            String text = (String) msg.get("text");
            if (text == null || text.isBlank()) return;

            Map<String, Object> chat = (Map<String, Object>) msg.get("chat");
            if (chat == null) return;
            String chatId = String.valueOf(chat.get("id"));

            String senderKey = channelConversationService.buildTelegramSenderKey(chatId);
            Conversation conv = channelConversationService.findOrCreateActiveConversation(
                    binding.getTenantId(),
                    binding.getChatbotId(),
                    "telegram",
                    senderKey
            );

            if (handleResetCommand(binding, conv, chatId, text)) {
                return;
            }
            channelConversationService.linkIdentityFromMessage(
                    binding.getTenantId(),
                    conv,
                    "telegram",
                    senderKey,
                    telegramDisplayName(chat, msg),
                    text
            );

            ChatbotInstance bot = botRepo.findById(conv.getChatbotId())
                    .orElseThrow(() -> new IllegalStateException("Bot not found: " + conv.getChatbotId()));

            // ✅ always persist user msg
            Message mUser = new Message();
            mUser.setId(UUID.randomUUID());
            mUser.setTenantId(binding.getTenantId());
            mUser.setConversationId(conv.getId());
            mUser.setRole("user");
            mUser.setContent(text);
            msgRepo.save(mUser);

            // =====================================================
            // ✅ NEW: RATE GOOD / RATE BAD -> insert feedback
            // Put it early so it works even during HANDOFF.
            // =====================================================
            String norm = text.trim().toUpperCase(Locale.ROOT);
            if (norm.equals("RATE GOOD") || norm.equals("RATE BAD")) {
                int rating = norm.equals("RATE GOOD") ? 1 : -1;

                Feedback fb = new Feedback();
                fb.setTenantId(binding.getTenantId().toString());
                fb.setConversationId(conv.getId().toString());
                fb.setRating(rating);
                fb.setComment("rate_keyword");
                feedbackRepo.save(fb);

                sendService.sendText(binding.getBotToken(), chatId, "Thanks for your feedback!");
                return;
            }

            String baseUrl = "";
            String t = text.trim();
            String requestedMode = ChatbotMode.normalize(bot.getMode());

            if ("CONFIRM".equalsIgnoreCase(t)) {
                if (!ChatbotMode.isTenantSales(requestedMode)) {
                    String blockedMsg = "This chat mode does not create purchase requests.";
                    log.info(
                            "Blocked Telegram CONFIRM by mode contract tenant={} conversationId={} requestedMode={}",
                            binding.getTenantId(),
                            conv.getId(),
                            requestedMode
                    );
                    Message mBot = new Message();
                    mBot.setId(UUID.randomUUID());
                    mBot.setTenantId(binding.getTenantId());
                    mBot.setConversationId(conv.getId());
                    mBot.setRole("assistant");
                    mBot.setContent(blockedMsg);
                    msgRepo.save(mBot);
                    sendService.sendText(binding.getBotToken(), chatId, blockedMsg);
                    return;
                }
                try {
                    LlmInstanceManager.Session session = llmInstanceManager.getOrStartSession(binding.getTenantId(), bot);
                    baseUrl = session.baseUrl();
                    Lead lead = leadService.createLeadFromConversation(
                            baseUrl,
                            binding.getTenantId().toString(),
                            "telegram",
                            conv.getId().toString(),
                            chatId
                    );
                    purchaseRequestService.findOrCreateFromLead(lead);

                    String handoffMsg =
                            "Thanks! Our staff will follow up to confirm delivery details.";

                    Message mBot = new Message();
                    mBot.setId(UUID.randomUUID());
                    mBot.setTenantId(binding.getTenantId());
                    mBot.setConversationId(conv.getId());
                    mBot.setRole("assistant");
                    mBot.setContent(handoffMsg);
                    msgRepo.save(mBot);

                    sendService.sendText(binding.getBotToken(), chatId, handoffMsg);
                } catch (Exception e) {
                    log.error("CONFIRM failed", e);
                    sendService.sendText(binding.getBotToken(), chatId,
                            "Sorry — I couldn’t create the purchase request right now. Please try again.");
                }
                return;
            }

            if ("CANCEL".equalsIgnoreCase(t)) {
                sendService.sendText(binding.getBotToken(), chatId,
                        "No problem — I’ve canceled the confirmation step. What would you like to do next?");
                return;
            }

            // ✅ HANDOFF gate
            Optional<Lead> leadOpt =
                    leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(
                            binding.getTenantId().toString(), conv.getId().toString());

            if (leadOpt.isPresent() && "HANDOFF".equalsIgnoreCase(leadOpt.get().getStage())) {
                // persist only, staff owns
                return;
            }

            List<Message> historyMsgs = msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(conv.getId());
            List<String> history = new ArrayList<>();
            for (Message hm : historyMsgs) if ("user".equals(hm.getRole())) history.add(hm.getContent());
            List<String> enrichedHistory = crossChannelConversationContextService.enrichHistory(binding.getTenantId(), conv, history);
            if (enrichedHistory != null && (!enrichedHistory.isEmpty() || history.isEmpty())) {
                history = enrichedHistory;
            }

            ChatRuntimeService.Result runtimeResult = chatRuntimeService.chat(
                    binding.getTenantId(),
                    bot,
                    text,
                    history,
                    conv.getId().toString(),
                    "telegram"
            );
            baseUrl = runtimeResult.baseUrl();
            ChatResponse ai = runtimeResult.response();

            String finalMode = ChatbotMode.finalMode(ai, requestedMode);
            log.info(
                    "Chat mode contract channel=telegram tenant={} conversationId={} requestedMode={} finalMode={} triggerPurchaseRequest={}",
                    binding.getTenantId(),
                    conv.getId(),
                    requestedMode,
                    finalMode,
                    ai.trigger_purchase_request()
            );
            if (Boolean.TRUE.equals(ai.trigger_purchase_request()) && !ChatbotMode.allowsPurchaseRequest(requestedMode, ai)) {
                log.info(
                        "Blocked purchase request by mode contract tenant={} conversationId={} requestedMode={} finalMode={}",
                        binding.getTenantId(),
                        conv.getId(),
                        requestedMode,
                        finalMode
                );
            }

            String reply = (ai.reply() == null) ? "" : ai.reply().trim();
            if (reply.isBlank()) return;

            Message mBot = new Message();
            mBot.setId(UUID.randomUUID());
            mBot.setTenantId(binding.getTenantId());
            mBot.setConversationId(conv.getId());
            mBot.setRole("assistant");
            mBot.setContent(reply);
            msgRepo.save(mBot);

            sendService.sendText(binding.getBotToken(), chatId, reply);

        } finally {
            if (prevTenant == null) TenantContext.clear();
            else TenantContext.set(prevTenant);
        }
    }

    private boolean handleResetCommand(TelegramBotBinding binding, Conversation conv, String chatId, String text) {
        String command = text == null ? "" : text.trim().toLowerCase(Locale.ROOT);
        if (!command.equals("/reset") && !command.equals("/reset-test") && !command.equals("/new") && !command.equals("/reset-all")) {
            return false;
        }

        String reply;
        if (command.equals("/new") || command.equals("/reset-all")) {
            NewConsultationSessionResponse ignored = conversationResetService.startNewConsultationSession(
                    binding.getTenantId(),
                    conv.getChatbotId(),
                    "telegram",
                    conv.getUserExternalId(),
                    conv.getId(),
                    conv.getUnifiedCustomerId()
            );
            reply = "Xong.";
        } else {
            conversationResetService.reset(
                    binding.getTenantId(),
                    new ConversationResetRequest(
                            conv.getId().toString(),
                            null,
                            null,
                            null,
                            true,
                            true
                    )
            );
            reply = "Xong.";
        }
        sendService.sendText(
                binding.getBotToken(),
                chatId,
                reply
        );
        return true;
    }

    @SuppressWarnings("unchecked")
    private void resolveCustomerIdentity(UUID tenantId, String senderKey, Map<String, Object> chat, Map<String, Object> msg) {
        if (customerIdentityService == null) {
            return;
        }
        String displayName = telegramDisplayName(chat, msg);
        try {
            customerIdentityService.resolveOrCreateIdentity(
                    tenantId,
                    "telegram",
                    senderKey,
                    displayName,
                    null,
                    null
            );
        } catch (RuntimeException ex) {
            log.debug("Skip telegram customer identity resolution tenant={} senderKey={}", tenantId, senderKey, ex);
        }
    }

    private String telegramDisplayName(Map<String, Object> chat, Map<String, Object> msg) {
        Object fromRaw = msg.get("from");
        if (fromRaw instanceof Map<?, ?> from) {
            Object firstName = from.get("first_name");
            Object lastName = from.get("last_name");
            String first = firstName == null ? "" : String.valueOf(firstName).trim();
            String last = lastName == null ? "" : String.valueOf(lastName).trim();
            String combined = (first + " " + last).trim();
            if (!combined.isBlank()) {
                return combined;
            }
        }
        if (chat != null) {
            Object title = chat.get("title");
            if (title != null && !String.valueOf(title).isBlank()) {
                return String.valueOf(title).trim();
            }
        }
        return null;
    }
}
