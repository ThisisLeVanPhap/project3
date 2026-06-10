package com.app.messenger.dto;

import com.app.messenger.MessengerPageBinding;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.UUID;

public record MessengerPageBindingResponse(
        UUID id,
        @JsonProperty("tenant_id")
        UUID tenantId,
        @JsonProperty("chatbot_id")
        UUID chatbotId,
        @JsonProperty("page_id")
        String pageId,
        String status,
        @JsonProperty("created_at")
        Instant createdAt,
        @JsonProperty("token_configured")
        boolean tokenConfigured,
        @JsonProperty("token_preview")
        String tokenPreview
) {
    public static MessengerPageBindingResponse from(MessengerPageBinding binding) {
        String token = binding.getPageAccessToken();
        return new MessengerPageBindingResponse(
                binding.getId(),
                binding.getTenantId(),
                binding.getChatbotId(),
                binding.getPageId(),
                binding.getStatus(),
                binding.getCreatedAt(),
                token != null && !token.isBlank(),
                maskToken(token)
        );
    }

    static String maskToken(String token) {
        if (token == null || token.isBlank()) {
            return null;
        }
        String trimmed = token.trim();
        if (trimmed.length() <= 8) {
            return "****";
        }
        return trimmed.substring(0, 4) + "..." + trimmed.substring(trimmed.length() - 4);
    }
}
