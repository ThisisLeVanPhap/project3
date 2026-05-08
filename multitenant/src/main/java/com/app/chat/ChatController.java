package com.app.chat;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.leads.LeadService;
import com.app.modelserver.ChatbotUpstreamException;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
import com.app.modelserver.PythonChatFallbacks;
import com.app.modelserver.dto.ChatResponse;
import com.app.purchases.PurchaseRequest;
import com.app.purchases.PurchaseRequestService;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.*;

@Slf4j
@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {

    private static final String PURCHASE_REQUEST_BLOCKED_REPLY =
            "Mình có thể hỗ trợ tạo yêu cầu mua hàng, nhưng cần bạn cung cấp đầy đủ họ tên, số điện thoại và địa chỉ nhận hàng trong cuộc chat này nhé.";
    private static final String PURCHASE_REQUEST_ERROR_REPLY =
            "Xin lỗi, hiện tại hệ thống chưa tạo được yêu cầu mua hàng. Bạn vui lòng thử lại sau nhé.";

    private final ConversationRepository convRepo;
    private final MessageRepository msgRepo;
    private final ChatbotInstanceRepository botRepo;
    private final PythonChatClient pythonChatClient;
    private final LlmInstanceManager llmInstanceManager;
    private final LeadService leadService;
    private final PurchaseRequestService purchaseRequestService;
    private final LeadRepository leadRepo;

    @GetMapping("/conversations")
    public List<Map<String, Object>> listConversations(
            @RequestParam UUID chatbotId,
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(required = false) String userExternalId
    ) {
        String tenantRaw = TenantContext.get();
        if (tenantRaw == null || tenantRaw.isBlank()) {
            throw new IllegalStateException("Missing tenant context");
        }
        UUID tenantId = UUID.fromString(tenantRaw);

        List<Conversation> convs;
        if (userExternalId != null && !userExternalId.isBlank()) {
            convs = convRepo.findTop50ByTenantIdAndChatbotIdAndUserExternalIdOrderByCreatedAtDesc(
                    tenantId, chatbotId, userExternalId);
        } else {
            convs = convRepo.findTop50ByTenantIdAndChatbotIdOrderByCreatedAtDesc(tenantId, chatbotId);
        }
        if (limit > 0 && limit < convs.size()) {
            convs = convs.subList(0, Math.min(limit, convs.size()));
        }

        List<Map<String, Object>> out = new ArrayList<>();
        for (Conversation c : convs) {
            long msgCount = msgRepo.countByConversationId(c.getId());
            Optional<Message> last = Optional.ofNullable(msgRepo.findFirstByConversationIdOrderByCreatedAtDesc(c.getId()));
            String lastPreview = last.map(m -> m.getContent())
                    .filter(s -> s != null)
                    .map(s -> s.length() > 80 ? s.substring(0, 80) + "…" : s)
                    .orElse("-");

            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", c.getId());
            m.put("title", c.getTitle()); // may be null
            m.put("createdAt", c.getCreatedAt());
            m.put("messageCount", msgCount);
            m.put("lastPreview", lastPreview);
            out.add(m);
        }
        return out;
    }

    @GetMapping("/conversation/{conversationId}/messages")
    public List<Map<String, Object>> getMessages(@PathVariable UUID conversationId) {
        String tenantRaw = TenantContext.get();
        if (tenantRaw == null || tenantRaw.isBlank()) {
            throw new IllegalStateException("Missing tenant context");
        }
        UUID tenantId = UUID.fromString(tenantRaw);

        Conversation conv = requireConversationOwnership(tenantId, conversationId);

        List<Message> msgs = msgRepo.findTop200ByTenantIdAndConversationIdOrderByCreatedAtAsc(tenantId, conversationId);
        List<Map<String, Object>> out = new ArrayList<>();
        for (Message msg : msgs) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("role", msg.getRole());
            m.put("content", msg.getContent());
            m.put("createdAt", msg.getCreatedAt());
            out.add(m);
        }
        return out;
    }

    @PutMapping("/conversation/{conversationId}/rename")
    public Map<String, Object> renameConversation(
            @PathVariable UUID conversationId,
            @RequestBody Map<String, String> req
    ) {
        String tenantRaw = TenantContext.get();
        if (tenantRaw == null || tenantRaw.isBlank()) {
            throw new IllegalStateException("Missing tenant context");
        }
        UUID tenantId = UUID.fromString(tenantRaw);

        Conversation conv = requireConversationOwnership(tenantId, conversationId);

        String title = req.get("title");
        if (title == null || title.isBlank()) {
            throw new IllegalArgumentException("title is required");
        }
        if (title.length() > 200) {
            title = title.substring(0, 200);
        }

        conv.setTitle(title);
        convRepo.save(conv);

        return Map.of("id", conv.getId(), "title", conv.getTitle());
    }

    @DeleteMapping("/conversation/{conversationId}")
    public Map<String, Object> deleteConversation(@PathVariable UUID conversationId) {
        String tenantRaw = TenantContext.get();
        if (tenantRaw == null || tenantRaw.isBlank()) {
            throw new IllegalStateException("Missing tenant context");
        }
        UUID tenantId = UUID.fromString(tenantRaw);

        Conversation conv = requireConversationOwnership(tenantId, conversationId);

        // Delete messages first (no cascade configured)
        msgRepo.deleteByConversationId(conversationId);
        convRepo.delete(conv);

        return Map.of("deleted", true, "id", conversationId);
    }

    @PostMapping("/start")
    public Map<String, Object> start(@RequestBody Map<String, String> req) {
        String tenantRaw = TenantContext.get();
        if (tenantRaw == null || tenantRaw.isBlank()) {
            throw new IllegalStateException("Missing tenant context");
        }

        String chatbotIdRaw = req.get("chatbotId");
        if (chatbotIdRaw == null || chatbotIdRaw.isBlank()) {
            throw new IllegalArgumentException("chatbotId is required");
        }

        String userExternalId = req.get("userExternalId"); // optional

        UUID tenantId = UUID.fromString(tenantRaw);
        UUID chatbotId = UUID.fromString(chatbotIdRaw);

        // Validate chatbot belongs to this tenant
        ChatbotInstance bot = botRepo.findById(chatbotId)
                .orElseThrow(() -> new IllegalArgumentException("Chatbot not found"));
        if (!tenantId.equals(bot.getTenantId())) {
            throw new IllegalArgumentException("Chatbot does not belong to this tenant");
        }

        Conversation c = new Conversation();
        c.setId(UUID.randomUUID());
        c.setChatbotId(chatbotId);
        c.setTenantId(tenantId);
        if (userExternalId != null && !userExternalId.isBlank()) {
            c.setUserExternalId(userExternalId);
        }
        convRepo.save(c);

        return Map.of("conversationId", c.getId());
    }

    @PostMapping("/send")
    public Map<String, Object> send(@RequestBody Map<String, String> req) {
        String tenantRaw = TenantContext.get();
        if (tenantRaw == null || tenantRaw.isBlank()) {
            throw new IllegalStateException("Missing tenant context");
        }

        String convIdRaw = req.get("conversationId");
        if (convIdRaw == null || convIdRaw.isBlank()) {
            throw new IllegalArgumentException("conversationId is required");
        }

        String userMsg = req.get("message");
        if (userMsg == null || userMsg.isBlank()) {
            throw new IllegalArgumentException("message is required");
        }

        UUID tenantId = UUID.fromString(tenantRaw);
        UUID convId = UUID.fromString(convIdRaw);

        Conversation conv = requireConversationOwnership(tenantId, convId);

        ChatbotInstance bot = botRepo.findById(conv.getChatbotId())
                .orElseThrow(() -> new IllegalArgumentException("Chatbot not found"));

        Message mUser = new Message(
                UUID.randomUUID(),
                convId,
                "user",
                userMsg);
        mUser.setTenantId(tenantId);
        msgRepo.save(mUser);

        // Auto-generate title from first user message if conversation has no title
        if (conv.getTitle() == null || conv.getTitle().isBlank()) {
            String title = userMsg.replaceAll("[\\n\\r]+", " ").trim();
            if (title.length() > 50) {
                title = title.substring(0, 50) + "...";
            }
            if (title.length() > 0) {
                conv.setTitle(title);
                convRepo.save(conv);
            }
        }

        List<Message> historyMsgs = msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(convId);

        List<String> history = new ArrayList<>();
        for (Message m : historyMsgs) {
            if ("user".equals(m.getRole())) {
                history.add(m.getContent());
            }
        }

        String baseUrl = "";
        ChatResponse resp;
        try {
            LlmInstanceManager.Session session = llmInstanceManager.getOrStartSession(tenantId, bot);
            baseUrl = session.baseUrl();
            resp = pythonChatClient.chat(
                    baseUrl,
                    userMsg,
                    history,
                    bot,
                    convId.toString(),
                    "web",
                    tenantId.toString(),
                    session.coldStart(),
                    session.warmupWaited()
            );
        } catch (ChatbotUpstreamException ex) {
            baseUrl = ex.getBaseUrl() == null ? "" : ex.getBaseUrl();
            resp = PythonChatFallbacks.forFailure(bot.getBaseModel(), bot.getAdapterPath(), ex.getCategory());
        }

        if (Boolean.TRUE.equals(resp.trigger_purchase_request()) && !baseUrl.isBlank()) {
            // Check if lead already created for this conversation (duplicate prevention)
            if (conv.isLeadCreated()) {
                resp = new ChatResponse(
                        "Yêu cầu mua hàng cho cuộc hội thoại này đã được tạo rồi. Nhân viên sẽ sớm liên hệ với bạn ạ.",
                        resp.latency_ms(),
                        resp.model(),
                        resp.adapter(),
                        false,
                        null,
                        null
                );
            } else {
                try {
                    Lead lead = leadService.createLeadFromConversation(
                            baseUrl,
                            tenantId.toString(),
                            "web",
                            convId.toString(),
                            ""
                    );
                    PurchaseRequest purchaseRequest = purchaseRequestService.findOrCreateFromLead(lead);

                    // Mark conversation as having lead created (idempotency)
                    conv.setLeadCreated(true);
                    convRepo.save(conv);

                    // Update lead status to CONTACTED
                    lead.setStatus("CONTACTED");
                    leadRepo.save(lead);

                    resp = new ChatResponse(
                            buildPurchaseRequestReply(purchaseRequest),
                            resp.latency_ms(),
                            resp.model(),
                            resp.adapter(),
                            false,
                            null,
                            null
                    );
                } catch (IllegalStateException ex) {
                    log.info("Blocked purchase request tenant={} conversationId={} reason={}", tenantId, convId, ex.getMessage());
                    resp = new ChatResponse(
                            PURCHASE_REQUEST_BLOCKED_REPLY,
                            resp.latency_ms(),
                            resp.model(),
                            resp.adapter(),
                            false,
                            null,
                            null
                    );
                } catch (Exception ex) {
                    log.error("Failed to persist purchase request tenant={} conversationId={}", tenantId, convId, ex);
                    resp = new ChatResponse(
                            PURCHASE_REQUEST_ERROR_REPLY,
                            resp.latency_ms(),
                            resp.model(),
                            resp.adapter(),
                            false,
                            null,
                            null
                    );
                }
            }
        }

        Message mBot = new Message(
                UUID.randomUUID(),
                convId,
                "assistant",
                resp.reply() == null ? "" : resp.reply()
        );
        mBot.setTenantId(tenantId);
        msgRepo.save(mBot);

        llmInstanceManager.cleanupIdle();

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("reply", resp.reply() == null ? "" : resp.reply());
        out.put("latencyMs", resp.latency_ms());
        out.put("model", resp.model() == null ? "" : resp.model());
        out.put("adapter", resp.adapter() == null ? "" : resp.adapter());
        out.put("llmBaseUrl", baseUrl == null ? "" : baseUrl);

        return out;
    }

    // Helper: check tenant ownership AND optional userExternalId ownership
    private Conversation requireConversationOwnership(UUID tenantId, UUID conversationId) {
        Conversation conv = convRepo.findById(conversationId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found"));
        if (!tenantId.equals(conv.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }
        return conv;
    }

    private static String buildPurchaseRequestReply(PurchaseRequest purchaseRequest) {
        List<String> lines = new ArrayList<>();
        String customerName = safe(purchaseRequest.getCustomerName());
        String phone = safe(purchaseRequest.getPhone());
        String shippingAddress = safe(purchaseRequest.getShippingAddress());

        if (!customerName.isBlank()) {
            lines.add("Cảm ơn " + customerName + "! Mình đã ghi nhận yêu cầu mua hàng của bạn rồi.");
        } else {
            lines.add("Mình đã ghi nhận yêu cầu mua hàng của bạn rồi.");
        }

        List<String> capturedFields = new ArrayList<>();
        if (!customerName.isBlank()) {
            capturedFields.add("Họ tên: " + customerName);
        }
        if (!phone.isBlank()) {
            capturedFields.add("SĐT: " + phone);
        }
        if (!shippingAddress.isBlank()) {
            capturedFields.add("Địa chỉ: " + shippingAddress);
        }

        if (!capturedFields.isEmpty()) {
            lines.add("Thông tin mình thu thập được:");
            for (String field : capturedFields) {
                lines.add("• " + field);
            }
        }

        lines.add("Nhân viên cửa hàng sẽ sớm liên hệ với bạn để xác nhận và hỗ trợ hoàn tất đơn hàng nhé!");
        return String.join("\n", lines);
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }
}
