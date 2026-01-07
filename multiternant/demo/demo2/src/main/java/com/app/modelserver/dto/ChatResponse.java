package com.app.modelserver.dto;

public record ChatResponse(
        String reply,
        Integer latency_ms,
        String model,
        String adapter
) {}