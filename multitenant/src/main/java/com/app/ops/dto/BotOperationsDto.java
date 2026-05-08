package com.app.ops.dto;

import java.util.UUID;

public record BotOperationsDto(
        UUID botId,
        String name,
        String channel,
        String status,
        String baseModel,
        String responseStyle
) {
}
