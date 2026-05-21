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
import com.app.modelserver.ChatbotMode;
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
import java.util.regex.Pattern;

@Slf4j
@RestController
@RequestMapping("/webhook/messenger")
@RequiredArgsConstructor
public class MessengerWebhookController {

    private static final Pattern VIETNAM_PHONE_PATTERN = Pattern.compile("(0|\\+84)[0-9]{8,10}");
    private static final long DEMO_REPLY_MIN_DELAY_MS = 15_000L;
    private static final long DEMO_REPLY_MAX_DELAY_MS = 20_000L;

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
                    String requestedMode = ChatbotMode.normalize(bot.getMode());

                    // ✅ CONFIRM -> create lead snapshot + stage=HANDOFF
                    if ("CONFIRM".equalsIgnoreCase(t)) {
                        if (!ChatbotMode.isTenantSales(requestedMode)) {
                            String blockedMsg = "This chat mode does not create purchase requests.";
                            log.info(
                                    "Blocked Messenger CONFIRM by mode contract tenant={} conversationId={} requestedMode={}",
                                    binding.getTenantId(),
                                    conv.getId(),
                                    requestedMode
                            );
                            persistAndSendAssistantReply(binding, conv, psid, blockedMsg);
                            continue;
                        }
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

                    if (messengerProperties.isDemoMode()) {
                        String reply = scriptedMessengerReply(text);
                        log.info("[MessengerDemoFallback] using scripted response reason=demo_mode tenant={} conversationId={}",
                                binding.getTenantId(), conv.getId());
                        persistAndSendScriptedReply(binding, conv, psid, reply);
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
                    } catch (Exception ex) {
                        log.warn("Messenger AI call failed tenant={} conversationId={} psid={}",
                                binding.getTenantId(), conv.getId(), psid, ex);
                        String reply = scriptedMessengerReply(text);
                        log.info("[MessengerDemoFallback] using scripted response reason=ai_exception tenant={} conversationId={}",
                                binding.getTenantId(), conv.getId());
                        persistAndSendScriptedReply(binding, conv, psid, reply);
                        continue;
                    }

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

                    String reply = (ai.reply() == null) ? "" : ai.reply().trim();
                    if (reply.isBlank() || PythonChatFallbacks.isKnownFailureMessage(reply)) {
                        String reason = reply.isBlank() ? "blank_ai_reply" : "known_ai_failure";
                        reply = scriptedMessengerReply(text);
                        log.info("[MessengerDemoFallback] using scripted response reason={} tenant={} conversationId={}",
                                reason, binding.getTenantId(), conv.getId());
                        persistAndSendScriptedReply(binding, conv, psid, reply);
                        continue;
                    }

                    persistAndSendAssistantReply(binding, conv, psid, reply);
                }

            } finally {
                if (prevTenant == null) TenantContext.clear();
                else TenantContext.set(prevTenant);
            }
        }
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

        sendService.sendText(psid, reply, binding.getPageAccessToken());
    }

    private void persistAndSendScriptedReply(
            MessengerPageBinding binding,
            Conversation conv,
            String psid,
            String reply
    ) {
        delayScriptedDemoReply(binding, conv);
        persistAndSendAssistantReply(binding, conv, psid, reply);
    }

    private void delayScriptedDemoReply(MessengerPageBinding binding, Conversation conv) {
        long delayMs = ThreadLocalRandom.current().nextLong(DEMO_REPLY_MIN_DELAY_MS, DEMO_REPLY_MAX_DELAY_MS + 1);
        log.info("[MessengerDemoFallback] delaying scripted response delayMs={} tenant={} conversationId={}",
                delayMs, binding.getTenantId(), conv.getId());
        try {
            Thread.sleep(delayMs);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
    }

    private String scriptedMessengerReply(String message) {
        String text = message == null ? "" : message.trim().toLowerCase(Locale.ROOT);

        if (VIETNAM_PHONE_PATTERN.matcher(text).find()) {
            return "Cảm ơn bạn. Mình đã ghi nhận thông tin tư vấn: sofa cho phòng khách 20m2, gia đình 4 người, ngân sách 8-12 triệu, phong cách hiện đại, màu xám. Nhân viên Nội Thất Caco sẽ liên hệ lại để tư vấn mẫu phù hợp hơn cho bạn.";
        }

        if (isGreeting(text)) {
            return "Chào bạn, mình là trợ lý tư vấn của Nội Thất Caco. Bạn cần hỗ trợ gì?";
        }

        if (containsAny(text, "sofa", "ghế sofa")) {
            return "Với sofa phòng khách, bạn có thể chọn sofa góc chữ L nếu cần nhiều chỗ ngồi, hoặc sofa đơn để bổ sung. Bạn muốn tìm ghế cho mấy người?";
        }

        if (containsAny(text, "20m2", "20 m2", "4 người", "bốn người")) {
            return "Với phòng khách khoảng 20m2 và gia đình 4 người, bạn có thể ưu tiên sofa góc chữ L kích thước vừa hoặc sofa văng 3 chỗ kết hợp thêm ghế đơn. Nếu muốn tiết kiệm diện tích, sofa văng sẽ dễ bố trí hơn. Nếu phòng có góc trống và bạn muốn nhiều chỗ ngồi, sofa chữ L sẽ hợp lý hơn. Ngân sách dự kiến của bạn khoảng bao nhiêu để mình tư vấn sát hơn?";
        }

        if (containsAny(text, "8", "12", "triệu", "8 đến 12")) {
            return "Trong khoảng 8 đến 12 triệu, bạn có thể tham khảo các mẫu sofa vải hoặc sofa nỉ kích thước vừa, phù hợp với gia đình 4 người. Nếu ưu tiên dễ vệ sinh thì có thể chọn giả da, còn nếu ưu tiên cảm giác êm và ấm thì nên chọn vải hoặc nỉ. Với phòng 20m2, mình gợi ý bạn chọn sofa văng 3 chỗ nếu muốn không gian thoáng, hoặc sofa góc chữ L loại nhỏ nếu muốn tận dụng góc phòng. Bạn thích phong cách hiện đại, tối giản hay sang trọng hơn?";
        }

        if (containsAny(text, "hiện đại", "xám", "màu xám")) {
            return "Dạ, với phong cách hiện đại và màu xám, bạn nên chọn sofa có dáng gọn, chân thấp hoặc chân kim loại đơn giản, ít họa tiết để phòng khách nhìn thoáng hơn. Màu xám cũng dễ phối với bàn trà gỗ sáng, thảm màu be hoặc trắng kem. Mình có thể ghi nhận nhu cầu của bạn là: sofa phòng khách 20m2, gia đình 4 người, ngân sách 8-12 triệu, phong cách hiện đại, màu xám. Bạn có muốn để lại số điện thoại để cửa hàng tư vấn mẫu cụ thể hơn không?";
        }

        return "Mình đã nhận được thông tin của bạn. Bạn có thể cho mình biết thêm loại sản phẩm, diện tích phòng, số người sử dụng và ngân sách dự kiến để mình tư vấn phù hợp hơn không?";
    }

    private boolean containsAny(String text, String... keywords) {
        for (String keyword : keywords) {
            if (text.contains(keyword)) {
                return true;
            }
        }
        return false;
    }

    private boolean isGreeting(String text) {
        return containsAny(text, "hello", "xin chào", "chào")
                || Pattern.compile("(^|\\s)hi([\\s,.!?]|$)").matcher(text).find();
    }
}
