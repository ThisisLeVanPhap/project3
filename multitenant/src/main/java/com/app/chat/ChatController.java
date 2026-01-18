package com.app.chat;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.PythonChatClient;
import com.app.modelserver.dto.ChatResponse;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ConversationRepository convRepo;
    private final MessageRepository msgRepo;
    private final ChatbotInstanceRepository botRepo;
    private final PythonChatClient pythonChatClient;
    private final LlmInstanceManager llmInstanceManager;

    @PostMapping("/start")
    public Map<String,Object> start(@RequestBody Map<String,String> req) {
        UUID tenantId = UUID.fromString(TenantContext.get());
        UUID chatbotId = UUID.fromString(req.get("chatbotId"));

        Conversation c = new Conversation();
        c.setId(UUID.randomUUID());
        c.setChatbotId(chatbotId);
        c.setTenantId(tenantId);
        convRepo.save(c);

        return Map.of("conversationId", c.getId());
    }

    @PostMapping("/send")
    public Map<String,Object> send(@RequestBody Map<String,String> req) {
        UUID tenantId = UUID.fromString(TenantContext.get());
        UUID convId = UUID.fromString(req.get("conversationId"));
        String userMsg = req.get("message");

        Conversation conv = convRepo.findById(convId)
                .orElseThrow(() -> new IllegalArgumentException("Conversation not found"));

        // ENFORCE tenant
        if (!tenantId.equals(conv.getTenantId())) {
            throw new IllegalArgumentException("Forbidden conversation for this tenant");
        }

        ChatbotInstance bot = botRepo.findById(conv.getChatbotId())
                .orElseThrow(() -> new IllegalArgumentException("Chatbot not found"));

        Message mUser = new Message(UUID.randomUUID(), convId, "user", userMsg);
        mUser.setTenantId(tenantId);
        msgRepo.save(mUser);

        List<Message> historyMsgs = msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(convId);

        // ✅ IMPORTANT: send only user turns (avoid treating assistant turns as user in Python prompt)
        List<String> history = new ArrayList<>();
        for (Message m : historyMsgs) {
            if ("user".equals(m.getRole())) {
                history.add(m.getContent());
            }
        }

        // per-tenant LLM instance
        String baseUrl = llmInstanceManager.getOrStartBaseUrl(tenantId, bot);

        ChatResponse resp = pythonChatClient.chat(baseUrl, userMsg, history, bot);

        Message mBot = new Message(UUID.randomUUID(), convId, "assistant", resp.reply());
        mBot.setTenantId(tenantId);
        msgRepo.save(mBot);

        // optional: cleanup idle
        llmInstanceManager.cleanupIdle();

        return Map.of(
                "reply", resp.reply(),
                "latencyMs", resp.latency_ms(),
                "model", resp.model(),
                "adapter", resp.adapter(),
                "llmBaseUrl", baseUrl
        );
    }
}
