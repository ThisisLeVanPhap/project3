package com.app.messenger;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class MessengerSendService {

    private final WebClient client = WebClient.create("https://graph.facebook.com/v19.0");

    public void sendText(String psid, String text, String pageAccessToken) {
        Map<String, Object> body = Map.of(
                "recipient", Map.of("id", psid),
                "message", Map.of("text", text)
        );

        client.post()
                .uri(uriBuilder -> uriBuilder
                        .path("/me/messages")
                        .queryParam("access_token", pageAccessToken)
                        .build()
                )
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .doOnError(Throwable::printStackTrace)
                .subscribe();
    }
}
