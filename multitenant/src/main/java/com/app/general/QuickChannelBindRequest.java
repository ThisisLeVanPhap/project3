package com.app.general;

public record QuickChannelBindRequest(
        String channelType,
        String channelName,
        String pageId,
        String botToken,
        String pageAccessToken,
        String tenantId
) {}
