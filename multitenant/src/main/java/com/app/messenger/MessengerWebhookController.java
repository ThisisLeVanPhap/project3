package com.app.messenger;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.chat.ChannelConversationService;
import com.app.chat.Conversation;
import com.app.chat.Message;
import com.app.chat.MessageRepository;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.leads.LeadService;
import com.app.modelserver.ChatbotUpstreamException;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
import com.app.modelserver.PythonChatFallbacks;
import com.app.modelserver.dto.ChatResponse;
import com.app.purchases.PurchaseRequestService;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

// ✅ NEW: feedback imports
import com.app.feedback.Feedback;
import com.app.feedback.FeedbackRepository;

import java.util.*;
import java.util.concurrent.*;

@Slf4j
@RestController
@RequestMapping("/webhook/messenger")
@RequiredArgsConstructor
public class MessengerWebhookController {

    private final MessengerPageBindingRepository bindingRepo;
    private final MessengerProperties messengerProperties;
    private final ChatbotInstanceRepository botRepo;
    private final ChannelConversationService channelConversationService;
    private final MessageRepository msgRepo;
    private final LeadRepository leadRepo;

    private final PythonChatClient python;
    private final LlmInstanceManager llmInstanceManager;
    private final MessengerSendService sendService;
    private final LeadService leadService;
    private final PurchaseRequestService purchaseRequestService;

    // ✅ NEW: feedback repo
    private final FeedbackRepository feedbackRepo;

    private final Set<String> processedMids = ConcurrentHashMap.newKeySet();
    private final ExecutorService workerPool = Executors.newFixedThreadPool(8);

    @GetMapping
    public String verify(
            @RequestParam(name = "hub.mode", required = false) String mode,
            @RequestParam(name = "hub.verify_token", required = false) String token,
            @RequestParam(name = "hub.challenge", required = false) String challenge
    ) {
        if ("subscribe".equals(mode) && messengerProperties.getVerifyToken().equals(token)) return challenge;
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Invalid verify token");
    }

    @PostMapping
    public ResponseEntity<String> onEvent(@RequestBody Map<String, Object> payload) {
        workerPool.submit(() -> {
            try { handlePayload(payload); }
            catch (Exception e) { log.error("Messenger webhook async error", e); }
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
            if (bindingOpt.isEmpty()) continue;
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

                    String mid = msg.get("mid") != null ? String.valueOf(msg.get("mid")) : null;
                    if (mid != null && !processedMids.add(mid)) continue;

                    String senderKey = channelConversationService.buildMessengerSenderKey(pageId, psid);
                    Conversation conv = channelConversationService.findOrCreateActiveConversation(
                            binding.getTenantId(),
                            binding.getChatbotId(),
                            "messenger",
                            senderKey
                    );

                    ChatbotInstance bot = botRepo.findById(conv.getChatbotId())
                            .orElseThrow(() -> new IllegalStateException("Bot not found: " + conv.getChatbotId()));

                    // ✅ Always persist user message
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

                        sendService.sendText(psid, "Thanks for your feedback!", binding.getPageAccessToken());
                        continue;
                    }

                    String baseUrl = "";
                    String t = text.trim();

                    // ✅ CONFIRM -> create lead snapshot + stage=HANDOFF
                    if ("CONFIRM".equalsIgnoreCase(t)) {
                        try {
                            LlmInstanceManager.Session session = llmInstanceManager.getOrStartSession(binding.getTenantId(), bot);
                            baseUrl = session.baseUrl();
                            Lead lead = leadService.createLeadFromConversation(
                                    baseUrl,
                                    binding.getTenantId().toString(),
                                    "messenger",
                                    conv.getId().toString(),
                                    psid
                            );
                            purchaseRequestService.findOrCreateFromLead(lead);

                            // one single bot/system message (handoff)
                            String handoffMsg =
                                    "Thanks! Our staff will follow up to confirm delivery details.";

                            Message mBot = new Message();
                            mBot.setId(UUID.randomUUID());
                            mBot.setTenantId(binding.getTenantId());
                            mBot.setConversationId(conv.getId());
                            mBot.setRole("assistant");
                            mBot.setContent(handoffMsg);
                            msgRepo.save(mBot);

                            sendService.sendText(psid, handoffMsg, binding.getPageAccessToken());
                        } catch (Exception e) {
                            log.error("CONFIRM failed", e);
                            sendService.sendText(
                                    psid,
                                    "Sorry — I couldn’t create the purchase request right now. Please try again.",
                                    binding.getPageAccessToken()
                            );
                        }
                        continue;
                    }

                    // CANCEL: allow bot to continue (no lead)
                    if ("CANCEL".equalsIgnoreCase(t)) {
                        sendService.sendText(psid,
                                "No problem — I’ve canceled the confirmation step. What would you like to do next?",
                                binding.getPageAccessToken());
                        continue;
                    }

                    // ✅ HANDOFF GATE: if lead exists and stage=HANDOFF, do NOT call python
                    Optional<Lead> leadOpt =
                            leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(
                                    binding.getTenantId().toString(), conv.getId().toString());

                    if (leadOpt.isPresent() && "HANDOFF".equalsIgnoreCase(leadOpt.get().getStage())) {
                        // Staff owns chat now: persist only, no bot reply.
                        log.info("Handoff gate: skip LLM for convId={}, psid={}", conv.getId(), psid);
                        continue;
                    }

                    // Normal: call python
                    List<Message> historyMsgs = msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(conv.getId());
                    List<String> history = new ArrayList<>();
                    for (Message hm : historyMsgs) if ("user".equals(hm.getRole())) history.add(hm.getContent());

                    ChatResponse ai;
                    try {
                        LlmInstanceManager.Session session = llmInstanceManager.getOrStartSession(binding.getTenantId(), bot);
                        baseUrl = session.baseUrl();
                        ai = python.chat(
                                baseUrl, text, history, bot,
                                conv.getId().toString(),
                                "messenger",
                                binding.getTenantId().toString(),
                                session.coldStart(),
                                session.warmupWaited()
                        );
                    } catch (ChatbotUpstreamException ex) {
                        baseUrl = ex.getBaseUrl() == null ? "" : ex.getBaseUrl();
                        ai = PythonChatFallbacks.forFailure(bot.getBaseModel(), bot.getAdapterPath(), ex.getCategory());
                    }

                    String reply = (ai.reply() == null) ? "" : ai.reply().trim();
                    if (reply.isBlank()) {
                        // e.g., python handoff guard returns ""
                        continue;
                    }

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
