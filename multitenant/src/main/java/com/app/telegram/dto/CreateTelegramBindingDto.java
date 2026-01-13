package com.app.telegram.dto;

import java.util.UUID;

public record CreateTelegramBindingDto(
        UUID chatbotId,
        String botToken
) {}
