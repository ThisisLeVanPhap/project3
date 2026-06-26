package com.app.general;

import java.util.UUID;

public record QuickChannelBindResponse(
        String channelType,
        UUID tenantId,
        UUID chatbotId,
        UUID bindingId,
        String webhookUrl,
        String message
) {}
