package com.app.chat;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
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
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.*;

@Slf4j
@RestController
@RequestMapping("/api/general/chat")
@RequiredArgsConstructor
public class GeneralChatController {

    private static final UUID SYSTEM_TENANT_ID = UUID.fromString("00000000-0000-0000-0000-000000000000");
    private static final String GENERAL_CHATBOT_MODE = "general_consumer";

    private final ConversationRepository convRepo;
    private final MessageRepository msgRepo;
    private final ChatbotInstanceRepository botRepo;
    private final PythonChatClient pythonChatClient;
    private final LlmInstanceManager llmInstanceManager;
    private final PurchaseRequestService purchaseRequestService;

    private ChatbotInstance getGeneralChatbot() {
        return botRepo.findByModeAndStatus(GENERAL_CHATBOT_MODE, "ACTIVE")
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND,
                        "General consumer chatbot not configured. Please set up a chatbot with mode='general_consumer'"));
    }

    @GetMapping("/conversations")
    public List<Map<String, Object>> listConversations(
            @RequestParam(defaultValue = "50") int limit
    ) {
        List<Conversation> convs = convRepo.findTop50ByTenantIdAndChatbotIdOrderByCreatedAtDesc(SYSTEM_TENANT_ID, getGeneralChatbot().getId());
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
            m.put("title", c.getTitle());
            m.put("createdAt", c.getCreatedAt());
            m.put("messageCount", msgCount);
            m.put("lastPreview", lastPreview);
            out.add(m);
        }
        return out;
    }

    @GetMapping("/conversation/{conversationId}/messages")
    public List<Map<String, Object>> getMessages(@PathVariable UUID conversationId) {
        Conversation conv = convRepo.findById(conversationId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found"));

        if (!SYSTEM_TENANT_ID.equals(conv.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }

        UUID generalChatbotId = getGeneralChatbot().getId();
        if (!generalChatbotId.equals(conv.getChatbotId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }

        List<Message> msgs = msgRepo.findTop200ByTenantIdAndConversationIdOrderByCreatedAtAsc(SYSTEM_TENANT_ID, conversationId);
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
        Conversation conv = convRepo.findById(conversationId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found"));
        if (!SYSTEM_TENANT_ID.equals(conv.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }
        if (!getGeneralChatbot().getId().equals(conv.getChatbotId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }

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
        Conversation conv = convRepo.findById(conversationId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found"));
        if (!SYSTEM_TENANT_ID.equals(conv.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }
        if (!getGeneralChatbot().getId().equals(conv.getChatbotId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }

        // Delete messages first
        msgRepo.deleteByConversationId(conversationId);
        convRepo.delete(conv);

        return Map.of("deleted", true, "id", conversationId);
    }

    @PostMapping("/start")
    public Map<String, Object> start() {
        ChatbotInstance bot = getGeneralChatbot();

        Conversation c = new Conversation();
        c.setId(UUID.randomUUID());
        c.setChatbotId(bot.getId());
        c.setTenantId(SYSTEM_TENANT_ID);
        convRepo.save(c);

        return Map.of("conversationId", c.getId());
    }

    @PostMapping("/send")
    public Map<String, Object> send(@RequestBody Map<String, String> req) {
        String convIdRaw = req.get("conversationId");
        if (convIdRaw == null || convIdRaw.isBlank()) {
            throw new IllegalArgumentException("conversationId is required");
        }

        String userMsg = req.get("message");
        if (userMsg == null || userMsg.isBlank()) {
            throw new IllegalArgumentException("message is required");
        }

        UUID convId = UUID.fromString(convIdRaw);
        ChatbotInstance bot = getGeneralChatbot();

        Conversation conv = convRepo.findById(convId)
                .orElseThrow(() -> new IllegalArgumentException("Conversation not found"));

        if (!SYSTEM_TENANT_ID.equals(conv.getTenantId())) {
            throw new IllegalArgumentException("Forbidden conversation");
        }

        if (!bot.getId().equals(conv.getChatbotId())) {
            throw new IllegalArgumentException("Conversation does not belong to general chat");
        }

        Message mUser = new Message(
                UUID.randomUUID(),
                convId,
                "user",
                userMsg);
        mUser.setTenantId(SYSTEM_TENANT_ID);
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
            LlmInstanceManager.Session session = llmInstanceManager.getOrStartSession(SYSTEM_TENANT_ID, bot);
            baseUrl = session.baseUrl();
            resp = pythonChatClient.chat(
                    baseUrl,
                    userMsg,
                    history,
                    bot,
                    convId.toString(),
                    "web",
                    SYSTEM_TENANT_ID.toString(),
                    session.coldStart(),
                    session.warmupWaited()
            );
        } catch (ChatbotUpstreamException ex) {
            baseUrl = ex.getBaseUrl() == null ? "" : ex.getBaseUrl();
            resp = PythonChatFallbacks.forFailure(bot.getBaseModel(), bot.getAdapterPath(), ex.getCategory());
        }

        Message mBot = new Message(
                UUID.randomUUID(),
                convId,
                "assistant",
                resp.reply() == null ? "" : resp.reply()
        );
        mBot.setTenantId(SYSTEM_TENANT_ID);
        msgRepo.save(mBot);

        // Create purchase request if triggered by chatbot (lead captured)
        if (Boolean.TRUE.equals(resp.trigger_purchase_request())) {
            String phone = resp.captured_phone();
            if (phone != null && !phone.isBlank()) {
                try {
                    String customerName = resp.captured_name();
                    if (customerName == null || customerName.isBlank()) {
                        customerName = "Chat User";
                    }
                    String transcript = "User: " + userMsg + "\nAssistant: " + resp.reply();
                    purchaseRequestService.createFromChat(
                            SYSTEM_TENANT_ID.toString(),
                            convId.toString(),
                            phone,
                            customerName,
                            transcript
                    );
                    log.info("Created purchase request from conversation {}", convId);
                } catch (Exception e) {
                    log.warn("Failed to create purchase request for conversation {}", convId, e);
                }
            }
        }

        llmInstanceManager.cleanupIdle();

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("reply", resp.reply() == null ? "" : resp.reply());
        out.put("latencyMs", resp.latency_ms());
        out.put("model", resp.model() == null ? "" : resp.model());
        out.put("adapter", resp.adapter() == null ? "" : resp.adapter());
        out.put("llmBaseUrl", baseUrl == null ? "" : baseUrl);

        return out;
    }
}
