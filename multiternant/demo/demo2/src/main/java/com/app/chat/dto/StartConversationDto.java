package com.app.chat.dto;

import jakarta.validation.constraints.NotBlank;

public record StartConversationDto(
        @NotBlank String chatbotId,
        String userExternalId
) {}
