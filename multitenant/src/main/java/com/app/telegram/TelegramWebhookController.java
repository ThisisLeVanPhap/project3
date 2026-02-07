package com.app.telegram;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.chat.Conversation;
import com.app.chat.ConversationRepository;
import com.app.chat.Message;
import com.app.chat.MessageRepository;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
import com.app.modelserver.dto.ChatResponse;
import com.app.tenant.TenantContext;
import com.app.leads.LeadService; // <-- NOTE: chỉnh package nếu khác
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.concurrent.*;

@Slf4j
@RestController
@RequestMapping("/webhook/telegram")
@RequiredArgsConstructor
public class TelegramWebhookController {

    private final TelegramBotBindingRepository bindingRepo;
    private final ChatbotInstanceRepository botRepo;

    private final ConversationRepository convRepo;
    private final MessageRepository msgRepo;

    private final PythonChatClient python;
    private final LlmInstanceManager llmInstanceManager;
    private final TelegramSendService sendService;

    // ✅ NEW: lead service to create purchase request from conversation
    private final LeadService leadService;

    private final Set<Long> processedUpdateIds = ConcurrentHashMap.newKeySet();
    private final ExecutorService workerPool = Executors.newFixedThreadPool(8);

    @PostMapping("/{secretPath}")
    public ResponseEntity<String> onUpdate(
            @PathVariable String secretPath,
            @RequestBody Map<String, Object> update
    ) {
        workerPool.submit(() -> {
            try {
                handle(secretPath, update);
            } catch (Exception e) {
                log.error("Telegram webhook async error", e);
            }
        });
        return ResponseEntity.ok("ok");
    }

    @SuppressWarnings("unchecked")
    private void handle(String secretPath, Map<String, Object> update) {
        TelegramBotBinding binding = bindingRepo.findBySecretPathAndStatus(secretPath, "ACTIVE")
                .orElseThrow(() -> new IllegalArgumentException("Invalid telegram secretPath"));

        Long updateId = update.get("update_id") instanceof Number n ? n.longValue() : null;
        if (updateId != null && !processedUpdateIds.add(updateId)) {
            log.info("Skip duplicate telegram update_id={}", updateId);
            return;
        }

        String prevTenant = TenantContext.get();
        try {
            TenantContext.set(binding.getTenantId().toString());

            Map<String, Object> msg = (Map<String, Object>) update.get("message");
            if (msg == null) return;

            String text = (String) msg.get("text");
            if (text == null || text.isBlank()) return;

            Map<String, Object> chat = (Map<String, Object>) msg.get("chat");
            if (chat == null) return;

            // chat.id là nơi trả lời (private/group)
            String chatId = String.valueOf(chat.get("id"));

            log.info("Telegram IN chatId={}, updateId={}, text={}", chatId, updateId, text);

            ChatbotInstance bot = botRepo.findById(binding.getChatbotId())
                    .orElseThrow(() -> new IllegalStateException("Bot not found: " + binding.getChatbotId()));

            // map conversation theo userExternalId = chatId
            Conversation conv = convRepo
                    .findByTenantIdAndChatbotIdAndUserExternalId(binding.getTenantId(), bot.getId(), chatId)
                    .orElseGet(() -> {
                        Conversation c = new Conversation();
                        c.setId(UUID.randomUUID());
                        c.setTenantId(binding.getTenantId());
                        c.setChatbotId(bot.getId());
                        c.setUserExternalId(chatId);
                        return convRepo.save(c);
                    });

            // ✅ Save user message
            Message mUser = new Message();
            mUser.setId(UUID.randomUUID());
            mUser.setTenantId(binding.getTenantId());
            mUser.setConversationId(conv.getId());
            mUser.setRole("user");
            mUser.setContent(text);
            msgRepo.save(mUser);

            List<Message> historyMsgs = msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(conv.getId());

            // ✅ Feedback quick: user sends 👍 or 👎
            if ("👍".equals(text.trim()) || "👎".equals(text.trim())) {
                boolean isCorrect = "👍".equals(text.trim());

                String lastQ = null, lastA = null;
                for (int i = historyMsgs.size() - 1; i >= 0; i--) {
                    Message mm = historyMsgs.get(i);
                    if (lastA == null && "assistant".equals(mm.getRole())) lastA = mm.getContent();
                    else if (lastQ == null && "user".equals(mm.getRole())) { lastQ = mm.getContent(); break; }
                }

                String baseUrl = llmInstanceManager.getOrStartBaseUrl(binding.getTenantId(), bot);

                python.feedback(baseUrl, new com.app.modelserver.dto.FeedbackRequest(
                        conv.getId().toString(),
                        binding.getTenantId().toString(),
                        "telegram",
                        lastQ != null ? lastQ : "",
                        lastA != null ? lastA : "",
                        isCorrect,
                        "thumb"
                ));

                sendService.sendText(binding.getBotToken(), chatId, "Cảm ơn bạn đã phản hồi!");
                return;
            }

            // ✅ per-tenant LLM instance (needed for CONFIRM too)
            String baseUrl = llmInstanceManager.getOrStartBaseUrl(binding.getTenantId(), bot);

            // =========================================================
            // ✅ NEW: CONFIRM / CANCEL handler (as instructed)
            // customerHandle = chatId (or username nếu bạn muốn đổi sau)
            // =========================================================
            String t = text == null ? "" : text.trim();

            if ("CONFIRM".equalsIgnoreCase(t)) {
                try {
                    leadService.createLeadFromConversation(
                            baseUrl,
                            binding.getTenantId().toString(),
                            "telegram",
                            conv.getId().toString(),
                            String.valueOf(chatId)
                    );
                    sendService.sendText(binding.getBotToken(), chatId,
                            "✅ Purchase request created. A staff member will contact you shortly to confirm the details.");
                } catch (Exception e) {
                    log.error("CONFIRM failed: tenantId={}, convId={}, chatId={}", binding.getTenantId(), conv.getId(), chatId, e);
                    sendService.sendText(binding.getBotToken(), chatId,
                            "Sorry — I couldn’t create the purchase request right now. Please try again, or share your phone/email and I’ll forward it to staff.");
                }
                return;
            }

            if ("CANCEL".equalsIgnoreCase(t)) {
                sendService.sendText(binding.getBotToken(), chatId,
                        "No problem — I’ve canceled the confirmation step. What would you like to do next?");
                return;
            }

            // Build history for python (current logic only includes user turns)
            List<String> history = new ArrayList<>();
            for (Message hm : historyMsgs) {
                if ("user".equals(hm.getRole())) history.add(hm.getContent());
            }

            ChatResponse ai = python.chat(
                    baseUrl, text, history, bot,
                    conv.getId().toString(),
                    "telegram",
                    binding.getTenantId().toString()
            );

            String reply = ai.reply();

            Message mBot = new Message();
            mBot.setId(UUID.randomUUID());
            mBot.setTenantId(binding.getTenantId());
            mBot.setConversationId(conv.getId());
            mBot.setRole("assistant");
            mBot.setContent(reply);
            msgRepo.save(mBot);

            // ✅ FIX: send AI reply (not the feedback string)
            sendService.sendText(binding.getBotToken(), chatId, reply);

        } finally {
            if (prevTenant == null) TenantContext.clear();
            else TenantContext.set(prevTenant);
        }
    }
}
