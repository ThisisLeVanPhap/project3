package com.app.messenger.dto;

import java.util.UUID;

public record CreateMessengerBindingDto(
        String pageId,
        UUID chatbotId,
        String pageAccessToken
) {}
