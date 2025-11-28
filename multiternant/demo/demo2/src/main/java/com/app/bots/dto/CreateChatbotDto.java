package com.app.bots.dto;

import jakarta.validation.constraints.NotBlank;

public record CreateChatbotDto(
        @NotBlank String name,
        @NotBlank String channel,
        String personaJson
) {}
