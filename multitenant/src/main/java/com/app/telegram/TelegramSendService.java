package com.app.telegram;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Map;

@Service
public class TelegramSendService {

    private final WebClient http = WebClient.builder().build();
    private final String publicBaseUrl;

    public TelegramSendService(@Value("${app.public-base-url:http://localhost:8080}") String publicBaseUrl) {
        this.publicBaseUrl = publicBaseUrl;
    }

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

    public boolean setWebhook(String botToken) {
        return setWebhookUrl(botToken, buildWebhookUrl(publicBaseUrl, botToken));
    }

    public boolean setWebhook(String botToken, String publicBaseUrl, String secretPath) {
        return setWebhookUrl(botToken, buildWebhookUrl(publicBaseUrl, secretPath));
    }

    public String buildWebhookUrl(String publicBaseUrl, String secretPath) {
        String baseUrl = (publicBaseUrl == null || publicBaseUrl.isBlank())
                ? this.publicBaseUrl
                : publicBaseUrl;
        return baseUrl.replaceAll("/+$", "") + "/webhook/telegram/" + secretPath;
    }

    private boolean setWebhookUrl(String botToken, String webhookUrl) {
        String base = "https://api.telegram.org/bot" + botToken;
        try {
            String json = http.post()
                    .uri(base + "/setWebhook")
                    .bodyValue(Map.of("url", webhookUrl))
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();
            return json != null && json.contains("\"ok\":true");
        } catch (Exception e) {
            return false;
        }
    }
}
