package com.app.modelserver.dto;

import java.util.List;

public record ChatRequest(
        String message,
        List<String> history,
        GenerationConfig gen,

        // ✅ metadata (optional)
        String conversation_id,
        String channel,
        String tenant_id,
        String mode  // tenant_sales | general_consumer
) {}
