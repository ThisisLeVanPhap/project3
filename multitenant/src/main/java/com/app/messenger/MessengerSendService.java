package com.app.messenger;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class MessengerSendService {

    private final WebClient client = WebClient.create("https://graph.facebook.com/v19.0");

    public Mono<Void> sendText(String psid, String text, String pageAccessToken) {
        return sendText(null, psid, text, pageAccessToken);
    }

    public Mono<Void> sendText(String pageId, String psid, String text, String pageAccessToken) {
        Map<String, Object> body = Map.of(
                "recipient", Map.of("id", psid),
                "message", Map.of("text", text)
        );

        Mono<Void> sendAttempt = client.post()
                .uri(uriBuilder -> uriBuilder
                        .path("/me/messages")
                        .queryParam("access_token", pageAccessToken)
                        .build()
                )
                .bodyValue(body)
                .retrieve()
                .onStatus(HttpStatusCode::isError, response -> response.bodyToMono(String.class)
                        .defaultIfEmpty("")
                        .flatMap(errorBody -> {
                            log.warn(
                                    "Messenger Graph API send failed pageId={} recipientId={} status={} error={}",
                                    pageId,
                                    psid,
                                    response.statusCode().value(),
                                    summarizeGraphError(errorBody)
                            );
                            return Mono.error(new GraphApiSendException(response.statusCode().value()));
                        }))
                .bodyToMono(String.class)
                .doOnSuccess(ignored -> log.debug(
                        "Messenger Graph API send accepted pageId={} recipientId={}",
                        pageId,
                        psid
                ))
                .doOnError(error -> log.warn(
                        "Messenger Graph API send error pageId={} recipientId={} errorType={}",
                        pageId,
                        psid,
                        error.getClass().getSimpleName()
                ))
                .onErrorResume(error -> Mono.empty())
                .then()
                .cache();
        sendAttempt.subscribe();
        return sendAttempt;
    }

    private static String summarizeGraphError(String errorBody) {
        if (errorBody == null || errorBody.isBlank()) {
            return "";
        }
        String singleLine = errorBody.replaceAll("\\s+", " ").trim();
        return singleLine.length() <= 200 ? singleLine : singleLine.substring(0, 200);
    }

    private static class GraphApiSendException extends RuntimeException {
        GraphApiSendException(int status) {
            super("Messenger Graph API send failed with status " + status);
        }
    }
}
