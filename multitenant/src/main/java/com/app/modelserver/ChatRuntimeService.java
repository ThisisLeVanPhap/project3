package com.app.modelserver;

import com.app.bots.ChatbotInstance;
import com.app.modelserver.dto.ChatResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ChatRuntimeService {

    private final LlmInstanceManager llmInstanceManager;
    private final PythonChatClient pythonChatClient;

    public record Result(ChatResponse response, String baseUrl, String runtimeMode) {
    }

    public Result chat(
            UUID tenantId,
            ChatbotInstance bot,
            String message,
            List<String> history,
            String conversationId,
            String channel
    ) {
        return chat(tenantId, bot, message, history, conversationId, channel, ChatbotMode.normalize(bot.getMode()));
    }

    public Result chat(
            UUID tenantId,
            ChatbotInstance bot,
            String message,
            List<String> history,
            String conversationId,
            String channel,
            String requestedMode
    ) {
        try {
            LlmInstanceManager.Session session = llmInstanceManager.getOrStartSession(tenantId, bot);
            ChatResponse response = pythonChatClient.chat(
                    session.baseUrl(),
                    message,
                    history,
                    bot,
                    conversationId,
                    channel,
                    tenantId.toString(),
                    requestedMode,
                    session.coldStart(),
                    session.warmupWaited()
            );
            return new Result(response, session.baseUrl(), session.runtimeMode());
        } catch (ChatbotUpstreamException ex) {
            String baseUrl = ex.getBaseUrl() == null ? "" : ex.getBaseUrl();
            ChatResponse fallback = PythonChatFallbacks.forFailure(bot.getBaseModel(), null, ex.getCategory());
            return new Result(fallback, baseUrl, "");
        }
    }

    public void cleanupIdle() {
        llmInstanceManager.cleanupIdle();
    }
}
