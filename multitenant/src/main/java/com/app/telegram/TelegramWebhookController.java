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

            Message mUser = new Message();
            mUser.setId(UUID.randomUUID());
            mUser.setTenantId(binding.getTenantId());
            mUser.setConversationId(conv.getId());
            mUser.setRole("user");
            mUser.setContent(text);
            msgRepo.save(mUser);

            List<Message> historyMsgs = msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(conv.getId());
            List<String> history = new ArrayList<>();
            for (Message hm : historyMsgs) {
                if ("user".equals(hm.getRole())) history.add(hm.getContent());
            }

            String baseUrl = llmInstanceManager.getOrStartBaseUrl(binding.getTenantId(), bot);
            ChatResponse ai = python.chat(baseUrl, text, history, bot);
            String reply = ai.reply();

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
}
