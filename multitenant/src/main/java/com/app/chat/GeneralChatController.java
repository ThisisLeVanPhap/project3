package com.app.chat;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.modelserver.ChatbotMode;
import com.app.modelserver.ChatRuntimeService;
import com.app.modelserver.dto.ChatResponse;
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
    private static final String LEGACY_GENERAL_CHATBOT_MODE = "general_consumer";

    private final ConversationRepository convRepo;
    private final MessageRepository msgRepo;
    private final ChatbotInstanceRepository botRepo;
    private final ChatRuntimeService chatRuntimeService;

    private ChatbotInstance getGeneralChatbot() {
        return findPreferredActiveBot(ChatbotMode.GENERAL_COMPARE)
                .or(() -> findPreferredActiveBot(LEGACY_GENERAL_CHATBOT_MODE))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND,
                        "General comparison chatbot not configured. Please set up a chatbot with mode='general_compare'"));
    }

    private ChatbotInstance getChatbotForMode(String requestedMode) {
        String mode = resolveGeneralMode(requestedMode);
        if (ChatbotMode.MARKET_PRICE.equals(mode)) {
            return findPreferredActiveBot(ChatbotMode.MARKET_PRICE)
                    .or(this::optionalGeneralChatbot)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND,
                            "Market price chatbot not configured. Please set up a chatbot with mode='market_price'"));
        }
        return getGeneralChatbot();
    }

    private Optional<ChatbotInstance> optionalGeneralChatbot() {
        return findPreferredActiveBot(ChatbotMode.GENERAL_COMPARE)
                .or(() -> findPreferredActiveBot(LEGACY_GENERAL_CHATBOT_MODE));
    }

    private Optional<ChatbotInstance> findPreferredActiveBot(String mode) {
        List<ChatbotInstance> bots = botRepo.findAllByModeAndStatusOrderByNameAsc(mode, "ACTIVE");
        return bots.stream()
                .min(Comparator.comparing((ChatbotInstance bot) -> isDemoBot(bot) ? 0 : 1)
                        .thenComparing(bot -> safe(bot.getName())))
                .or(() -> bots.stream().findFirst());
    }

    private boolean isDemoBot(ChatbotInstance bot) {
        String name = bot.getName();
        return name != null && name.trim().toUpperCase(Locale.ROOT).startsWith("DEMO");
    }

    private String resolveGeneralMode(String rawMode) {
        if (rawMode == null || rawMode.isBlank()) {
            return ChatbotMode.GENERAL_COMPARE;
        }
        String normalized = ChatbotMode.normalize(rawMode);
        return ChatbotMode.MARKET_PRICE.equals(normalized)
                ? ChatbotMode.MARKET_PRICE
                : ChatbotMode.GENERAL_COMPARE;
    }

    @GetMapping("/conversations")
    public List<Map<String, Object>> listConversations(
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam String userExternalId,
            @RequestParam(required = false) String mode
    ) {
        String owner = requireUserExternalId(userExternalId);
        ChatbotInstance bot = getChatbotForMode(mode);
        List<Conversation> convs = convRepo.findTop50ByTenantIdAndChatbotIdAndUserExternalIdOrderByCreatedAtDesc(
                SYSTEM_TENANT_ID,
                bot.getId(),
                owner
        );
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
    public List<Map<String, Object>> getMessages(
            @PathVariable UUID conversationId,
            @RequestParam String userExternalId,
            @RequestParam(required = false) String mode
    ) {
        requireOwnedGeneralConversation(conversationId, userExternalId, getChatbotForMode(mode).getId());

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
            @RequestParam String userExternalId,
            @RequestParam(required = false) String mode,
            @RequestBody Map<String, String> req
    ) {
        Conversation conv = requireOwnedGeneralConversation(conversationId, userExternalId, getChatbotForMode(mode).getId());

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
    public Map<String, Object> deleteConversation(
            @PathVariable UUID conversationId,
            @RequestParam String userExternalId,
            @RequestParam(required = false) String mode
    ) {
        Conversation conv = requireOwnedGeneralConversation(conversationId, userExternalId, getChatbotForMode(mode).getId());

        // Delete messages first
        msgRepo.deleteByConversationId(conversationId);
        convRepo.delete(conv);

        return Map.of("deleted", true, "id", conversationId);
    }

    @PostMapping("/start")
    public Map<String, Object> start(@RequestBody Map<String, String> req) {
        ChatbotInstance bot = getChatbotForMode(req.get("mode"));
        String owner = requireUserExternalId(req.get("userExternalId"));

        Conversation c = new Conversation();
        c.setId(UUID.randomUUID());
        c.setChatbotId(bot.getId());
        c.setTenantId(SYSTEM_TENANT_ID);
        c.setUserExternalId(owner);
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
        String requestedMode = resolveGeneralMode(req.get("mode"));
        ChatbotInstance bot = getChatbotForMode(requestedMode);
        Conversation conv = requireOwnedGeneralConversation(convId, req.get("userExternalId"), bot.getId());
        log.info(
                "General chat selected chatbot conversationId={} selectedChatbotId={} requestedMode={} provider={} baseModel={} adapter={}",
                convId,
                bot.getId(),
                requestedMode,
                safe(bot.getProvider()),
                safe(bot.getBaseModel()),
                "-"
        );

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

        ChatRuntimeService.Result runtimeResult = chatRuntimeService.chat(
                SYSTEM_TENANT_ID,
                bot,
                userMsg,
                history,
                convId.toString(),
                "web",
                requestedMode
        );
        String baseUrl = runtimeResult.baseUrl();
        String runtimeMode = runtimeResult.runtimeMode();
        ChatResponse resp = runtimeResult.response();

        String finalMode = ChatbotMode.finalMode(resp, requestedMode);
        log.info(
                "Chat mode contract channel=general-web tenant={} conversationId={} selectedChatbotId={} requestedMode={} finalMode={} provider={} baseModel={} adapter={} pythonRuntimeMode={} pythonBaseUrl={} triggerPurchaseRequest={}",
                SYSTEM_TENANT_ID,
                convId,
                bot.getId(),
                requestedMode,
                finalMode,
                safe(bot.getProvider()),
                safe(bot.getBaseModel()),
                "-",
                safe(runtimeMode),
                safe(baseUrl),
                resp.trigger_purchase_request()
        );
        if (Boolean.TRUE.equals(resp.trigger_purchase_request())) {
            log.info(
                    "Blocked purchase request by mode contract tenant={} conversationId={} requestedMode={} finalMode={}",
                    SYSTEM_TENANT_ID,
                    convId,
                    requestedMode,
                    finalMode
            );
        }

        Message mBot = new Message(
                UUID.randomUUID(),
                convId,
                "assistant",
                resp.reply() == null ? "" : resp.reply()
        );
        mBot.setTenantId(SYSTEM_TENANT_ID);
        msgRepo.save(mBot);

        chatRuntimeService.cleanupIdle();

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("reply", resp.reply() == null ? "" : resp.reply());
        out.put("latencyMs", resp.latency_ms());
        out.put("model", resp.model() == null ? "" : resp.model());
        out.put("adapter", resp.adapter() == null ? "" : resp.adapter());
        out.put("llmBaseUrl", baseUrl == null ? "" : baseUrl);

        return out;
    }

    private static String requireUserExternalId(String userExternalId) {
        if (userExternalId == null || userExternalId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "userExternalId is required");
        }
        return userExternalId.trim();
    }

    private static String safe(String value) {
        return value == null || value.isBlank() ? "-" : value;
    }

    private Conversation requireOwnedGeneralConversation(UUID conversationId, String userExternalId) {
        return requireOwnedGeneralConversation(conversationId, userExternalId, getGeneralChatbot().getId());
    }

    private Conversation requireOwnedGeneralConversation(UUID conversationId, String userExternalId, UUID generalChatbotId) {
        String owner = requireUserExternalId(userExternalId);
        Conversation conv = convRepo.findById(conversationId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found"));
        if (!SYSTEM_TENANT_ID.equals(conv.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }
        if (!generalChatbotId.equals(conv.getChatbotId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }
        if (!owner.equals(conv.getUserExternalId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found");
        }
        return conv;
    }
}
