package com.app.modelserver;

import com.app.bots.ChatbotInstance;
import com.app.modelserver.dto.ChatRequest;
import com.app.modelserver.dto.ChatResponse;
import com.app.modelserver.dto.GenerationConfig;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class PythonChatClient {

    private final WebClient.Builder builder;
    private final Map<String, WebClient> clients = new ConcurrentHashMap<>();

    public PythonChatClient(WebClient.Builder builder) {
        this.builder = builder;
    }

    private WebClient client(String baseUrl) {
        return clients.computeIfAbsent(baseUrl, url -> builder.baseUrl(url).build());
    }

    public ChatResponse chat(String baseUrl, ChatRequest request) {
        String baseModel = request.gen() != null ? request.gen().base_model() : "unknown";
        String adapter = request.gen() != null ? request.gen().adapter() : null;

        return client(baseUrl).post()
                .uri("/chat")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(ChatResponse.class)
                .onErrorResume(ex -> {
                    ex.printStackTrace();
                    return Mono.just(new ChatResponse(
                            "Sorry — the system is busy right now. Please try again in a moment.",
                            0,
                            baseModel,
                            adapter
                    ));
                })
                .block();
    }

    public ChatResponse chat(String baseUrl,
                             String message,
                             List<String> history,
                             ChatbotInstance cfg) {

        GenerationConfig gen = new GenerationConfig(
                cfg.getBaseModel(),
                cfg.getAdapterPath(),
                cfg.getTokenizerPath(),
                cfg.getSystemPrompt(),
                cfg.getMaxNewTokens(),
                cfg.getTemperature(),
                cfg.getTopP(),
                cfg.getTopK(),
                List.of("## Instruction:", "## # System:", "## System:", "### Instruction:", "### System:", "</s>"),
                false
        );

        ChatRequest request = new ChatRequest(message, history, gen);
        return chat(baseUrl, request);
    }
}
