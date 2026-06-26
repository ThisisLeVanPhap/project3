package com.app.modelserver;

import com.app.bots.ChatbotInstance;
import com.app.modelserver.dto.ChatRequest;
import com.app.modelserver.dto.ChatResponse;
import com.app.modelserver.dto.FeedbackRequest;
import com.app.modelserver.dto.GenerationConfig;
import com.app.modelserver.dto.StateResponse;
import io.netty.channel.ChannelOption;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.Exceptions;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;

import java.net.ConnectException;
import java.net.NoRouteToHostException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.nio.channels.UnresolvedAddressException;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeoutException;

@Slf4j
@Service
public class PythonChatClient {

    private final WebClient.Builder builder;
    private final LlmProperties props;
    private final Map<String, WebClient> clients = new ConcurrentHashMap<>();

    public PythonChatClient(WebClient.Builder builder, LlmProperties props) {
        this.builder = builder;
        this.props = props;
    }

    private WebClient client(String baseUrl) {
        return clients.computeIfAbsent(baseUrl, url -> {
            HttpClient httpClient = HttpClient.create()
                    .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, props.getConnectTimeoutMs())
                    .responseTimeout(Duration.ofMillis(props.getResponseTimeoutMs()));
            return builder.clone()
                    .clientConnector(new ReactorClientHttpConnector(httpClient))
                    .baseUrl(url)
                    .build();
        });
    }

    public ChatResponse chat(String baseUrl, ChatRequest request, boolean coldStart, boolean warmupWaited) {
        String baseModel = request.gen() != null ? request.gen().base_model() : "unknown";
        String adapter = request.gen() != null ? request.gen().adapter() : null;
        String requestedMode = request.gen() != null ? request.gen().mode() : request.mode();

        try {
            ChatResponse response = client(baseUrl).post()
                    .uri("/chat")
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(ChatResponse.class)
                    .timeout(Duration.ofMillis(props.getResponseTimeoutMs()))
                    .block();
            log.info(
                    "Python chat response tenant={} channel={} requestedMode={} finalMode={} provider={} baseModel={} adapter={} baseUrl={} triggerPurchaseRequest={}",
                    request.tenant_id(),
                    request.channel(),
                    ChatbotMode.normalize(requestedMode),
                    ChatbotMode.finalMode(response, requestedMode),
                    request.gen() != null ? safe(request.gen().provider()) : "-",
                    safe(baseModel),
                    safe(adapter),
                    safe(baseUrl),
                    response != null ? response.trigger_purchase_request() : null
            );
            return response;
        } catch (Exception ex) {
            ChatbotUpstreamException upstream = classify(baseUrl, request.tenant_id(), coldStart, warmupWaited, ex);
            log.warn(
                    "Chatbot upstream failure tenant={} baseUrl={} category={} status={} coldStart={} warmupWaited={} channel={} provider={} baseModel={} adapter={} message={}",
                    upstream.getTenantId(),
                    upstream.getBaseUrl(),
                    upstream.getCategory(),
                    upstream.getUpstreamStatus(),
                    upstream.isColdStart(),
                    upstream.isWarmupWaited(),
                    request.channel(),
                    request.gen() != null ? safe(request.gen().provider()) : "-",
                    safe(baseModel),
                    safe(adapter),
                    upstream.getMessage(),
                    upstream
            );
            return PythonChatFallbacks.forFailure(baseModel, adapter, upstream.getCategory());
        }
    }

    public ChatResponse chat(String baseUrl,
                             String message,
                             List<String> history,
                             ChatbotInstance cfg,
                             String conversationId,
                             String channel,
                             String tenantId,
                             boolean coldStart,
                             boolean warmupWaited) {
        return chat(
                baseUrl,
                message,
                history,
                cfg,
                conversationId,
                channel,
                tenantId,
                ChatbotMode.normalize(cfg.getMode()),
                coldStart,
                warmupWaited
        );
    }

    public ChatResponse chat(String baseUrl,
                             String message,
                             List<String> history,
                             ChatbotInstance cfg,
                             String conversationId,
                             String channel,
                             String tenantId,
                             String requestedMode,
                             boolean coldStart,
                             boolean warmupWaited) {

        String mode = ChatbotMode.normalize(requestedMode);

        // Claude is system-level provider: do not forward per-chatbot API config fields.
        // Key/model/base URL are resolved from env in Python.
        GenerationConfig gen = new GenerationConfig(
                cfg.getBaseModel(),
                null,
                cfg.getTokenizerPath(),
                cfg.getSystemPrompt(),
                cfg.getMaxNewTokens(),
                cfg.getTemperature(),
                cfg.getTopP(),
                cfg.getTopK(),
                cfg.getResponseStyle(),
                List.of("## Instruction:", "## # System:", "## System:", "### Instruction:", "### System:", "</s>"),
                cfg.getProvider(),
                null,  // api_model - system-level env only
                null,  // api_key - system-level env only
                null,  // api_base_url - system-level env only
                mode,
                ChatbotMode.DEFAULT_RETRIEVAL_MODE,
                null
        );

        ChatRequest request = new ChatRequest(
                message,
                history,
                gen,
                conversationId,
                channel,
                tenantId,
                mode
        );
        return chat(baseUrl, request, coldStart, warmupWaited);
    }

    public void feedback(String baseUrl, FeedbackRequest req) {
        client(baseUrl).post()
                .uri("/feedback")
                .bodyValue(req)
                .retrieve()
                .bodyToMono(String.class)
                .onErrorResume(ex -> {
                    ex.printStackTrace();
                    return Mono.just("error");
                })
                .block();
    }

    public StateResponse getState(String baseUrl, String conversationId) {
        return client(baseUrl).get()
                .uri(uriBuilder -> uriBuilder.path("/state")
                        .queryParam("conversation_id", conversationId)
                        .build())
                .retrieve()
                .bodyToMono(StateResponse.class)
                .block();
    }

    public void resetState(String baseUrl, String tenantId, String conversationId) {
        client(baseUrl).post()
                .uri("/state/reset")
                .bodyValue(Map.of(
                        "tenant_id", tenantId,
                        "conversation_id", conversationId
                ))
                .retrieve()
                .bodyToMono(String.class)
                .block();
    }

    private ChatbotUpstreamException classify(
            String baseUrl,
            String tenantId,
            boolean coldStart,
            boolean warmupWaited,
            Throwable error
    ) {
        Throwable root = Exceptions.unwrap(error);

        if (root instanceof ChatbotUpstreamException upstream) {
            return upstream;
        }
        if (root instanceof WebClientResponseException responseException) {
            int status = responseException.getStatusCode().value();
            UpstreamFailureCategory category = responseException.getStatusCode().is4xxClientError()
                    ? UpstreamFailureCategory.UPSTREAM_4XX
                    : UpstreamFailureCategory.UPSTREAM_5XX;
            return new ChatbotUpstreamException(
                    category,
                    tenantId,
                    baseUrl,
                    status,
                    coldStart,
                    warmupWaited,
                    "Upstream chatbot returned HTTP " + status,
                    responseException
            );
        }
        if (isTimeout(root)) {
            return new ChatbotUpstreamException(
                    UpstreamFailureCategory.TIMEOUT,
                    tenantId,
                    baseUrl,
                    null,
                    coldStart,
                    warmupWaited,
                    "Timed out waiting for chatbot response",
                    root
            );
        }
        if (root instanceof WebClientRequestException requestException) {
            Throwable requestRoot = requestException.getCause() == null
                    ? requestException
                    : Exceptions.unwrap(requestException.getCause());
            if (isTimeout(requestRoot)) {
                return new ChatbotUpstreamException(
                        UpstreamFailureCategory.TIMEOUT,
                        tenantId,
                        baseUrl,
                        null,
                        coldStart,
                        warmupWaited,
                        "Timed out contacting chatbot service",
                        requestException
                );
            }
            if (requestRoot instanceof ConnectException
                    || requestRoot instanceof UnknownHostException
                    || requestRoot instanceof NoRouteToHostException
                    || requestRoot instanceof UnresolvedAddressException) {
                return new ChatbotUpstreamException(
                        UpstreamFailureCategory.UNAVAILABLE,
                        tenantId,
                        baseUrl,
                        null,
                        coldStart,
                        warmupWaited,
                        "Chatbot service is unavailable",
                        requestException
                );
            }
        }

        return new ChatbotUpstreamException(
                UpstreamFailureCategory.UNAVAILABLE,
                tenantId,
                baseUrl,
                null,
                coldStart,
                warmupWaited,
                "Chatbot request failed before a valid response was received",
                root
        );
    }

    private static boolean isTimeout(Throwable error) {
        if (error instanceof TimeoutException || error instanceof SocketTimeoutException) {
            return true;
        }
        String className = error == null ? "" : error.getClass().getName();
        return className.endsWith("TimeoutException");
    }

    private static String safe(String value) {
        return value == null || value.isBlank() ? "-" : value;
    }
}
