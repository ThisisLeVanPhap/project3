package com.app.messenger;

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
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.*;
import java.util.concurrent.*;

@Slf4j
@RestController
@RequestMapping("/webhook/messenger")
@RequiredArgsConstructor
public class MessengerWebhookController {

    private static final String VERIFY_TOKEN = "woodchat_secret";

    private final MessengerPageBindingRepository bindingRepo;
    private final ChatbotInstanceRepository botRepo;
    private final ConversationRepository convRepo;
    private final MessageRepository msgRepo;

    private final PythonChatClient python;
    private final LlmInstanceManager llmInstanceManager;
    private final MessengerSendService sendService;

    // ✅ NEW: lead service to create purchase request from conversation
    private final LeadService leadService;

    // ✅ Dedupe theo message.mid (Meta retry sẽ bị skip)
    private final Set<String> processedMids = ConcurrentHashMap.newKeySet();

    // ✅ Thread pool để xử lý async (ACK nhanh)
    private final ExecutorService workerPool = Executors.newFixedThreadPool(8);

    @GetMapping
    public String verify(
            @RequestParam(name = "hub.mode", required = false) String mode,
            @RequestParam(name = "hub.verify_token", required = false) String token,
            @RequestParam(name = "hub.challenge", required = false) String challenge
    ) {
        if ("subscribe".equals(mode) && VERIFY_TOKEN.equals(token)) {
            return challenge;
        }
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Invalid verify token");
    }

    @PostMapping
    public ResponseEntity<String> onEvent(@RequestBody Map<String, Object> payload) {
        // ✅ ACK NGAY để Facebook không retry
        workerPool.submit(() -> {
            try {
                handlePayload(payload);
            } catch (Exception e) {
                log.error("Messenger webhook async error", e);
            }
        });
        return ResponseEntity.ok("ok");
    }

    @SuppressWarnings("unchecked")
    private void handlePayload(Map<String, Object> payload) {
        List<Map<String, Object>> entries =
                (List<Map<String, Object>>) payload.getOrDefault("entry", List.of());

        for (Map<String, Object> entry : entries) {
            String pageId = String.valueOf(entry.get("id"));
            if (pageId == null || "null".equals(pageId)) continue;

            Optional<MessengerPageBinding> bindingOpt = bindingRepo.findByPageId(pageId);
            if (bindingOpt.isEmpty()) {
                log.warn("No messenger_page_bindings for pageId={}", pageId);
                continue;
            }
            MessengerPageBinding binding = bindingOpt.get();

            String prevTenant = TenantContext.get();
            try {
                TenantContext.set(binding.getTenantId().toString());

                List<Map<String, Object>> messaging =
                        (List<Map<String, Object>>) entry.getOrDefault("messaging", List.of());

                for (Map<String, Object> ev : messaging) {

                    Map<String, Object> sender = (Map<String, Object>) ev.get("sender");
                    if (sender == null) continue;
                    String psid = String.valueOf(sender.get("id"));

                    Map<String, Object> msg = (Map<String, Object>) ev.get("message");
                    if (msg == null) continue;

                    String text = (String) msg.get("text");
                    if (text == null || text.isBlank()) continue;

                    // ✅ dedupe mid
                    String mid = msg.get("mid") != null ? String.valueOf(msg.get("mid")) : null;
                    if (mid != null && !processedMids.add(mid)) {
                        log.info("Skip duplicate messenger mid={}", mid);
                        continue;
                    }

                    log.info("Messenger IN pageId={}, psid={}, mid={}, text={}", pageId, psid, mid, text);

                    ChatbotInstance bot = botRepo.findById(binding.getChatbotId())
                            .orElseThrow(() -> new IllegalStateException("Bot not found: " + binding.getChatbotId()));

                    Conversation conv = convRepo
                            .findByTenantIdAndChatbotIdAndUserExternalId(binding.getTenantId(), bot.getId(), psid)
                            .orElseGet(() -> {
                                Conversation c = new Conversation();
                                c.setId(UUID.randomUUID());
                                c.setTenantId(binding.getTenantId());
                                c.setChatbotId(bot.getId());
                                c.setUserExternalId(psid);
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

                    List<Message> historyMsgs =
                            msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(conv.getId());

                    // ✅ Feedback quick: user sends 👍 or 👎
                    if ("👍".equals(text.trim()) || "👎".equals(text.trim())) {
                        boolean isCorrect = "👍".equals(text.trim());

                        String lastQ = null;
                        String lastA = null;
                        for (int i = historyMsgs.size() - 1; i >= 0; i--) {
                            Message mm = historyMsgs.get(i);
                            if (lastA == null && "assistant".equals(mm.getRole())) lastA = mm.getContent();
                            else if (lastQ == null && "user".equals(mm.getRole())) { lastQ = mm.getContent(); break; }
                        }

                        String baseUrl = llmInstanceManager.getOrStartBaseUrl(binding.getTenantId(), bot);

                        python.feedback(baseUrl, new com.app.modelserver.dto.FeedbackRequest(
                                conv.getId().toString(),
                                binding.getTenantId().toString(),
                                "messenger",
                                lastQ != null ? lastQ : "",
                                lastA != null ? lastA : "",
                                isCorrect,
                                "thumb"
                        ));

                        sendService.sendText(psid, "Thanks for your feedback!", binding.getPageAccessToken());
                        continue;
                    }

                    // ✅ per-tenant LLM instance (moved up so CONFIRM can use it)
                    String baseUrl = llmInstanceManager.getOrStartBaseUrl(binding.getTenantId(), bot);

                    // =========================================================
                    // ✅ NEW: CONFIRM / CANCEL handler
                    // Put here: after text, conv, tenantId(binding), bot, baseUrl, psid
                    // =========================================================
                    String t = text == null ? "" : text.trim();

                    if ("CONFIRM".equalsIgnoreCase(t)) {
                        try {
                            leadService.createLeadFromConversation(
                                    baseUrl,
                                    binding.getTenantId().toString(),
                                    "messenger",
                                    conv.getId().toString(),
                                    psid
                            );
                            sendService.sendText(
                                    psid,
                                    "✅ Purchase request created. A staff member will contact you shortly to confirm the details.",
                                    binding.getPageAccessToken()
                            );
                        } catch (Exception e) {
                            log.error("CONFIRM failed: tenantId={}, convId={}, psid={}", binding.getTenantId(), conv.getId(), psid, e);
                            sendService.sendText(
                                    psid,
                                    "Sorry — I couldn’t create the purchase request right now. Please try again, or reply with your phone/email and I’ll forward it to staff.",
                                    binding.getPageAccessToken()
                            );
                        }
                        continue;
                    }

                    if ("CANCEL".equalsIgnoreCase(t)) {
                        sendService.sendText(
                                psid,
                                "No problem — I’ve canceled the confirmation step. What would you like to do next?",
                                binding.getPageAccessToken()
                        );
                        continue;
                    }

                    // Build history for python (current logic only includes user turns)
                    List<String> history = new ArrayList<>();
                    for (Message hm : historyMsgs) {
                        if ("user".equals(hm.getRole())) {
                            history.add(hm.getContent());
                        }
                    }

                    ChatResponse ai = python.chat(
                            baseUrl, text, history, bot,
                            conv.getId().toString(),
                            "messenger",
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

                    sendService.sendText(psid, reply, binding.getPageAccessToken());
                }

            } finally {
                if (prevTenant == null) TenantContext.clear();
                else TenantContext.set(prevTenant);
            }
        }
    }
}
