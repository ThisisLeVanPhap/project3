package com.app.modelserver.dto;

public record ChatResponse(
        String reply,
        Integer latency_ms,
        String model,
        String adapter,
        Boolean trigger_purchase_request,
        String captured_phone,
        String captured_name
) {}