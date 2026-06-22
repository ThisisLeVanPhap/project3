package com.app.messenger;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.chat.ChannelConversationService;
import com.app.chat.Conversation;
import com.app.chat.ConversationResetRequest;
import com.app.chat.ConversationResetService;
import com.app.chat.Message;
import com.app.chat.MessageRepository;
import com.app.chat.NewConsultationSessionResponse;
import com.app.customers.CustomerIdentityService;
import com.app.feedback.Feedback;
import com.app.feedback.FeedbackRepository;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.leads.LeadService;
import com.app.modelserver.ChatbotMode;
import com.app.modelserver.ChatbotUpstreamException;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
import com.app.modelserver.PythonChatFallbacks;
import com.app.modelserver.UpstreamFailureCategory;
import com.app.modelserver.dto.ChatResponse;
import com.app.purchases.PurchaseRequestService;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

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
    private final FeedbackRepository feedbackRepo;
    private final CustomerIdentityService customerIdentityService;
    private final ConversationResetService conversationResetService;

    private final Set<String> processedMids = ConcurrentHashMap.newKeySet();
    private final ExecutorService workerPool = Executors.newFixedThreadPool(8);

    @GetMapping
    public String verify(
            @RequestParam(name = "hub.mode", required = false) String mode,
            @RequestParam(name = "hub.verify_token", required = false) String token,
            @RequestParam(name = "hub.challenge", required = false) String challenge
    ) {
        if ("subscribe".equals(mode) && messengerProperties.getVerifyToken().equals(token)) {
            return challenge;
        }
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Invalid verify token");
    }

    @PostMapping
    public ResponseEntity<String> onEvent(@RequestBody Map<String, Object> payload) {
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
            if (pageId == null || "null".equals(pageId)) {
                continue;
            }

            Optional<MessengerPageBinding> bindingOpt = bindingRepo.findByPageIdAndStatus(pageId, "ACTIVE");
            if (bindingOpt.isEmpty()) {
                log.warn("Messenger webhook ignored because no ACTIVE binding pageId={}", pageId);
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
                    if (sender == null) {
                        continue;
                    }
                    String psid = String.valueOf(sender.get("id"));

                    Map<String, Object> msg = (Map<String, Object>) ev.get("message");
                    if (msg == null) {
                        continue;
                    }

                    String text = (String) msg.get("text");
                    if (text == null || text.isBlank()) {
                        continue;
                    }

                    String mid = msg.get("mid") != null ? String.valueOf(msg.get("mid")) : null;
                    if (mid != null && !processedMids.add(mid)) {
                        continue;
                    }

                    String senderKey = channelConversationService.buildMessengerSenderKey(pageId, psid);
                    resolveCustomerIdentity(binding.getTenantId(), senderKey);
                    Conversation conv = channelConversationService.findOrCreateActiveConversation(
                            binding.getTenantId(),
                            binding.getChatbotId(),
                            "messenger",
                            senderKey
                    );

                    if (handleResetCommand(binding, conv, psid, text)) {
                        continue;
                    }

                    ChatbotInstance bot = botRepo.findById(conv.getChatbotId())
                            .orElseThrow(() -> new IllegalStateException("Bot not found: " + conv.getChatbotId()));

                    persistUserMessage(binding, conv, text);

                    String norm = text.trim().toUpperCase(Locale.ROOT);
                    if (norm.equals("RATE GOOD") || norm.equals("RATE BAD")) {
                        persistFeedback(binding, conv, norm.equals("RATE GOOD") ? 1 : -1);
                        sendService.sendText(binding.getPageId(), psid, "Thanks for your feedback!", binding.getPageAccessToken());
                        continue;
                    }

                    String requestedMode = ChatbotMode.normalize(bot.getMode());

                    if ("CONFIRM".equalsIgnoreCase(text.trim())) {
                        handleConfirm(binding, bot, conv, psid, requestedMode);
                        continue;
                    }

                    if ("CANCEL".equalsIgnoreCase(text.trim())) {
                        sendService.sendText(
                                binding.getPageId(),
                                psid,
                                "No problem. I have canceled the confirmation step. What would you like to do next?",
                                binding.getPageAccessToken()
                        );
                        continue;
                    }

                    Optional<Lead> leadOpt =
                            leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(
                                    binding.getTenantId().toString(), conv.getId().toString());

                    if (leadOpt.isPresent() && "HANDOFF".equalsIgnoreCase(leadOpt.get().getStage())) {
                        log.info("Handoff gate: skip LLM for convId={}, psid={}", conv.getId(), psid);
                        continue;
                    }

                    ChatResponse ai = callChatbot(binding, bot, conv, psid, text);
                    enforceModeContract(binding, conv, requestedMode, ai);

                    String reply = normalizeReply(bot, binding, conv, psid, ai);
                    persistAndSendAssistantReply(binding, conv, psid, reply);
                }
            } finally {
                if (prevTenant == null) {
                    TenantContext.clear();
                } else {
                    TenantContext.set(prevTenant);
                }
            }
        }
    }

    private boolean handleResetCommand(MessengerPageBinding binding, Conversation conv, String psid, String text) {
        String command = text == null ? "" : text.trim().toLowerCase(Locale.ROOT);
        if (!command.equals("/reset") && !command.equals("/reset-test") && !command.equals("/new") && !command.equals("/reset-all")) {
            return false;
        }

        String reply;
        if (command.equals("/new") || command.equals("/reset-all")) {
            NewConsultationSessionResponse ignored = conversationResetService.startNewConsultationSession(
                    binding.getTenantId(),
                    conv.getChatbotId(),
                    "messenger",
                    conv.getUserExternalId(),
                    conv.getId(),
                    conv.getUnifiedCustomerId()
            );
            reply = "Đã bắt đầu phiên tư vấn mới. Mình sẽ không dùng thông tin từ phiên cũ.";
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
            reply = "Đã reset hội thoại hiện tại.";
        }
        sendService.sendText(
                binding.getPageId(),
                psid,
                reply,
                binding.getPageAccessToken()
        );
        return true;
    }

    private void persistUserMessage(MessengerPageBinding binding, Conversation conv, String text) {
        Message mUser = new Message();
        mUser.setId(UUID.randomUUID());
        mUser.setTenantId(binding.getTenantId());
        mUser.setConversationId(conv.getId());
        mUser.setRole("user");
        mUser.setContent(text);
        msgRepo.save(mUser);
    }

    private void resolveCustomerIdentity(UUID tenantId, String senderKey) {
        if (customerIdentityService == null) {
            return;
        }
        try {
            customerIdentityService.resolveOrCreateIdentity(
                    tenantId,
                    "messenger",
                    senderKey,
                    null,
                    null,
                    null
            );
        } catch (RuntimeException ex) {
            log.debug("Skip messenger customer identity resolution tenant={} senderKey={}", tenantId, senderKey, ex);
        }
    }

    private void persistFeedback(MessengerPageBinding binding, Conversation conv, int rating) {
        Feedback fb = new Feedback();
        fb.setTenantId(binding.getTenantId().toString());
        fb.setConversationId(conv.getId().toString());
        fb.setRating(rating);
        fb.setComment("rate_keyword");
        feedbackRepo.save(fb);
    }

    private void handleConfirm(
            MessengerPageBinding binding,
            ChatbotInstance bot,
            Conversation conv,
            String psid,
            String requestedMode
    ) {
        if (!ChatbotMode.isTenantSales(requestedMode)) {
            String blockedMsg = "This chat mode does not create purchase requests.";
            log.info(
                    "Blocked Messenger CONFIRM by mode contract tenant={} conversationId={} requestedMode={}",
                    binding.getTenantId(),
                    conv.getId(),
                    requestedMode
            );
            persistAndSendAssistantReply(binding, conv, psid, blockedMsg);
            return;
        }

        try {
            LlmInstanceManager.Session session = llmInstanceManager.getOrStartSession(binding.getTenantId(), bot);
            Lead lead = leadService.createLeadFromConversation(
                    session.baseUrl(),
                    binding.getTenantId().toString(),
                    "messenger",
                    conv.getId().toString(),
                    psid
            );
            purchaseRequestService.findOrCreateFromLead(lead);

            persistAndSendAssistantReply(
                    binding,
                    conv,
                    psid,
                    "Thanks! Our staff will follow up to confirm delivery details."
            );
        } catch (Exception e) {
            log.error("CONFIRM failed", e);
            sendService.sendText(
                    binding.getPageId(),
                    psid,
                    "Sorry, I could not create the purchase request right now. Please try again.",
                    binding.getPageAccessToken()
            );
        }
    }

    private ChatResponse callChatbot(
            MessengerPageBinding binding,
            ChatbotInstance bot,
            Conversation conv,
            String psid,
            String text
    ) {
        List<Message> historyMsgs = msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(conv.getId());
        List<String> history = new ArrayList<>();
        for (Message hm : historyMsgs) {
            if ("user".equals(hm.getRole())) {
                history.add(hm.getContent());
            }
        }

        try {
            LlmInstanceManager.Session session = llmInstanceManager.getOrStartSession(binding.getTenantId(), bot);
            return python.chat(
                    session.baseUrl(),
                    text,
                    history,
                    bot,
                    conv.getId().toString(),
                    "messenger",
                    binding.getTenantId().toString(),
                    session.coldStart(),
                    session.warmupWaited()
            );
        } catch (ChatbotUpstreamException ex) {
            return PythonChatFallbacks.forFailure(bot.getBaseModel(), bot.getAdapterPath(), ex.getCategory());
        } catch (Exception ex) {
            log.warn(
                    "Messenger AI call failed tenant={} conversationId={} psid={}",
                    binding.getTenantId(),
                    conv.getId(),
                    psid,
                    ex
            );
            return PythonChatFallbacks.forFailure(
                    bot.getBaseModel(),
                    bot.getAdapterPath(),
                    UpstreamFailureCategory.UNAVAILABLE
            );
        }
    }

    private void enforceModeContract(
            MessengerPageBinding binding,
            Conversation conv,
            String requestedMode,
            ChatResponse ai
    ) {
        String finalMode = ChatbotMode.finalMode(ai, requestedMode);
        log.info(
                "Chat mode contract channel=messenger tenant={} conversationId={} requestedMode={} finalMode={} triggerPurchaseRequest={}",
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
    }

    private String normalizeReply(
            ChatbotInstance bot,
            MessengerPageBinding binding,
            Conversation conv,
            String psid,
            ChatResponse ai
    ) {
        String reply = ai.reply() == null ? "" : ai.reply().trim();
        if (reply.isBlank()) {
            log.warn(
                    "Messenger AI returned blank reply tenant={} conversationId={} psid={}",
                    binding.getTenantId(),
                    conv.getId(),
                    psid
            );
            return PythonChatFallbacks
                    .forFailure(bot.getBaseModel(), bot.getAdapterPath(), UpstreamFailureCategory.UPSTREAM_5XX)
                    .reply();
        }

        if (PythonChatFallbacks.isKnownFailureMessage(reply)) {
            log.warn(
                    "Messenger AI returned fallback reply tenant={} conversationId={} psid={} reply={}",
                    binding.getTenantId(),
                    conv.getId(),
                    psid,
                    reply
            );
        }
        return reply;
    }

    private void persistAndSendAssistantReply(
            MessengerPageBinding binding,
            Conversation conv,
            String psid,
            String reply
    ) {
        Message mBot = new Message();
        mBot.setId(UUID.randomUUID());
        mBot.setTenantId(binding.getTenantId());
        mBot.setConversationId(conv.getId());
        mBot.setRole("assistant");
        mBot.setContent(reply);
        msgRepo.save(mBot);

        sendService.sendText(binding.getPageId(), psid, reply, binding.getPageAccessToken());
    }
}
