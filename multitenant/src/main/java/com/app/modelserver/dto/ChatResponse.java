package com.app.modelserver.dto;

import java.util.Map;

public record ChatResponse(
        String reply,
        Integer latency_ms,
        String model,
        String adapter,
        Boolean trigger_purchase_request,
        String captured_phone,
        String captured_name,
        Map<String, Object> debug
) {}
