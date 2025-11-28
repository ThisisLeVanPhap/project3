package com.app.chat.dto;

import jakarta.validation.constraints.NotBlank;

public record SendMessageDto(
        @NotBlank String conversationId,
        @NotBlank String message
) {}
