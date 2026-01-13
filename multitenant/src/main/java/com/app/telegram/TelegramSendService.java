package com.app.telegram;

import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Map;

@Service
public class TelegramSendService {

    private final WebClient http = WebClient.builder().build();

    public void sendText(String botToken, String chatId, String text) {
        String base = "https://api.telegram.org/bot" + botToken;

        Map<String, Object> body = Map.of(
                "chat_id", chatId,
                "text", text
        );

        http.post()
                .uri(base + "/sendMessage")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .doOnError(Throwable::printStackTrace)
                .subscribe();
    }
}
